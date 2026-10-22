"""CPU-only dense oracle tests. Dense attention exists ONLY in this test file.

Run from innovation with an existing PyTorch interpreter:
  CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    python -m unittest direction_runtime.test_runtime -v
"""
from dataclasses import replace
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from .frozen import load_frozen
from .nodes import (DirectionBlockPatch, DirectionState,
                    H3DirectionGatedSchedule, parse_layers)
from .runtime import (ComputeTrace, DirectionConfig, direction_attention, fixed_spatial_indices,
                      probe_probabilities, serialize_report, vectorized_gate)


def dense_attention(q, k, v):
    assert q.device.type == "cpu", "This oracle must never run on CUDA"
    logits = q @ k.transpose(-1, -2) / math.sqrt(q.shape[-1])
    return logits.softmax(-1) @ v, logits.logsumexp(-1)


def fixture(temporal=4, frame_rows=4, heads=3, dim=5, lo=1, hi=3):
    torch.manual_seed(91)
    ra = 3  # text plus character image, outside reference-video keys
    rb = ra + temporal * frame_rows
    ta, tb = rb + 2, rb + 2 + temporal * frame_rows  # audio separates video groups
    n = tb + 1
    q, k, v = [torch.randn(1, heads, n, dim, dtype=torch.float64) for _ in range(3)]
    plan = dict(seq_len=n, query_interval_half_open=[ta + lo * frame_rows, ta + hi * frame_rows],
                reference_video_segment=[ra, rb], target_video_segment=[ta, tb],
                latent_interval_half_open=[lo, hi], frame_rows=frame_rows)
    return q, k, v, plan


def flat(x):
    return x.transpose(1, 2).reshape(1, x.shape[-2], -1)


class GateTests(unittest.TestCase):
    def test_vectorized_matches_pure_python_prototype(self):
        path = Path(__file__).resolve().parent.parent / "direction_gate.py"
        spec = importlib.util.spec_from_file_location("_direction_scalar_oracle", path)
        import sys
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        ds = [(1., 0.), (-1., 0.), (0., 1.), (1., 1.), (0., 0.), (1e-7, 0.), (math.nan, 0.)]
        ps = [(1., 0., 0.), (0., 1., 0.), (1., 1., 1.), (0., 0., 1.), (-1., 0., 0.)]
        cases = [(d, p) for d in ds for p in ps]
        d = torch.tensor([a for a, _ in cases], dtype=torch.float64)
        p = torch.tensor([b for _, b in cases], dtype=torch.float64)
        before = torch.zeros_like(d)
        after = torch.tensor([[2., 0.]] * len(cases), dtype=torch.float64)
        result = vectorized_gate(d, before, after, p, torch.tensor(1), torch.tensor(0), torch.tensor(2), DirectionConfig())
        for i, (dv, pv) in enumerate(cases):
            expected = module.direction_gate(dv, (0., 0.), (2., 0.), pv, 1, previous_bin=0, next_bin=2)
            self.assertAlmostEqual(result["gate"][i].item(), expected.gate, places=12)
            from .runtime import REASONS
            self.assertEqual(REASONS[result["reason"][i]], expected.reason)

    def test_small_valid_norm_does_not_shrink_cosine_by_epsilon(self):
        d = torch.tensor([[1e-7]], dtype=torch.float64)
        result = vectorized_gate(d, torch.zeros_like(d), torch.tensor([[2e-6]], dtype=torch.float64),
                                 torch.tensor([[1., 0., 0.]], dtype=torch.float64),
                                 torch.tensor(1), torch.tensor(0), torch.tensor(2), DirectionConfig())
        self.assertEqual(result["gate"].item(), 1.)

    def test_invalid_configuration(self):
        for values in ({"alpha": -1}, {"alpha": math.nan}, {"key_chunk": 0},
                       {"min_concentration": 2}, {"min_tangent_norm": -1}):
            with self.assertRaises(ValueError):
                DirectionConfig(**values)


