"""Run with stdlib unittest; torch numerical checks run when torch is installed."""

import importlib.util
import math
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("h3_event_core", ROOT / "extensions/H3EventEmphasis/core.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
try:
    import torch
except ImportError:
    torch = None


def tensor_shape(*shape):
    return SimpleNamespace(shape=shape)


def positive():
    return [[tensor_shape(1, 10, 5376), {"minimax_refs": [
        {"kind": "image", "latent_h": 62, "latent_w": 62,
         "latent": tensor_shape(1, 24, 1, 62, 62)},
        {"kind": "video", "latent_t": 42, "latent_h": 46, "latent_w": 82,
         "ref_audio_t": 0, "latent": tensor_shape(1, 24, 42, 46, 82)},
    ]}]]


def layout():
    return SimpleNamespace(signature=(10, 42, 46, 82, 235), seq_len=80653,
                           segments=[(0, 10, "text"), (10, 971, "ref_img"),
                                     (971, 40577, "ref_img"), (40577, 41047, "audio"),
                                     (41047, 80653, "video")])


class MetadataTests(unittest.TestCase):
    def test_positional_frame_mapping(self):
        self.assertEqual(sum(core.frame_spans(42)), 141)
        self.assertEqual(core.event_latent_range(39, 44, 42), (12, 14))
        self.assertEqual(core.event_latent_range(41, 42, 42), (12, 13))
        self.assertEqual(core.event_latent_range(0, 0, 42), (0, 1))
        self.assertEqual(core.event_latent_range(140, 140, 42), (41, 42))

    def test_bad_frame_intervals(self):
        for a, b in [(-1, 0), (44, 39), (140, 141), (39.0, 44)]:
            with self.assertRaises(ValueError):
                core.event_latent_range(a, b, 42)

    def test_reference_video_selected_not_image(self):
        plan = core.validate_layout(core.conditioning_metadata(positive()), layout(), 39, 44)
        self.assertEqual(plan["reference_index"], 1)
        self.assertEqual(plan["reference_image_segments"], [[10, 971]])
        self.assertEqual(plan["key_interval_half_open"], [12287, 14173])
        self.assertEqual(plan["query_interval_half_open"], [52363, 54249])
        self.assertEqual(plan["position_bin_coverage_inclusive"], [39, 46])
        self.assertEqual(plan["key_first_time_coordinate"], 76.0)
        self.assertEqual(plan["query_first_time_coordinate"], 311.0)

    def test_bad_latent_metadata_rejected(self):
        p = positive()
        p[0][1]["minimax_refs"][1]["latent_t"] = 41
        with self.assertRaises(ValueError):
            core.conditioning_metadata(p)

    def test_ambiguous_reference_videos_rejected(self):
        p = positive()
        p[0][1]["minimax_refs"].append(p[0][1]["minimax_refs"][1])
        with self.assertRaises(ValueError):
            core.conditioning_metadata(p)

    def test_packed_shape_or_segment_mismatch_rejected(self):
        for wrong in ("signature", "segments", "seq_len"):
            current = layout()
            if wrong == "signature":
                current.signature = (11, 42, 46, 82, 235)
            elif wrong == "segments":
                current.segments[1] = (10, 971, "video")
            else:
                current.seq_len += 1
            with self.assertRaises(ValueError):
                core.validate_layout(core.conditioning_metadata(positive()), current, 39, 44)

    def test_factor_one_passes_native_objects_and_result_exactly(self):
        q, k, v, result = object(), object(), object(), object()
        calls = []
        def native(*args, **kwargs):
            calls.append((args, kwargs))
            return result
        actual = core.duplicate_event_attention(native, q, k, v, 56, 1, (0, 1), (0, 1),
                                               mask=None, skip_reshape=True)
        self.assertIs(actual, result)
        self.assertEqual(calls, [((q, k, v, 56), {"mask": None, "skip_reshape": True})])

    def test_scalar_softmax_duplication_equals_log_two(self):
        logits, values, selected = [0.3, -0.4, 1.2, 0.0], [2.0, -1.0, 0.4, 3.0], (1, 3)
        def attention(xs, vs):
            es = [math.exp(x) for x in xs]
            return sum(e * v for e, v in zip(es, vs)) / sum(es)
        duplicated = attention(logits + [logits[i] for i in selected],
                               values + [values[i] for i in selected])
        biased = attention([x + (math.log(2) if i in selected else 0) for i, x in enumerate(logits)], values)
        self.assertAlmostEqual(duplicated, biased, places=14)

    def test_factor_one_block_hook_is_exact_native_and_counts_forwards(self):
        current = layout()
        class Positions:
            shape = (current.seq_len, 3)
            def __getitem__(self, key):
                return {(12287, 0): 76.0, (52363, 0): 311.0}[key]
        current.position_ids = Positions()
        with tempfile.TemporaryDirectory() as directory:
            state = core.EventState(core.conditioning_metadata(positive()), 1, 39, 44,
                                    "test", directory, num_blocks=2)
            for forward in range(2):
                for block in range(2):
                    options = {"block_index": block, "minimax_h3_layout": current}
                    args = {"layout": current, "transformer_options": options}
                    expected = object()
                    def native(received):
                        self.assertIs(received, args)
                        self.assertIs(received["transformer_options"], options)
                        self.assertNotIn("optimized_attention_override", options)
                        return expected
                    actual = core.EventBlockPatch(state, block)(args, {"original_block": native})
                    self.assertIs(actual, expected)
            self.assertEqual(state.audit["calls_by_block"], [2, 2])
            self.assertEqual(state.audit["calls_by_forward"], [2, 2])
            self.assertEqual(state.audit["completed_forward_calls"], 2)
            self.assertEqual(state.audit["native_override_calls"], 0)
            self.assertTrue(state.path.is_file())
            with self.assertRaises(FileExistsError):
                core.EventState(state.metadata, 1, 39, 44, "test", directory, num_blocks=2)


@unittest.skipIf(torch is None, "torch unavailable; run these checks in existing ComfyUI environment")
class TorchAttentionTests(unittest.TestCase):
    def setUp(self):
        generator = torch.Generator().manual_seed(21013)
        self.device = os.environ.get("H3_EVENT_TEST_DEVICE", "cpu")
        self.dtype = torch.float64 if self.device == "cpu" else torch.bfloat16
        self.tolerance = 1e-12 if self.device == "cpu" else 2e-2
        self.q, self.k, self.v = [torch.randn(1, 2, 17, 8, generator=generator, dtype=torch.float64).to(self.device, self.dtype)
                                for _ in range(3)]
        self.calls = []

    def native(self, q, k, v, heads, mask=None, skip_reshape=True, **kwargs):
        self.calls.append((q.shape[-2], k.shape[-2], mask))
        out = torch.nn.functional.scaled_dot_product_attention(q, k, v, attn_mask=mask)
        return out.transpose(1, 2).reshape(1, q.shape[-2], heads * q.shape[-1])

    def test_duplicate_equivalence_and_query_isolation(self):
        baseline = self.native(self.q, self.k, self.v, 2)
        self.calls.clear()
        actual = core.duplicate_event_attention(self.native, self.q, self.k, self.v, 2, 2,
                                               (3, 6), (10, 13), mask=None, skip_reshape=True)
        bias = torch.zeros(17, dtype=self.dtype, device=self.device)
        bias[3:6] = math.log(2)
        expected = self.native(self.q[:, :, 10:13], self.k, self.v, 2, mask=bias[None, None, None, :])
        torch.testing.assert_close(actual[:, 10:13], expected, atol=self.tolerance, rtol=self.tolerance)
        self.assertTrue(torch.equal(actual[:, :10], baseline[:, :10]))
        self.assertTrue(torch.equal(actual[:, 13:], baseline[:, 13:]))
        self.assertEqual(self.calls[:2], [(17, 17, None), (3, 20, None)])

    def test_factor_one_tensor_bitwise_identity(self):
        expected = self.native(self.q, self.k, self.v, 2)
        actual = core.duplicate_event_attention(self.native, self.q, self.k, self.v, 2, 1,
                                               (3, 6), (10, 13), mask=None, skip_reshape=True)
        self.assertTrue(torch.equal(expected, actual))

    def test_masked_path_rejected(self):
        with self.assertRaises(ValueError):
            core.duplicate_event_attention(self.native, self.q, self.k, self.v, 2, 2,
                                           (3, 6), (10, 13), mask=torch.ones(17), skip_reshape=True)

    def test_bounded_prefix_of_noncontiguous_event_window(self):
        tensor = torch.arange(2 * 3 * 11 * 5).reshape(2, 3, 11, 5)[:, :, 2:8, :]
        self.assertFalse(tensor.is_contiguous())
        for count in (1, 4, 9, 29, 31, 95, tensor.numel()):
            self.assertTrue(torch.equal(core._flat_prefix(tensor, count), tensor.flatten()[:count]))


if __name__ == "__main__":
    unittest.main()
