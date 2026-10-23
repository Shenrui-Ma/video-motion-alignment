import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

import core
import run

POLICY = run.read(Path(__file__).with_name("POLICY.json"))
FOLDS = POLICY["folds"]


def small(c):
    c = np.asarray(c, dtype=np.float64)
    if c.ndim == 2:
        c = np.repeat(c[:, None, :], 8, axis=1)
    return core.analyze_reference(c[None], np.stack([np.arange(len(c))] * 2, axis=1),
                                  np.ones(len(c), dtype=bool), FOLDS)


class MathematicalTests(unittest.TestCase):
    def test_static_retains_all_ties(self):
        a = small(np.ones((9, 9)) / 9)
        self.assertTrue(np.all(a["candidate_count"] == 9))
        self.assertTrue(np.all(a["nearest_mask"]))
        self.assertTrue(np.all(a["linear_rank"] == 0))
        self.assertTrue(np.all(a["candidate_diameter"] == 8))
        self.assertTrue(np.all(a["minimum_separation_curve"] == 0))

    def test_role5_repetition_is_ambiguous(self):
        c = np.eye(15)[np.arange(15) % 5]
        a = small(c)
        self.assertTrue(np.all(a["candidate_count"] == 3))
        self.assertTrue(np.all(a["candidate_diameter"] == 10))
        self.assertGreater(float(np.mean(a["linear_heldout_error"] ** 2)), 15)

    def test_permuted_reference_has_exact_time_despite_raw_mean_error(self):
        c = np.eye(7)[:, [2, 3, 6, 0, 4, 1, 5]]
        self.assertGreater(np.max(abs(c @ np.arange(7) - np.arange(7))), 2)
        a = small(c)
        self.assertTrue(np.all(a["candidate_count"] == 1))
        np.testing.assert_allclose(a["linear_heldout_error"], 0, atol=2e-14)

    def test_ill_conditioned_reference_has_large_inverse_gain(self):
        c = (1 - 1e-8) * np.ones((6, 6)) / 6 + 1e-8 * np.eye(6)
        a = small(c)
        self.assertGreater(float(a["linear_inverse_gain"].min()), 1e8)
        self.assertLess(np.max(abs(a["linear_fit_error"])), 1e-6)
        self.assertLess(a["minimum_separation_curve"].max(), 1e-6)

    def test_training_radius_does_not_force_heldout_coverage(self):
        c = np.repeat(np.eye(7)[:, None, :], 8, axis=1)
        c[:, 1::2] = np.roll(c[:, 1::2], 2, axis=0)
        a = small(c)
        self.assertTrue(np.all(a["training_radius"] == 0))
        self.assertTrue(np.all(a["heldout_max_radius_descriptive"] > 1))
        self.assertFalse(a["candidate_contains_correct_time"].any())
        self.assertTrue(np.all(a["candidate_count"] == 1))

    def test_out_of_template_support_keeps_empty_set(self):
        c = np.repeat(np.eye(7)[:, None, :], 8, axis=1)
        c[:, 1::2] = 1 / 7
        a = small(c)
        self.assertTrue(np.all(a["candidate_count"] == 0))
        self.assertTrue(np.isnan(a["candidate_diameter"]).all())
        s = core.summarize(a)
        self.assertTrue(all(r["empty_fraction"] == 1 for r in s["per_head_fold"]))

    def test_appearance_lookalike_remains_unidentifiable_after_perfect_cv(self):
        c = np.eye(7)
        a = small(c)
        self.assertTrue(np.all(a["candidate_contains_correct_time"]))
        # External worlds: delayed content and unchanged pose with different appearance.
        delayed = c[5]
        appearance_only = c[5]
        np.testing.assert_array_equal(delayed, appearance_only)
        d = core.pair_distance(appearance_only, c)
        self.assertEqual(np.flatnonzero(d == 0).tolist(), [5])
        self.assertFalse(core.summarize(a)["generated_domain_validated"])

    def test_all_resolution_curve_matches_bruteforce(self):
        rng = np.random.default_rng(14)
        c = rng.dirichlet(np.ones(8), size=(8, 8))
        a = small(c)
        for fold in range(2):
            template = c[:, FOLDS[fold]["train"]].mean(1)
            for k, delta in enumerate(a["resolutions"]):
                expected = min(np.linalg.norm(np.sqrt(template[i]) - np.sqrt(template[j]))
                               for i in range(8) for j in range(8) if abs(i-j) >= delta)
                self.assertAlmostEqual(a["minimum_separation_curve"][0, fold, k], expected)

    def test_loo_radius_uses_three_train_probes_only(self):
        rng = np.random.default_rng(7)
        c = rng.dirichlet(np.ones(5), size=(5, 8))
        a = small(c)
        for f in range(2):
            idx = FOLDS[f]["train"]
            values = []
            for t in range(5):
                for probe in idx:
                    others = c[t, [p for p in idx if p != probe]].mean(0)
                    values.append(np.linalg.norm(np.sqrt(c[t, probe]) - np.sqrt(others)))
            self.assertAlmostEqual(a["training_radius"][0, f], max(values))

    def test_key_permutation_and_probe_fold_symmetry(self):
        rng = np.random.default_rng(3)
        c = rng.dirichlet(np.ones(6), size=(6, 8))
        a, b = small(c), small(c[..., ::-1])
        for key in ("candidate_mask", "minimum_separation_curve", "heldout_distances"):
            np.testing.assert_allclose(a[key], b[key], atol=1e-14)
        perm = [1, 0, 3, 2, 5, 4, 7, 6]
        swapped = small(c[:, perm])
        for key in ("candidate_mask", "heldout_distances", "linear_heldout_error"):
            np.testing.assert_allclose(a[key][:, ::-1], swapped[key], atol=1e-12)


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.policy = copy.deepcopy(POLICY)
        valid = np.asarray(POLICY["valid_bins"], dtype=bool)
        p = np.zeros(POLICY["shape"], dtype=np.float64)
        for t in range(31):
            p[:, t, :, t] = .8
            p[:, t, :, :31] += .2 / 31
        self.arrays = {"qrn_kn": p, "qrw_kw": p.copy(), "valid_bins": valid,
                       "physical_frame_spans_inclusive": np.array(POLICY["physical_frame_spans_inclusive"]),
                       "spatial_ids": np.array(POLICY["spatial_ids"])}
        for step in (9, 19):
            self.save(step)
        run.write(self.root / "upstream.json", {"status": "complete", "results_written": True,
                                                "summary_sha256": POLICY["upstream"]["summary_sha256"]})
        self.policy["upstream"]["status_sha256"] = run.sha(self.root / "upstream.json")
        self.manifest = {"schema": "h3-reference-only-diagnostic-input-v1", "upstream_status": "upstream.json",
                         "steps": {"9": "step9.npz", "19": "step19.npz"}}
        self.inputs = self.root / "inputs.json"
        run.write(self.inputs, self.manifest)

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, step):
        path = self.root / f"step{step}.npz"
        np.savez_compressed(path, **self.arrays)
        # Invalid generated member is deliberate: reference-only loader must never decode it.
        with zipfile.ZipFile(path, "a") as archive:
            archive.writestr("qn_kn.npy", b"this is not a valid npy array")
            archive.writestr("generated_event_mae.npy", b"not used")
        self.policy["upstream"]["npz_sha256"][str(step)] = run.sha(path)

    def test_real_shape_integration_retains_every_axis_and_all_four_products(self):
        status = run.execute(self.inputs, self.root / "out", self.policy)
        self.assertEqual(status["status"], "complete")
        out = self.root / "out"
        self.assertEqual(len(list(out.glob("*.npz"))), 4)
        summary = run.read(out / "summary.json")
        self.assertEqual(len(summary["diagnostics"]), 4)
        for path in out.glob("*.npz"):
            with np.load(path, allow_pickle=False) as z:
                self.assertEqual(z["candidate_mask"].shape, (56, 2, 31, 4, 31))
                self.assertEqual(z["pairwise_distance"].shape, (56, 2, 31, 31))
                self.assertEqual(z["linear_heldout_error"].shape, (56, 2, 31, 4))
                self.assertTrue(np.all(z["candidate_count"] == 1))
                self.assertTrue(np.all(z["candidate_contains_correct_time"]))
                self.assertEqual(z["valid_indices"].tolist(), list(range(31)))
                self.assertEqual(z["input_valid_bins"].tolist(), POLICY["valid_bins"])
                self.assertEqual(z["input_spatial_ids"].tolist(), POLICY["spatial_ids"])
        self.assertFalse(summary["generated_domain_validated"])

    def test_npz_access_white_list(self):
        from numpy.lib.npyio import NpzFile
        original = NpzFile.__getitem__
        accessed = []
        def guarded(obj, key):
            accessed.append(key)
            self.assertIn(key, run.ALLOWED_KEYS)
            return original(obj, key)
        with patch.object(NpzFile, "__getitem__", guarded):
            run.preflight(run.path_inputs(self.inputs), self.policy)
        self.assertEqual(set(accessed), run.ALLOWED_KEYS)
        self.assertEqual(len(accessed), 10)

    def test_missing_input_pending_without_results(self):
        (self.root / "step19.npz").unlink()
        status = run.execute(self.inputs, self.root / "out", self.policy)
        self.assertEqual(status["status"], "pending")
        self.assertEqual([x.name for x in (self.root / "out").iterdir()], ["STATUS.json"])

    def test_wrong_identity_invalid_before_decode(self):
        self.policy["upstream"]["npz_sha256"]["9"] = "0" * 64
        with patch.object(run, "decode_reference", side_effect=AssertionError("must not decode")):
            status = run.execute(self.inputs, self.root / "out", self.policy)
        self.assertEqual(status["status"], "invalid")
        self.assertFalse(status["results_written"])

    def test_unknown_step_invalid(self):
        self.manifest["steps"]["18"] = "step9.npz"
        run.write(self.inputs, self.manifest)
        status = run.execute(self.inputs, self.root / "out", self.policy)
        self.assertEqual(status["status"], "invalid")

    def test_missing_step_pending(self):
        del self.manifest["steps"]["19"]
        run.write(self.inputs, self.manifest)
        self.assertEqual(run.execute(self.inputs, self.root / "out", self.policy)["status"], "pending")

    def test_failed_upstream_invalid_running_pending(self):
        for state in ("failed", "running"):
            run.write(self.root / "upstream.json", {"status": state})
            actual = run.execute(self.inputs, self.root / state, self.policy)["status"]
            self.assertEqual(actual, "pending" if state == "running" else "invalid")

    def test_bad_padding_or_normalization_invalid(self):
        for name in ("padding", "normalization"):
            arr = self.arrays["qrn_kn"]
            if name == "padding":
                arr[0, 31, 0, 0] = 1
            else:
                arr[0, 31, 0, 0] = 0
                arr[0, 0, 0, 0] *= .9
            self.save(9)
            status = run.execute(self.inputs, self.root / name, self.policy)
            self.assertEqual(status["status"], "invalid")

    def test_nonfinite_or_shape_mismatch_invalid(self):
        for name in ("nonfinite", "shape"):
            if name == "nonfinite":
                self.arrays["qrn_kn"][0, 0, 0, 0] = np.nan
            else:
                self.arrays["qrn_kn"] = self.arrays["qrw_kw"][:, :, :-1]
            self.save(9)
            status = run.execute(self.inputs, self.root / name, self.policy)
            self.assertEqual(status["status"], "invalid")

    def test_no_overwrite_previous_results(self):
        out = self.root / "out"
        out.mkdir()
        (out / "keep").write_text("untouched")
        with self.assertRaises(FileExistsError):
            run.execute(self.inputs, out, self.policy)
        self.assertEqual((out / "keep").read_text(), "untouched")


if __name__ == "__main__":
    unittest.main()
