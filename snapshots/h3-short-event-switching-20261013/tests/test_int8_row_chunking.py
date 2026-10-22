import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import torch


spec = importlib.util.spec_from_file_location("int8_row_chunking", Path(__file__).resolve().parents[1] / "scripts/int8_row_chunking.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MathStub:
    """CPU analogue of original row-local activation/rotation/int8 semantics."""
    def __init__(self):
        self.calls = []

    def __call__(self, x, weight, weight_scale, bias=None, out_dtype=torch.bfloat16,
                 convrot=False, convrot_groupsize=256, input_act=None):
        self.calls.append(dict(x=x, weight=weight, weight_scale=weight_scale, bias=bias,
                               out_dtype=out_dtype, convrot=convrot,
                               convrot_groupsize=convrot_groupsize, input_act=input_act))
        if input_act == "swiglu":
            gate, up = x.chunk(2, dim=-1)
            x = torch.nn.functional.silu(gate) * up
        elif input_act == "gelu_tanh":
            x = torch.nn.functional.gelu(x, approximate="tanh")
        elif input_act not in (None, "none"):
            raise ValueError(input_act)
        shape = x.shape
        x = x.reshape(-1, shape[-1])
        if convrot:
            if convrot_groupsize != 4 or x.shape[-1] % 4:
                raise ValueError("CPU fixture only supports group 4")
            h = torch.tensor([[1, 1, 1, -1], [1, 1, -1, 1], [1, -1, 1, 1], [-1, 1, 1, 1]], dtype=x.dtype) / 2
            x = (x.reshape(-1, x.shape[-1] // 4, 4) @ h).reshape(x.shape)
        scale = x.abs().amax(dim=1, keepdim=True).clamp_min(1e-30) / 127
        q = (x / scale).round().clamp(-128, 127).to(torch.int8)
        y = (q.float() @ weight.float().T) * (scale * weight_scale.reshape(1, -1))
        if bias is not None:
            y += bias
        return y.to(out_dtype).reshape(*shape[:-1], weight.shape[0])


class RowChunkTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(123)

    def args(self, x=None, n=6, k=8, scalar_scale=False):
        return dict(x=x if x is not None else torch.randn(2, 5, k),
                    weight=torch.randint(-8, 9, (n, k), dtype=torch.int8),
                    weight_scale=torch.rand(1 if scalar_scale else n, 1) + 0.1)

    def compare(self, arguments, limit=63):
        stub = MathStub()
        expected = stub(**arguments)
        stub.calls.clear()
        events = []
        wrapped = module.wrap_int8_linear(stub, index_limit=limit, event_callback=events.append)
        result = wrapped(**arguments)
        torch.testing.assert_close(result, expected, rtol=0, atol=0)
        self.assertEqual(result.device, expected.device)
        self.assertEqual(result.dtype, expected.dtype)
        return stub.calls, events, result

    def test_3d_rows_reshape_bias_per_channel_scale_and_dtype(self):
        arguments = self.args()
        arguments.update(bias=torch.randn(6), out_dtype=torch.float16)
        calls, events, result = self.compare(arguments, limit=31)
        self.assertEqual(result.shape, (2, 5, 6))
        self.assertEqual([c["x"].shape[0] for c in calls], [4, 4, 2])
        self.assertEqual(events[0]["chunks"], 3)
        for call in calls:
            for key in ("weight", "weight_scale", "bias"):
                self.assertIs(call[key], arguments[key])
            self.assertEqual(call["out_dtype"], torch.float16)

    def test_noncontiguous_leading_dimensions(self):
        x = torch.randn(2, 8, 5).transpose(1, 2)
        self.assertFalse(x.is_contiguous())
        calls, _, _ = self.compare(self.args(x=x), limit=31)
        self.assertTrue(all(call["x"].is_contiguous() for call in calls))

    def test_swiglu_convrot_and_scalar_scale_are_forwarded_once_per_chunk(self):
        arguments = self.args(x=torch.randn(2, 5, 16), scalar_scale=True)
        arguments.update(input_act="swiglu", convrot=True, convrot_groupsize=4,
                         bias=torch.randn(6), out_dtype=torch.float32)
        calls, _, _ = self.compare(arguments)
        self.assertEqual([c["x"].shape for c in calls], [(4, 16), (4, 16), (2, 16)])
        for call in calls:
            self.assertEqual(call["input_act"], "swiglu")
            self.assertIs(call["convrot"], True)
            self.assertEqual(call["convrot_groupsize"], 4)

    def test_gelu_activation_matches_original(self):
        arguments = self.args()
        arguments["input_act"] = "gelu_tanh"
        self.compare(arguments, limit=31)

    def test_below_threshold_preserves_original_input_and_shape(self):
        x = torch.randn(2, 8, 3).transpose(1, 2)
        arguments = self.args(x=x)
        stub = MathStub()
        wrapped = module.wrap_int8_linear(stub, index_limit=63)
        result = wrapped(arguments["x"], arguments["weight"], arguments["weight_scale"])
        self.assertEqual(result.shape, (2, 3, 6))
        self.assertEqual(len(stub.calls), 1)
        self.assertIs(stub.calls[0]["x"], x)
        self.assertFalse(stub.calls[0]["x"].is_contiguous())

    def test_exact_last_offset_boundary_does_not_chunk(self):
        calls, events, _ = self.compare(self.args(x=torch.randn(8, 8)), limit=63)
        self.assertEqual(len(calls), 1)
        self.assertEqual(events, [])

    def test_output_width_can_trigger_chunking_when_input_is_small(self):
        calls, events, _ = self.compare(self.args(x=torch.randn(5, 4), n=16, k=4), limit=63)
        self.assertEqual([c["x"].shape[0] for c in calls], [4, 1])
        self.assertEqual(events[0]["max_flat_offset"], 79)

    def test_max_rows_cap_and_positional_forwarding(self):
        args = self.args()
        stub = MathStub()
        wrapped = module.wrap_int8_linear(stub, index_limit=63, max_chunk_rows=3)
        wrapped(args["x"], args["weight"], args["weight_scale"], None, torch.float32, False, 4, None)
        self.assertEqual([c["x"].shape[0] for c in stub.calls], [3, 3, 3, 1])
        self.assertTrue(all(c["convrot_groupsize"] == 4 for c in stub.calls))

    def test_api_drift_and_unsafe_policy_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "API changed"):
            module.wrap_int8_linear(lambda x, weight: x)
        for kwargs in ({"max_chunk_rows": 16385}, {"index_limit": 1 << 31}, {"index_limit": -1}):
            with self.assertRaises(ValueError):
                module.wrap_int8_linear(MathStub(), **kwargs)
        wrapped = module.wrap_int8_linear(MathStub(), index_limit=3)
        with self.assertRaisesRegex(RuntimeError, "single INT8 linear row"):
            wrapped(**self.args())

    def test_registry_export_hook_idempotence_and_log(self):
        backend = ModuleType("comfy_kitchen.backends.triton")
        backend.int8_linear = original = MathStub()
        registry_module = ModuleType("comfy_kitchen.registry")
        registry_module.registry = SimpleNamespace(get_implementation=lambda name, backend=None: sys.modules["comfy_kitchen.backends.triton"].int8_linear)
        with tempfile.TemporaryDirectory() as td, patch.dict(sys.modules, {
            "comfy_kitchen.backends.triton": backend, "comfy_kitchen.registry": registry_module,
        }):
            log = Path(td) / "chunk.jsonl"
            record = module.install(log_path=log, index_limit=31)
            self.assertEqual(record["status"], "installed")
            self.assertIs(backend.int8_linear._h3_row_chunk_original, original)
            hooked = backend.int8_linear
            self.assertEqual(module.install(index_limit=31)["status"], "already_installed")
            self.assertIs(backend.int8_linear, hooked)
            with self.assertRaisesRegex(RuntimeError, "different policy"):
                module.install(index_limit=63)
            backend.int8_linear(**self.args())
            records = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(records[0]["status"], "installed")
            self.assertEqual(records[1]["event"], "int8_row_chunk")

    def test_registry_identity_mismatch_refuses_patch(self):
        original = MathStub()
        backend = ModuleType("comfy_kitchen.backends.triton")
        backend.int8_linear = original
        registry_module = ModuleType("comfy_kitchen.registry")
        registry_module.registry = SimpleNamespace(get_implementation=lambda *a, **k: MathStub())
        with patch.dict(sys.modules, {"comfy_kitchen.backends.triton": backend, "comfy_kitchen.registry": registry_module}):
            with self.assertRaisesRegex(RuntimeError, "differs"):
                module.install()
        self.assertIs(backend.int8_linear, original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