class AttentionTests(unittest.TestCase):
    def setUp(self):
        self.config = DirectionConfig(min_concentration=0, min_routing_offset=0,
                                      query_chunk=2, key_chunk=2, record_cuda_timing=False)

    def run_route(self, q, k, v, plan, **kwargs):
        reports = []
        result = direction_attention(q, k, v, q.shape[1], plan, attention=dense_attention,
                                     config=kwargs.pop("config", self.config), diagnostics=reports, **kwargs)
        return result, reports[0]

    def test_alpha_zero_and_native_are_exact_identity_with_one_call(self):
        q, k, v, plan = fixture()
        expected = flat(dense_attention(q, k, v)[0])
        for kwargs in ({"config": replace(self.config, alpha=0)}, {"mode": "native"}):
            actual, report = self.run_route(q, k, v, plan, **kwargs)
            self.assertTrue(torch.equal(actual, expected))
            self.assertEqual(report["trace"].counts, {"full": 1})
            self.assertEqual(report["trace"].logits_matmul_calls, 0)

    def test_constant_reference_values_are_identity(self):
        q, k, v, plan = fixture()
        ra, rb = plan["reference_video_segment"]
        v[:, :, ra:rb] = 2.0
        actual, report = self.run_route(q, k, v, plan)
        expected = flat(dense_attention(q, k, v)[0])
        torch.testing.assert_close(actual, expected, rtol=0, atol=1e-14)
        self.assertTrue(torch.equal(report["gate_per_head_bin"], torch.zeros_like(report["gate_per_head_bin"])))

    def test_uniform_mode_matches_frozen_mass_preserve(self):
        q, k, v, plan = fixture()
        actual, report = self.run_route(q, k, v, plan, mode="mass_preserve")
        def flash_contract_oracle(q, k, v):
            output, lse = dense_attention(q, k, v)
            return output, lse.float()
        expected = load_frozen().core.route_attention(q, k, v, q.shape[1], plan,
                                                     mode="mass_preserve", alpha=self.config.alpha,
                                                     attention=flash_contract_oracle)
        # Frozen implementation intentionally accumulates in fp32, including fp64 tests.
        torch.testing.assert_close(actual, expected, rtol=2e-6, atol=2e-7)
        self.assertEqual(report["trace"].counts, {"full": 1, "reference": 1, "aligned": 1})

    def test_dense_probability_oracle_preserves_mass_and_nonreference_weights(self):
        q, k, v, plan = fixture()
        actual, report = self.run_route(q, k, v, plan)
        qa, qb = plan["query_interval_half_open"]
        ra, rb = plan["reference_video_segment"]
        lo, hi = plan["latent_interval_half_open"]
        f = plan["frame_rows"]
        probabilities = (q @ k.transpose(-1, -2) / math.sqrt(q.shape[-1])).softmax(-1)
        changed_p = probabilities.clone()
        a = report["alpha_per_head_bin"]
        for h in range(q.shape[1]):
            for local_t, t in enumerate(range(lo, hi)):
                for row in range(f):
                    qi = qa + local_t * f + row
                    mass = probabilities[0, h, qi, ra:rb].sum()
                    same_logits = q[0, h, qi] @ k[0, h, ra + t * f:ra + (t + 1) * f].T / math.sqrt(q.shape[-1])
                    changed_p[0, h, qi, ra:rb] *= 1 - a[h, local_t]
                    changed_p[0, h, qi, ra + t * f:ra + (t + 1) * f] += a[h, local_t] * mass * same_logits.softmax(-1)
        self.assertTrue((a > 0).any(), "fixture must exercise an active correction")
        torch.testing.assert_close(changed_p[:, :, :, ra:rb].sum(-1), probabilities[:, :, :, ra:rb].sum(-1), rtol=0, atol=1e-15)
        self.assertTrue(torch.equal(changed_p[:, :, :, :ra], probabilities[:, :, :, :ra]))
        self.assertTrue(torch.equal(changed_p[:, :, :, rb:], probabilities[:, :, :, rb:]))
        torch.testing.assert_close(changed_p.sum(-1), torch.ones_like(changed_p.sum(-1)), rtol=0, atol=1e-15)
        torch.testing.assert_close(actual, flat(changed_p @ v), rtol=1e-12, atol=1e-12)
        native = flat(probabilities @ v)
        self.assertTrue(torch.equal(actual[:, :qa], native[:, :qa]))
        self.assertTrue(torch.equal(actual[:, qb:], native[:, qb:]))

    def test_chunked_probe_distribution_matches_dense_and_is_bounded(self):
        q, k, _, plan = fixture(frame_rows=7)
        config = replace(self.config, query_chunk=2, key_chunk=3)
        ra, rb = plan["reference_video_segment"]
        probe = q[:, :, :9]
        trace = ComputeTrace(dense_attention, config, q.device)
        actual = probe_probabilities(probe, k[:, :, ra:rb], 7, config, trace)
        logits = probe @ k[:, :, ra:rb].transpose(-1, -2) / math.sqrt(q.shape[-1])
        expected = logits.reshape(1, q.shape[1], 9, 4, 7).logsumexp(-1).softmax(-1)
        torch.testing.assert_close(actual, expected, rtol=1e-12, atol=1e-12)
        self.assertLessEqual(trace.max_logits_shape[-2], 2)
        self.assertLessEqual(trace.max_logits_shape[-1], 3)
        self.assertEqual(trace.logits_matmul_calls, 5 * 4 * 3)

    def test_both_boundaries_use_one_sided_neighbors(self):
        q, k, v, plan = fixture(lo=0, hi=4)
        actual, report = self.run_route(q, k, v, plan)
        self.assertTrue(torch.isfinite(actual).all())
        self.assertEqual(report["query_bins"], [0, 1, 2, 3])
        # Independently calculate per-probe gates using dense restricted attention.
        ra, rb = plan["reference_video_segment"]
        qa, _ = plan["query_interval_half_open"]
        spatial = fixed_spatial_indices(plan)
        for t in (0, 3):
            qi = [qa + 4 * t + s for s in spatial]
            qs = q[:, :, qi]
            full, lse = dense_attention(qs, k, v)
            ref, ref_lse = dense_attention(qs, k[:, :, ra:rb], v[:, :, ra:rb])
            same = dense_attention(qs, k[:, :, ra + 4 * t:ra + 4 * (t + 1)], v[:, :, ra + 4 * t:ra + 4 * (t + 1)])[0]
            prev_t, next_t = max(0, t - 1), min(3, t + 1)
            prev = dense_attention(qs, k[:, :, ra + 4 * prev_t:ra + 4 * (prev_t + 1)], v[:, :, ra + 4 * prev_t:ra + 4 * (prev_t + 1)])[0]
            nxt = dense_attention(qs, k[:, :, ra + 4 * next_t:ra + 4 * (next_t + 1)], v[:, :, ra + 4 * next_t:ra + 4 * (next_t + 1)])[0]
            logits = qs @ k[:, :, ra:rb].transpose(-1, -2) / math.sqrt(q.shape[-1])
            p = logits.reshape(1, 3, len(spatial), 4, 4).logsumexp(-1).softmax(-1)
            d = (ref_lse - lse).exp().unsqueeze(-1) * (same - ref)
            gate = vectorized_gate(d, prev, nxt, p, torch.tensor(t), torch.tensor(prev_t), torch.tensor(next_t), self.config)["gate"].mean(-1)[0]
            torch.testing.assert_close(report["gate_per_head_bin"][:, t], gate, rtol=1e-12, atol=1e-12)

    def test_one_reference_bin_skips_extra_calls(self):
        q, k, v, plan = fixture(temporal=1, lo=0, hi=1)
        actual, report = self.run_route(q, k, v, plan)
        self.assertTrue(torch.equal(actual, flat(dense_attention(q, k, v)[0])))
        self.assertEqual(report["skip_reason"], "insufficient_reference_bins")
        self.assertEqual(report["trace"].counts, {"full": 1})

    def test_report_counts_and_energy_are_serializable(self):
        q, k, v, plan = fixture()
        actual, report = self.run_route(q, k, v, plan)
        serialized = serialize_report(report)
        json.dumps(serialized, allow_nan=False)
        self.assertEqual(serialized["compute"]["attention_call_total"], 5)
        self.assertEqual(serialized["compute"]["attention_calls"]["probe_previous"], 1)
        self.assertEqual(serialized["compute"]["attention_calls"]["probe_next"], 1)
        native = flat(dense_attention(q, k, v)[0])
        self.assertAlmostEqual(serialized["applied_correction_energy"], (actual - native).square().sum().item(), places=12)
        self.assertLessEqual(serialized["applied_correction_energy"], self.config.alpha ** 2 * serialized["native_correction_energy"] + 1e-12)

    def test_fp32_and_bfloat16_cpu_inputs_remain_finite(self):
        for dtype in (torch.float32, torch.bfloat16):
            q, k, v, plan = fixture()
            q, k, v = (x.to(dtype) for x in (q, k, v))
            actual, report = self.run_route(q, k, v, plan)
            self.assertEqual(actual.dtype, dtype)
            self.assertTrue(torch.isfinite(actual).all())
            self.assertTrue((report["gate_per_head_bin"] >= 0).all())
            self.assertTrue((report["gate_per_head_bin"] <= 1).all())

    def test_spatial_grid_is_fixed_by_geometry(self):
        plan = {"frame_rows": 16, "signature": [2, 4, 8, 8, 0]}
        self.assertEqual(fixed_spatial_indices(plan), [5, 7, 13, 15])

    def test_invalid_query_range_is_rejected_before_attention(self):
        q, k, v, plan = fixture()
        plan["query_interval_half_open"] = list(plan["reference_video_segment"])
        with self.assertRaises(ValueError):
            self.run_route(q, k, v, plan)


