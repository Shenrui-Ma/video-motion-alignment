import importlib
import sys
import types
import unittest
from pathlib import Path
import torch

ROOT = Path(__file__).resolve().parents[1]
pkg = types.ModuleType("r151_test_router")
pkg.__path__ = [str(ROOT / "extensions/H3TemporalRouter")]
sys.modules[pkg.__name__] = pkg
core = importlib.import_module(pkg.__name__ + ".core")
rec = importlib.import_module(pkg.__name__ + ".reciprocal")


def plan():
    return dict(seq_len=31, reference_video_segment=[3, 15], target_video_segment=[19, 31],
                latent_interval_half_open=[1, 3], frame_rows=3,
                key_interval_half_open=[6, 12], query_interval_half_open=[22, 28])


def dense(q, k, v):
    z = q @ k.transpose(-1, -2) / q.shape[-1]**.5
    return z.softmax(-1) @ v, z.logsumexp(-1).float()  # Flash returns FP32 natural LSE.


def explicit(q, k, v, alpha, beta):
    z = q @ k.transpose(-1, -2) / q.shape[-1]**.5
    native = z.softmax(-1)
    p = native.clone()
    for qa, qb, ka, kb, qbase, strength in ((22, 28, 3, 15, 19, alpha),
                                           (6, 12, 19, 31, 3, beta)):
        for i in range(qa, qb):
            j = ka + (i-qbase)//3*3
            mass = native[:, :, i, ka:kb].sum(-1, keepdim=True)
            p[:, :, i, ka:kb] *= 1-strength
            p[:, :, i, j:j+3] += strength*mass*z[:, :, i, j:j+3].softmax(-1)
    out = p @ v
    return out.transpose(1, 2).reshape(1, 31, 24), p, native


class ReciprocalTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        gen = torch.Generator().manual_seed(151)
        self.q, self.k, self.v = [torch.randn(1, 3, 31, 8, generator=gen,
                                             dtype=torch.float64) for _ in range(3)]

    def run_arm(self, a, b, **kw):
        return rec.route_reciprocal(self.q, self.k, self.v, 3, plan(),
                                    alpha=a, beta=b, attention=dense, **kw)

    def test_zero_is_exact_original(self):
        out = self.run_arm(0., 0.)
        old = core.route_attention(self.q, self.k, self.v, 3, plan(),
                                  mode="native", attention=dense)
        self.assertTrue(torch.equal(out, old))

    def test_beta_zero_exact_r149_forward(self):
        for a in (0., .25, 1.):
            old = core.route_attention(self.q, self.k, self.v, 3, plan(),
                                      mode="mass_preserve", alpha=a, attention=dense)
            self.assertTrue(torch.equal(self.run_arm(a, 0.), old))

    def test_both_directions_match_explicit_probabilities(self):
        # Production deliberately retains the original FP32 correction arithmetic,
        # also when the independent dense oracle uses FP64.
        for a, b in ((0., 1.), (1., 1.), (.25, .75)):
            expect, _, _ = explicit(self.q, self.k, self.v, a, b)
            torch.testing.assert_close(self.run_arm(a, b), expect, atol=5e-7, rtol=2e-6)

    def test_group_mass_complement_and_normalization(self):
        for a, b in ((0., 1.), (1., 1.), (.25, .75)):
            _, p, old = explicit(self.q, self.k, self.v, a, b)
            for qa, qb, ka, kb in ((22, 28, 3, 15), (6, 12, 19, 31)):
                torch.testing.assert_close(p[:, :, qa:qb, ka:kb].sum(-1),
                                           old[:, :, qa:qb, ka:kb].sum(-1), atol=2e-15, rtol=2e-15)
                self.assertTrue(torch.equal(p[:, :, qa:qb, :ka], old[:, :, qa:qb, :ka]))
                self.assertTrue(torch.equal(p[:, :, qa:qb, kb:], old[:, :, qa:qb, kb:]))
            torch.testing.assert_close(p.sum(-1), torch.ones_like(p.sum(-1)), atol=2e-15, rtol=2e-15)
            self.assertGreaterEqual(float(p.min()), 0.)

    def test_only_same_bin_keys_for_unit_strength(self):
        _, p, _ = explicit(self.q, self.k, self.v, 1., 1.)
        for qa, qb, ka, kb, qbase in ((22, 28, 3, 15, 19), (6, 12, 19, 31, 3)):
            for i in range(qa, qb):
                j = ka+(i-qbase)//3*3
                self.assertEqual(int(torch.count_nonzero(p[:, :, i, ka:j])), 0)
                self.assertEqual(int(torch.count_nonzero(p[:, :, i, j+3:kb])), 0)

    def test_nonselected_rows_and_inputs_rng_unchanged(self):
        saved = [x.clone() for x in (self.q, self.k, self.v)]
        rng = torch.get_rng_state().clone()
        native = self.run_arm(0., 0.)
        out = self.run_arm(1., 1.)
        keep = list(range(6)) + list(range(12, 22)) + list(range(28, 31))
        self.assertTrue(torch.equal(out[:, keep], native[:, keep]))
        reverse = self.run_arm(0., 1.)
        self.assertTrue(torch.equal(reverse[:, 19:], native[:, 19:]))
        self.assertTrue(all(torch.equal(x, y) for x, y in zip(saved, (self.q, self.k, self.v))))
        self.assertTrue(torch.equal(rng, torch.get_rng_state()))

    def test_one_joint_call_and_aux_counts(self):
        for a, b, count in ((0., 0., 1), (1., 0., 3), (0., 1., 3), (1., 1., 5)):
            calls = []
            def counted(q, k, v):
                calls.append((q.shape[-2], k.shape[-2]))
                return dense(q, k, v)
            rec.route_reciprocal(self.q, self.k, self.v, 3, plan(), alpha=a, beta=b, attention=counted)
            self.assertEqual(len(calls), count)
            self.assertEqual(calls.count((31, 31)), 1)

    def test_bad_ranges_and_parameters(self):
        for update in ({"reference_video_segment": [2, 14]}, {"target_video_segment": [14, 26]},
                       {"key_interval_half_open": [2, 3]}, {"frame_rows": True}):
            with self.assertRaises(ValueError):
                rec.reverse_ranges(dict(plan(), **update))
        for a, b in ((-1., 1.), (1., float("nan")), (1., 2.)):
            with self.assertRaises(ValueError):
                self.run_arm(a, b)

    def test_raw_reverse_mass_diagnostics_and_finite_extremes(self):
        for sign in (-1., 1.):
            self.q.fill_(10.)
            self.k.fill_(-10.)
            self.k[:, :, 19:].fill_(sign*10.)
            d = {}
            out = self.run_arm(0., 1., diagnostics=d)
            self.assertTrue(bool(torch.isfinite(out).all()))
            self.assertEqual(float(d["reverse_all_finite"]), 1.)
            self.assertLessEqual(float(d["reverse_log_mass_max"]), 1e-6)

    def test_no_rope_or_position_input(self):
        import inspect
        parameters = inspect.signature(rec.route_reciprocal).parameters
        self.assertNotIn("position_ids", parameters)
        self.assertNotIn("inv_freq", parameters)


if __name__ == "__main__":
    unittest.main()
