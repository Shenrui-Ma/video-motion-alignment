"""CPU algebra tests and optional CUDA Flash toy checks; no model load.

Run: python -m unittest discover -s tests -p test_temporal_router.py -v
GPU: H3_ROUTER_TEST_DEVICE=cuda python tests/test_temporal_router.py -v
"""

import math
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extensions"))
from H3TemporalRouter import core
from H3TemporalRouter.layout import event_latent_range

try:
    import torch
except ImportError:
    torch = None


def dense_attention(q, k, v):
    logits = q @ k.transpose(-1, -2) / math.sqrt(q.shape[-1])
    return logits.softmax(-1) @ v, torch.logsumexp(logits, dim=-1)


class LayoutAndStateTests(unittest.TestCase):
    def test_actual_frame_intervals(self):
        self.assertEqual(event_latent_range(39, 44, 42), (12, 14))
        self.assertEqual(event_latent_range(50, 65, 42), (14, 20))
        self.assertEqual(event_latent_range(54, 69, 42), (16, 22))

    def test_clipped_temporal_neighborhood_has_no_duplicates(self):
        self.assertEqual(core.temporal_neighborhood(0, 4, 1, -4), (0, 2))
        self.assertEqual(core.temporal_neighborhood(3, 4, 1, 4), (2, 4))
        self.assertEqual(core.temporal_neighborhood(1, 4, 0, 1), (2, 3))
        self.assertEqual(core.temporal_neighborhood(1, 4, 1, 0), (0, 3))

    def test_invalid_ranges(self):
        for args in [(-1, 4, 0, 0), (4, 4, 0, 0), (0, 4, 2, 0), (0, 4, 1, 0.5)]:
            with self.assertRaises(ValueError):
                core.temporal_neighborhood(*args)

    def test_half_open_selection_and_overwrite_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            kwargs = dict(metadata={}, mode="mass_preserve", alpha=1.0, radius=0,
                          time_offset=0, start_frame=0, end_frame=0,
                          block_start=2, block_end=4, step_start=1, step_end=3,
                          run_id="test", audit_dir=directory, num_blocks=5)
            state = core.RouterState(**kwargs)
            for step, block, expected in [(0, 2, False), (1, 1, False), (1, 2, True),
                                          (2, 3, True), (2, 4, False), (3, 2, False)]:
                state.forward_index = step
                self.assertEqual(state.selected(block), expected)
            with self.assertRaises(FileExistsError):
                core.RouterState(**kwargs)