class AdapterTests(unittest.TestCase):
    def test_layer_selection_is_explicit_and_schedule_bounded(self):
        self.assertEqual(parse_layers("0,2-4,4"), (0, 2, 3, 4))
        self.assertEqual(parse_layers("none"), ())
        self.assertEqual(len(parse_layers("all")), 50)
        for bad in ("-1", "50", "4-2", "x", "1,"):
            with self.assertRaises(ValueError):
                parse_layers(bad)
        with tempfile.TemporaryDirectory() as directory:
            state = DirectionState({}, mode="direction_gated", config=DirectionConfig(),
                                   selected_layers=(1, 3), enabled=True, start_frame=0, end_frame=4,
                                   schedule="early", run_id="test", audit_dir=directory)
            state.forward_index = 2
            self.assertTrue(state.selected(1))
            self.assertFalse(state.selected(2))
            state.forward_index = 9
            self.assertFalse(state.selected(1))
            state.forward_index = 2
            state.enabled = False
            self.assertFalse(state.selected(1))

    def test_patch_boundary_and_audit_with_fake_block_cpu(self):
        q, k, v, plan = fixture()
        layout = object()
        with tempfile.TemporaryDirectory() as directory:
            state = DirectionState({}, mode="direction_gated", config=DirectionConfig(record_cuda_timing=False),
                                   selected_layers=(0,), enabled=True, start_frame=0, end_frame=4,
                                   schedule="global_weak", run_id="adapter", audit_dir=directory,
                                   num_blocks=1)
            state.plan_for = lambda _: plan
            block_patch = DirectionBlockPatch(state, 0)
            def attention_pytorch(*args, **kwargs):
                raise AssertionError("native entry only identifies the attention API")
            def original_block(args):
                override = args["transformer_options"]["optimized_attention_override"]
                return override(attention_pytorch, q, k, v, q.shape[1], skip_reshape=True)
            with patch.object(load_frozen().core, "flash_attention_lse", dense_attention):
                actual = block_patch({"layout": layout, "transformer_options": {
                    "block_index": 0, "minimax_h3_layout": layout,
                    "sample_sigmas": torch.tensor([1., 0.])}}, {"original_block": original_block})
            self.assertEqual(actual.shape, (1, q.shape[-2], q.shape[1] * q.shape[-1]))
            audit = json.loads((Path(directory) / "adapter.json").read_text())
            self.assertEqual(audit["completed_forward_calls"], 1)
            self.assertEqual(audit["compute_call_totals"]["probe_next"], 1)
            self.assertEqual(audit["calls_by_block"], [1])
            self.assertEqual(audit["selected_layers"], [0])
            self.assertEqual(audit["full_dit_forward_calls_added"], 0)

    def test_node_schema_has_switches(self):
        inputs = H3DirectionGatedSchedule.INPUT_TYPES()["required"]
        for field in ("enabled", "mode", "schedule", "selected_layers", "alpha"):
            self.assertIn(field, inputs)


if __name__ == "__main__":
    torch.set_num_threads(1)
    unittest.main()
