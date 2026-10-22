"""Optional read-only check of the existing router's attention injection seam."""

import importlib.util
import os
import sys
import unittest
from pathlib import Path

import torch

from adapter import SageAttentionLSE
from diagnostics import fp32_attention


@unittest.skipUnless(os.environ.get("H3_ROUTER_EXTENSION_PATH"), "set H3_ROUTER_EXTENSION_PATH")
class ExistingRouterSeamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.dont_write_bytecode = True
        extension = Path(os.environ["H3_ROUTER_EXTENSION_PATH"]).resolve()
        spec = importlib.util.spec_from_file_location(
            "isolated_h3_router_probe", extension / "__init__.py",
            submodule_search_locations=[str(extension)],
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        cls.core = sys.modules[f"{spec.name}.core"]

    def test_existing_mass_preserve_and_alpha_zero(self):
        generator = torch.Generator().manual_seed(42)
        q, k, v = [torch.randn((1, 2, 12, 64), generator=generator).half() for _ in range(3)]
        plan = {
            "query_interval_half_open": [6, 12],
            "reference_video_segment": [0, 6],
            "frame_rows": 2,
            "latent_interval_half_open": [0, 3],
        }
        calls = []

        def fake_sage(q, k, v, **kwargs):
            calls.append(q.shape)
            out, lse = fp32_attention(*(x.transpose(1, 2) for x in (q, k, v)))
            return out.to(q.dtype).transpose(1, 2).contiguous(), lse

        def direct_oracle(q, k, v):
            out, lse = fp32_attention(q, k, v)
            return out.to(q.dtype), lse

        attention = SageAttentionLSE(fake_sage)
        for alpha in (0, 0.5, 1):
            calls.clear()
            actual = self.core.route_attention(
                q, k, v, 2, plan, mode="mass_preserve", alpha=alpha, attention=attention
            )
            expected = self.core.route_attention(
                q, k, v, 2, plan, mode="mass_preserve", alpha=alpha, attention=direct_oracle
            )
            self.assertTrue(torch.equal(actual, expected))
            self.assertEqual(actual.shape, (1, 12, 128))
            if alpha == 0:
                self.assertEqual(len(calls), 1)
            else:
                self.assertEqual(len(calls), 3)
                self.assertEqual(calls[-1], (3, 2, 2, 64))