@unittest.skipIf(torch is None, "torch not available in this interpreter")
class AlgebraTests(unittest.TestCase):
    def setUp(self):
        generator = torch.Generator().manual_seed(261016)
        self.q, self.k, self.v = [torch.randn(1, 2, 29, 8, generator=generator)
                                for _ in range(3)]
        # 3 prefix tokens, four reference frames x3 tokens, 2 other tokens,
        # four target frames x3 tokens. Target frames1..2 selected.
        self.plan = {"reference_video_segment": [3, 15],
                     "query_interval_half_open": [20, 26],
                     "latent_interval_half_open": [1, 3], "frame_rows": 3}

    def call(self, **kwargs):
        return core.route_attention(self.q, self.k, self.v, 2, self.plan,
                                    attention=dense_attention, **kwargs)

    def explicit(self, mode, radius=0, time_offset=0, alpha=1.0):
        logits = self.q @ self.k.transpose(-1, -2) / math.sqrt(self.q.shape[-1])
        probabilities = logits.softmax(-1)
        expected = probabilities.clone()
        for qi in range(20, 26):
            reference_frame = 1 + (qi - 20) // 3
            lo, hi = core.temporal_neighborhood(reference_frame, 4, radius, time_offset)
            a, b = 3 + 3 * lo, 3 + 3 * hi
            if mode == "mass_preserve":
                ref_mass = probabilities[:, :, qi, 3:15].sum(-1, keepdim=True)
                expected[:, :, qi, 3:15] = 0
                expected[:, :, qi, a:b] = ref_mass * logits[:, :, qi, a:b].softmax(-1)
            elif mode == "hard_route":
                row = logits[:, :, qi].clone()
                row[:, :, 3:a] = -float("inf")
                row[:, :, b:15] = -float("inf")
                expected[:, :, qi] = row.softmax(-1)
            else:
                raise ValueError(mode)
        mixed = probabilities + alpha * (expected - probabilities)
        return (mixed @ self.v).transpose(1, 2).reshape(1, 29, 16), mixed, probabilities

    def test_mass_preserve_matches_explicit_probability_redistribution(self):
        for radius in (0, 1):
            for offset in (0, -4, 4):
                for alpha in (0.3, 1.0):
                    with self.subTest(radius=radius, offset=offset, alpha=alpha):
                        expected, p, original = self.explicit("mass_preserve", radius, offset, alpha)
                        actual = self.call(mode="mass_preserve", radius=radius, time_offset=offset, alpha=alpha)
                        torch.testing.assert_close(actual, expected, atol=1e-6, rtol=3e-6)
                        torch.testing.assert_close(p[:, :, 20:26, 3:15].sum(-1),
                                                   original[:, :, 20:26, 3:15].sum(-1))
                        self.assertTrue(torch.equal(p[:, :, 20:26, :3], original[:, :, 20:26, :3]))
                        self.assertTrue(torch.equal(p[:, :, 20:26, 15:], original[:, :, 20:26, 15:]))

    def test_hard_route_matches_explicit_dense_key_mask(self):
        for radius in (0, 1):
            for offset in (0, -4, 4):
                for alpha in (0.3, 1.0):
                    with self.subTest(radius=radius, offset=offset, alpha=alpha):
                        expected, _, _ = self.explicit("hard_route", radius, offset, alpha)
                        actual = self.call(mode="hard_route", radius=radius, time_offset=offset, alpha=alpha)
                        torch.testing.assert_close(actual, expected, atol=5e-7, rtol=4e-6)

    def test_untargeted_queries_are_bitwise_native(self):
        baseline = self.call(mode="native")
        for mode in ("mass_preserve", "hard_route"):
            actual = self.call(mode=mode)
            self.assertTrue(torch.equal(actual[:, :20], baseline[:, :20]))
            self.assertTrue(torch.equal(actual[:, 26:], baseline[:, 26:]))

    def test_alpha_zero_and_diagnostic_are_bitwise_native(self):
        baseline = self.call(mode="native")
        for mode in ("mass_preserve", "hard_route"):
            self.assertTrue(torch.equal(self.call(mode=mode, alpha=0), baseline))
        stats = []
        self.assertTrue(torch.equal(self.call(mode="diagnostic", diagnostics=stats), baseline))
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0].shape, (5,))
        self.assertEqual(float(stats[0][2]), 0.0)
        self.assertEqual(float(stats[0][3]), 1.0)

    def test_large_logit_common_offset_is_stable(self):
        # Direct backend wrapper adds a shared LSE offset; outputs do not change.
        def shifted(q, k, v):
            out, lse = dense_attention(q, k, v)
            return out, lse + 500
        for mode in ("mass_preserve", "hard_route"):
            actual = core.route_attention(self.q, self.k, self.v, 2, self.plan,
                                           mode=mode, attention=shifted)
            torch.testing.assert_close(actual, self.call(mode=mode), atol=2e-5, rtol=2e-4)

    def test_native_backend_is_called_once_with_original_tensors(self):
        calls = []
        def recorded(q, k, v):
            calls.append((q, k, v))
            return dense_attention(q, k, v)
        core.route_attention(self.q, self.k, self.v, 2, self.plan, mode="native", attention=recorded)
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][0], self.q)
        self.assertIs(calls[0][1], self.k)
        self.assertIs(calls[0][2], self.v)

    def test_hard_route_near_unit_ref_mass_with_quantized_output(self):
        # A dominant wrong-time key makes P(reference) approach1 while the
        # retained same-time keys remain weak. Subtraction would be unstable.
        self.q.fill_(0)
        self.q[..., 0] = 4
        self.k.fill_(0)
        self.k[:, :, 3:6, 0] = 10
        expected, _, original = self.explicit("hard_route")
        self.assertGreater(float(original[:, :, 20:26, 3:15].sum(-1).min()), 0.999)
        def quantized(q, k, v):
            out, lse = dense_attention(q, k, v)
            return out.to(torch.bfloat16).to(q.dtype), lse
        actual = core.route_attention(self.q, self.k, self.v, 2, self.plan,
                                      mode="hard_route", attention=quantized)
        torch.testing.assert_close(actual, expected, atol=0.002, rtol=0.02)

    def test_readout_records_normalized_frame_probabilities(self):
        readout = core.temporal_readout(self.q, self.k, self.plan)
        self.assertEqual(len(readout["query_records"]), 2)
        for t, row in zip((1, 2), readout["query_records"]):
            self.assertEqual(row["query_latent_bin"], t)
            self.assertEqual(len(row["p_ref_frame"]), 4)
            self.assertAlmostEqual(sum(row["p_ref_frame"]), 1.0, places=6)
            self.assertEqual(row["same_bin_mass"], row["p_ref_frame"][t])


