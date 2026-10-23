"""CPU-only small-tensor oracles; no model, VAE, detector or CUDA work."""

import math
import unittest
from unittest import mock

import torch

from temporal_coverage_v2.attention import attach_h3_coverage, coverage_attention
from temporal_coverage_v2.routing import CoverageConfig, sampled_time_quality, solve_temporal_coverage


def dense_attention(q, k, v):
    logits = torch.matmul(q, k.transpose(-1, -2)) / math.sqrt(q.shape[-1])
    return logits.softmax(-1) @ v, logits.logsumexp(-1)


class CoverageTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(42)

    def assert_budgets(self, result, valid=None, tol=2.1e-4):
        self.assertTrue(result.applied, result.summary())
        p = result.probabilities
        target = torch.ones(p.shape[0], dtype=p.dtype) if valid is None else valid.to(p.dtype)
        self.assertTrue(torch.all(p >= 0))
        self.assertTrue(torch.all(p[~result.allowed] == 0))
        torch.testing.assert_close(p.sum(1), target, atol=tol, rtol=0)
        torch.testing.assert_close(p.sum(0), target, atol=tol, rtol=0)
        mask = target.bool()
        means = (p @ torch.arange(p.shape[0], dtype=p.dtype))[mask]
        self.assertTrue(bool(torch.all(means[1:] >= means[:-1] - 1e-6)))

    def test_shared_favorite_cannot_consume_every_output_bin(self):
        quality = torch.zeros(5, 5, dtype=torch.float64)
        quality[:, 2] = 8
        self.assertGreater(float(quality.softmax(-1).sum(0)[2]), 4.9)
        result = solve_temporal_coverage(quality, config=CoverageConfig(radius=4))
        self.assert_budgets(result)
        self.assertLessEqual(float(result.probabilities.sum(0).max()), 1.0002)

    def test_local_mask_and_clipped_boundaries(self):
        quality = torch.randn(7, 7, dtype=torch.float64)
        result = solve_temporal_coverage(quality, config=CoverageConfig(radius=1, iterations=512))
        self.assert_budgets(result)
        self.assertEqual(int(result.allowed[0].sum()), 2)
        self.assertEqual(int(result.allowed[-1].sum()), 2)
        self.assertEqual(int(result.allowed[3].sum()), 3)

    def test_reversed_assignment_contracts_to_ordered_means(self):
        quality = torch.eye(5, dtype=torch.float64).flip(1) * 4
        config = CoverageConfig(radius=4, temporal_penalty=0, minimum_mean_gap=0.1)
        result = solve_temporal_coverage(quality, config=config)
        self.assert_budgets(result)
        self.assertLess(result.transport_fraction, 1)
        means = result.probabilities @ torch.arange(5, dtype=torch.float64)
        self.assertGreaterEqual(float((means[1:] - means[:-1]).min()), 0.1 - 1e-10)

    def test_padding_ignored_on_both_axes_even_when_nan(self):
        valid = torch.tensor([True, False, True, True, False])
        quality = torch.randn(5, 5, dtype=torch.float64)
        quality[~(valid[:, None] & valid[None, :])] = torch.nan
        result = solve_temporal_coverage(quality, config=CoverageConfig(radius=4), valid_mask=valid)
        self.assert_budgets(result, valid)
        self.assertEqual(float(result.probabilities[~valid].sum()), 0)

    def test_zero_radius_identity(self):
        result = solve_temporal_coverage(torch.randn(4, 4), config=CoverageConfig(radius=0))
        self.assert_budgets(result)
        self.assertTrue(torch.equal(result.probabilities, torch.eye(4)))
        self.assertEqual(result.reason, "identity")

    def test_single_bin_identity(self):
        result = solve_temporal_coverage(torch.zeros(1, 1))
        self.assert_budgets(result)
        self.assertEqual(float(result.probabilities[0, 0]), 1)

    def test_custom_mask_preserves_holes(self):
        allowed = torch.ones(4, 4, dtype=torch.bool)
        allowed[0, 2] = allowed[2, 0] = False
        result = solve_temporal_coverage(torch.randn(4, 4), allowed_mask=allowed,
                                         config=CoverageConfig(radius=3, iterations=512))
        self.assert_budgets(result)
        self.assertEqual(float(result.probabilities[0, 2]), 0)

    def test_infeasible_support_returns_no_route(self):
        allowed = torch.ones(4, 4, dtype=torch.bool)
        allowed[:, 2] = False
        result = solve_temporal_coverage(torch.randn(4, 4), allowed_mask=allowed)
        self.assertFalse(result.applied)
        self.assertEqual(result.reason, "identity_anchor_infeasible")
        self.assertEqual(float(result.probabilities.sum()), 0)

    def test_no_valid_bins_returns_no_route(self):
        result = solve_temporal_coverage(torch.zeros(4, 4), valid_mask=torch.zeros(4, dtype=torch.bool))
        self.assertFalse(result.applied)
        self.assertEqual(result.reason, "no_valid_bins")

    def test_low_signal_returns_no_route(self):
        result = solve_temporal_coverage(torch.zeros(4, 4))
        self.assertFalse(result.applied)
        self.assertEqual(result.reason, "low_signal")

    def test_nonfinite_quality_returns_no_route(self):
        quality = torch.randn(4, 4)
        quality[1, 1] = torch.nan
        result = solve_temporal_coverage(quality)
        self.assertFalse(result.applied)
        self.assertEqual(result.reason, "nonfinite_quality")

    def test_failed_convergence_returns_no_route(self):
        result = solve_temporal_coverage(torch.randn(7, 7) * 2,
                                         config=CoverageConfig(radius=3, iterations=1, tolerance=1e-8))
        self.assertFalse(result.applied)
        self.assertEqual(result.reason, "not_converged")

    def test_invalid_contracts_raise(self):
        with self.assertRaises(ValueError):
            solve_temporal_coverage(torch.ones(3, 4))
        with self.assertRaises(ValueError):
            CoverageConfig(entropy=0)
        with self.assertRaises(ValueError):
            solve_temporal_coverage(torch.ones(4, 4), valid_mask=torch.ones(4))

    def test_streamed_quality_matches_dense_small_oracle(self):
        q = torch.randn(1, 3, 20, 4, dtype=torch.float64)
        k = torch.randn_like(q)
        quality = sampled_time_quality(q, k, 5, query_samples=5, head_samples=3, key_chunk=2)
        logits = q @ k.transpose(-1, -2) / 2
        expected = logits.softmax(-1).reshape(1, 3, 4, 5, 4, 5).sum(-1).mean((0, 1, 3))
        torch.testing.assert_close(quality.exp(), expected, atol=1e-12, rtol=1e-12)

    def test_quality_buffers_are_sampled_and_chunk_bounded(self):
        q, k = (torch.randn(1, 8, 80, 4) for _ in range(2))
        original = torch.matmul
        sizes = []

        def record(left, right):
            sizes.append((tuple(left.shape), tuple(right.shape)))
            return original(left, right)

        with mock.patch("torch.matmul", side_effect=record):
            sampled_time_quality(q, k, 20, query_samples=3, head_samples=2, key_chunk=7)
        self.assertTrue(sizes)
        self.assertTrue(all(a[0] <= 2 and a[1] <= 12 and b[-1] <= 7 for a, b in sizes))

    def test_realistic_bins_column_bias_converges(self):
        for n in (29,32):
            q=.325*torch.arange(n,dtype=torch.float64)[None,:].repeat(n,1)
            result=solve_temporal_coverage(q)
            self.assert_budgets(result)
            self.assertLessEqual(result.solver_iterations,64)
            self.assertGreater(result.solver_seconds,0)

    def test_random_realistic_matrices_converge(self):
        for n in (29,32,48):
            for seed in range(3):
                torch.manual_seed(seed)
                result=solve_temporal_coverage(.6*torch.randn(n,n))
                self.assert_budgets(result)

    def test_sharp_pathology_is_bounded_and_finite(self):
        n=32;q=torch.randn(n,n,dtype=torch.float64)*1000
        result=solve_temporal_coverage(q)
        self.assertTrue(torch.isfinite(result.probabilities).all())
        self.assertLessEqual(result.solver_iterations,64)
        if result.applied:self.assert_budgets(result)
        else:self.assertEqual(result.reason,"not_converged")

    def test_disconnected_diagonal_support(self):
        q=torch.randn(32,32);allowed=torch.eye(32,dtype=torch.bool)
        result=solve_temporal_coverage(q,allowed_mask=allowed,config=CoverageConfig(min_quality_span=0))
        self.assert_budgets(result)



class AdapterTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(4)
        self.q, self.k, self.v = (torch.randn(1, 2, 28, 3, dtype=torch.float64) for _ in range(3))
        self.plan = dict(seq_len=28, reference_video_segment=[2, 14],
                         target_video_segment=[16, 28], query_interval_half_open=[19, 28],
                         latent_interval_half_open=[1, 4], frame_rows=3)

    def call(self, **kwargs):
        return coverage_attention(self.q, self.k, self.v, 2, self.plan,
                                   attention=dense_attention, **kwargs)

    def packed(self, value):
        return value.transpose(1, 2).reshape(1, 28, 6)

    def explicit_probability_oracle(self, config, alpha):
        scores = self.q @ self.k.transpose(-1, -2) / math.sqrt(3)
        original = scores.softmax(-1)
        effective = original.clone()
        route = solve_temporal_coverage(sampled_time_quality(self.q[:, :, 19:28], self.k[:, :, 5:14], 3), config=config)
        self.assertTrue(route.applied, route.summary())
        # Match the frozen implementation's FP32 LSE mass recovery exactly.
        full_lse = scores.logsumexp(-1)
        ref_lse = scores[:, :, 19:28, 2:14].logsumexp(-1)
        mass = (ref_lse.float() - full_lse[:, :, 19:28].float()).clamp(max=0).exp().double()
        conditional = scores[:, :, 19:28, 2:14].softmax(-1)
        routed = torch.zeros_like(conditional)
        for out_t in range(3):
            for ref_t in range(3):
                selected = scores[:, :, 19 + out_t * 3:22 + out_t * 3, 5 + ref_t * 3:8 + ref_t * 3].softmax(-1)
                routed[:, :, out_t * 3:(out_t + 1) * 3, (ref_t + 1) * 3:(ref_t + 2) * 3] = route.probabilities[out_t, ref_t] * selected
        effective[:, :, 19:28, 2:14] += alpha * mass.unsqueeze(-1) * (routed - conditional)
        return original, effective, mass

    def test_disabled_and_zero_alpha_have_one_native_call(self):
        native = self.packed(dense_attention(self.q, self.k, self.v)[0])
        for options in (dict(enabled=False), dict(enabled=True, alpha=0)):
            counted = mock.Mock(side_effect=dense_attention)
            actual = coverage_attention(self.q, self.k, self.v, 2, self.plan,
                                        attention=counted, **options)
            self.assertTrue(torch.equal(actual, native))
            self.assertEqual(counted.call_count, 1)

    def test_factory_off_returns_original_without_import_or_audit(self):
        marker = object()
        self.assertIs(attach_h3_coverage(marker, None, core=None, enabled=False,
                                        start_frame=0, end_frame=1, run_id="unused", audit_dir="unused"), marker)

    def test_identity_matches_same_time_mass_preserving_formula(self):
        config = CoverageConfig(radius=0)
        _, expected, _ = self.explicit_probability_oracle(config, 0.8)
        actual = self.call(enabled=True, alpha=0.8, config=config)
        torch.testing.assert_close(actual, self.packed(expected @ self.v), atol=1e-12, rtol=1e-12)

    def test_routing_matches_probability_oracle_and_preserves_reference_mass(self):
        config = CoverageConfig(radius=2, iterations=512)
        original, effective, mass = self.explicit_probability_oracle(config, 0.7)
        diagnostics = {}
        actual = self.call(enabled=True, alpha=0.7, config=config, diagnostics=diagnostics)
        torch.testing.assert_close(actual, self.packed(effective @ self.v), atol=1e-12, rtol=1e-12)
        torch.testing.assert_close(effective.sum(-1), torch.ones_like(effective.sum(-1)), atol=1e-12, rtol=1e-12)
        torch.testing.assert_close(effective[:, :, :, 2:14].sum(-1), original[:, :, :, 2:14].sum(-1), atol=1e-12, rtol=1e-12)
        torch.testing.assert_close(diagnostics["reference_mass"].double(), mass, atol=0, rtol=0)
        self.assertTrue(torch.equal(effective[:, :, :19], original[:, :, :19]))
        self.assertTrue(torch.equal(effective[:, :, :, 14:], original[:, :, :, 14:]))
        self.assertLessEqual(diagnostics["attention_calls"], 2 + 2 * config.radius + 1)

    def test_weak_signal_falls_back_to_same_time_weak(self):
        self.q.zero_()
        diagnostics = {}
        actual=self.call(enabled=True,alpha=.25,diagnostics=diagnostics)
        expected=self.call(enabled=True,alpha=.25,config=CoverageConfig(radius=0))
        torch.testing.assert_close(actual,expected,atol=1e-12,rtol=1e-12)
        self.assertEqual(diagnostics["reason"],"same_time_fallback")
        self.assertEqual(diagnostics["fallback_reason"],"low_signal")
        self.assertFalse(diagnostics["routing_solved"])
        self.assertEqual(diagnostics["attention_calls"],3)

    def test_invalid_layout_rejected(self):
        self.plan["query_interval_half_open"] = [18, 28]
        with self.assertRaises(ValueError):
            self.call(enabled=True)

    def test_input_tensors_are_unmodified(self):
        saved = [value.clone() for value in (self.q, self.k, self.v)]
        self.call(enabled=True, config=CoverageConfig(radius=0))
        self.assertTrue(all(torch.equal(a, b) for a, b in zip(saved, (self.q, self.k, self.v))))


if __name__ == "__main__":
    unittest.main(verbosity=2)
