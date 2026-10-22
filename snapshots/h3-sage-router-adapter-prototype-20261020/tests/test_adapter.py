import math
import unittest

import torch

from adapter import SageAttentionLSE
from diagnostics import fp32_attention, make_case, mass_preserve
from validate_gpu import call_preserving_qkv


class AdapterTests(unittest.TestCase):
    def setUp(self):
        (self.q, self.k, self.v), self.ref, self.aligned = make_case(
            torch, "random", device="cpu", dtype=torch.float16
        )
        self.calls = []

    def exact_backend(self, q, k, v, **kwargs):
        self.calls.append((q, k, v, kwargs))
        out, lse = fp32_attention(*(x.transpose(1, 2) for x in (q, k, v)))
        return out.to(q.dtype).transpose(1, 2).contiguous(), lse

    def test_layout_options_and_natural_lse_are_preserved(self):
        out, lse = SageAttentionLSE(self.exact_backend)(self.q, self.k, self.v)
        expected, expected_lse = fp32_attention(self.q, self.k, self.v)
        self.assertTrue(torch.equal(out, expected.to(self.q.dtype)))
        self.assertTrue(torch.equal(lse, expected_lse))
        q, k, v, options = self.calls[0]
        self.assertEqual(q.shape, (2, 19, 3, 64))
        self.assertEqual(k.shape, (2, 131, 3, 64))
        self.assertTrue(all(x.is_contiguous() for x in (q, k, v)))
        self.assertEqual(options, {
            "tensor_layout": "NHD", "is_causal": False, "qk_quant_gran": "per_warp",
            "sm_scale": 0.125, "pv_accum_dtype": "fp32", "smooth_k": True,
            "smooth_v": False, "return_lse": True,
        })

    def test_sliced_reference_and_aligned_lengths(self):
        attention = SageAttentionLSE(self.exact_backend)
        for section in (self.ref, self.aligned):
            out, lse = attention(self.q, self.k[:, :, section], self.v[:, :, section])
            self.assertEqual(out.shape, self.q.shape)
            self.assertEqual(lse.shape, self.q.shape[:-1])
        self.assertEqual([call[1].shape[1] for call in self.calls], [67, 17])

    def test_bfloat16_and_padded_head_dimension_contract(self):
        for dim in (32, 80, 128):
            (q, k, v), _, _ = make_case(torch, "random", device="cpu", dtype=torch.bfloat16, dim=dim)
            out, lse = SageAttentionLSE(self.exact_backend, smooth_k=False)(q, k, v)
            self.assertEqual(out.dtype, torch.bfloat16)
            self.assertEqual(lse.dtype, torch.float32)
            self.assertEqual(out.shape, q.shape)
            self.assertEqual(self.calls[-1][-1]["sm_scale"], dim ** -0.5)
            self.assertFalse(self.calls[-1][-1]["smooth_k"])

    def test_default_refuses_cpu_without_importing_sage(self):
        with self.assertRaisesRegex(ValueError, "requires CUDA"):
            SageAttentionLSE()(self.q, self.k, self.v)

    def test_bad_inputs_fail_before_backend(self):
        attention = SageAttentionLSE(self.exact_backend)
        inputs = [
            (self.q[0], self.k, self.v),
            (self.q, self.k[:, :1], self.v[:, :1]),
            (self.q, self.k[:, :, :-1], self.v),
            (self.q.float(), self.k.float(), self.v.float()),
            (self.q, self.k.bfloat16(), self.v),
            (self.q[:, :, :0], self.k, self.v),
            tuple(torch.zeros(1, 1, 2, 129, dtype=torch.float16) for _ in range(3)),
        ]
        for q, k, v in inputs:
            with self.subTest(shape=q.shape), self.assertRaises(ValueError):
                attention(q, k, v)
        self.assertEqual(self.calls, [])

    def test_bad_backend_returns_fail(self):
        valid_out = torch.zeros(2, 19, 3, 64, dtype=torch.float16)
        valid_lse = torch.zeros(2, 3, 19)
        invalid = [
            valid_out,
            (valid_out, valid_lse, None),
            (valid_out.transpose(1, 2), valid_lse),
            (valid_out, valid_lse.transpose(1, 2)),
            (valid_out.float(), valid_lse),
            (valid_out, valid_lse.half()),
        ]
        for result in invalid:
            with self.subTest(kind=type(result).__name__), self.assertRaises(ValueError):
                SageAttentionLSE(lambda *a, result=result, **kw: result)(self.q, self.k, self.v)

    def test_backend_exception_propagates_without_fallback(self):
        def fails(*args, **kwargs):
            raise RuntimeError("sentinel kernel error")
        with self.assertRaisesRegex(RuntimeError, "sentinel kernel error"):
            SageAttentionLSE(fails)(self.q, self.k, self.v)

    def test_mean_shift_lse_is_not_corrected_twice(self):
        # A uniform K shift leaves O unchanged and shifts natural LSE by Q.c/sqrt(D).
        q, k, v = self.q.float(), self.k.float(), self.v.float()
        shift = torch.full((2, 3, 1, 64), 3.0)
        out, lse = fp32_attention(q, k, v)
        shifted_out, shifted_lse = fp32_attention(q, k + shift, v)
        torch.testing.assert_close(out, shifted_out, atol=1e-6, rtol=1e-5)
        torch.testing.assert_close(shifted_lse - lse, (q * shift).sum(-1) / 8,
                                   atol=1e-6, rtol=1e-5)
        natural_lse = shifted_lse
        returned_out = shifted_out.to(self.q.dtype).transpose(1, 2).contiguous()
        _, returned_lse = SageAttentionLSE(
            lambda *a, **kw: (returned_out, natural_lse)
        )(self.q, self.k, self.v)
        self.assertIs(returned_lse, natural_lse)

    def test_raw_mass_formula_matches_explicit_probability_redistribution(self):
        for name in ("random", "different_k_means", "mass_near_zero", "mass_near_one"):
            (q, k, v), ref, aligned = make_case(torch, name, device="cpu", dtype=torch.float32)
            full, lf = fp32_attention(q, k, v)
            reference, lr = fp32_attention(q, k[:, :, ref], v[:, :, ref])
            aligned_out, _ = fp32_attention(q, k[:, :, aligned], v[:, :, aligned])
            logits = q @ k.transpose(-1, -2) / math.sqrt(q.shape[-1])
            weights = logits.softmax(-1)
            mass = weights[:, :, :, ref].sum(-1)
            routed_weights = weights.clone()
            routed_weights[:, :, :, ref] = 0
            routed_weights[:, :, :, aligned] += mass.unsqueeze(-1) * logits[:, :, :, aligned].softmax(-1)
            corrected = mass_preserve(full, reference, aligned_out, lf, lr, alpha=1.0)
            torch.testing.assert_close(corrected, routed_weights @ v, atol=2e-6, rtol=2e-5)
            torch.testing.assert_close((lr - lf).exp(), mass, atol=2e-6, rtol=2e-5)
            if name == "mass_near_zero":
                self.assertLess(mass.max().item(), 0.0001)
            if name == "mass_near_one":
                self.assertGreater(mass.min().item(), 0.9999)

    def test_alpha_zero_exact_and_positive_delta_not_clamped(self):
        full = torch.ones(1, 1, 1, 1, dtype=torch.float16)
        self.assertIs(mass_preserve(full, None, None, None, None, alpha=0), full)
        result = mass_preserve(full, torch.zeros_like(full), full,
                               torch.zeros(1, 1, 1), torch.ones(1, 1, 1), alpha=1)
        self.assertEqual(result.dtype, torch.float32)
        self.assertGreater(result.item(), 3.7)

    def test_invalid_alpha_and_shapes(self):
        for alpha in (-1, 2, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                mass_preserve(None, None, None, None, None, alpha=alpha)
        with self.assertRaisesRegex(ValueError, "output shape"):
            mass_preserve(self.q, self.k, self.q, None, None, alpha=1)
        with self.assertRaisesRegex(ValueError, "LSE shape"):
            mass_preserve(self.q, self.q, self.q, torch.zeros(1), torch.zeros(1), alpha=1)

    def test_gpu_probe_detects_mutation_of_parent_k_through_subset(self):
        evidence = {}
        originals = (self.q, self.k, self.v)
        inputs = (self.q, self.k[:, :, self.ref], self.v[:, :, self.ref])
        call_preserving_qkv(torch, fp32_attention, inputs, originals, evidence, "reference")
        self.assertEqual(evidence["reference"], {"q": True, "k": True, "v": True})

        def mutates_k(q, k, v):
            k.add_(1)
            return fp32_attention(q, k, v)

        with self.assertRaisesRegex(RuntimeError, "mutated original"):
            call_preserving_qkv(torch, mutates_k, inputs, originals, evidence, "reference")
        self.assertEqual(evidence["reference"], {"q": True, "k": False, "v": True})


if __name__ == "__main__":
    unittest.main()