@unittest.skipIf(torch is None or os.environ.get("H3_ROUTER_TEST_DEVICE") != "cuda",
                 "set H3_ROUTER_TEST_DEVICE=cuda for GPU Flash toy tests")
class CUDAFlashTests(unittest.TestCase):
    def setUp(self):
        generator = torch.Generator().manual_seed(261016)
        self.q, self.k, self.v = [torch.randn(1, 4, 77, 64, generator=generator).to("cuda", torch.bfloat16)
                                for _ in range(3)]
        self.plan = {"reference_video_segment": [5, 37],
                     "query_interval_half_open": [53, 69],
                     "latent_interval_half_open": [1, 3], "frame_rows": 8}

    def test_flash_output_lse_matches_float32_dense(self):
        out, lse = core.flash_attention_lse(self.q, self.k, self.v)
        expected, expected_lse = dense_attention(self.q.float(), self.k.float(), self.v.float())
        torch.testing.assert_close(out.float(), expected, atol=0.008, rtol=0.04)
        torch.testing.assert_close(lse, expected_lse, atol=0.0001, rtol=0.0001)

    def test_native_flash_matches_native_sdpa(self):
        flash = core.route_attention(self.q, self.k, self.v, 4, self.plan, mode="native")
        sdpa = torch.nn.functional.scaled_dot_product_attention(self.q, self.k, self.v)
        sdpa = sdpa.transpose(1, 2).reshape(1, 77, 256)
        torch.testing.assert_close(flash, sdpa, atol=0, rtol=0)

    def test_flash_hard_route_near_unit_reference_mass(self):
        self.q.fill_(0)
        self.q[..., 0] = 4
        self.k.fill_(0)
        self.k[:, :, 5:13, 0] = 32
        # Event target frames1/2 exclude the dominant reference frame0.
        stats = []
        actual = core.route_attention(self.q, self.k, self.v, 4, self.plan,
                                      mode="hard_route", diagnostics=stats)
        expected = core.route_attention(self.q.float(), self.k.float(), self.v.float(), 4,
                                        self.plan, mode="hard_route", attention=dense_attention)
        self.assertGreater(float(stats[0][0]), 0.999)
        self.assertTrue(bool(torch.isfinite(actual).all()))
        torch.testing.assert_close(actual.float(), expected, atol=0.008, rtol=0.05)

    def test_flash_routing_matches_float32_dense_and_preserves_other_queries(self):
        baseline = core.route_attention(self.q, self.k, self.v, 4, self.plan, mode="native")
        for mode in ("mass_preserve", "hard_route"):
            for radius, offset in ((0, 0), (1, 0), (1, 4), (0, -4)):
                with self.subTest(mode=mode, radius=radius, offset=offset):
                    actual = core.route_attention(self.q, self.k, self.v, 4, self.plan,
                                                  mode=mode, radius=radius, time_offset=offset)
                    expected = core.route_attention(self.q.float(), self.k.float(), self.v.float(), 4,
                                                    self.plan, mode=mode, radius=radius,
                                                    time_offset=offset, attention=dense_attention)
                    torch.testing.assert_close(actual.float(), expected, atol=0.012, rtol=0.05)
                    self.assertTrue(torch.equal(actual[:, :53], baseline[:, :53]))
                    self.assertTrue(torch.equal(actual[:, 69:], baseline[:, 69:]))
            zero = core.route_attention(self.q, self.k, self.v, 4, self.plan, mode=mode, alpha=0)
            self.assertTrue(torch.equal(zero, baseline))


if __name__ == "__main__":
    unittest.main()
