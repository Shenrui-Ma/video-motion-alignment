import unittest
import numpy as np

from oracle import time_code, read_time, trajectory_matches, separation, leave_probe_split


class IdentifiabilityTests(unittest.TestCase):
    def test_non_diagonal_permutation_is_identifiable(self):
        # Raw key-coordinate mean is wrong although fingerprints retain all time information.
        tau = np.arange(7, dtype=float)
        c = np.eye(7)[:, [3, 0, 6, 1, 5, 2, 4]]
        self.assertGreater(np.max(np.abs(c @ tau - tau)), 2)
        code = time_code(c, tau)
        np.testing.assert_allclose(read_time(code, c), tau, atol=2e-14)
        self.assertLess(code["unregularized_unidentifiable_residual"], 1e-13)

    def test_static_reference_has_no_absolute_time(self):
        c = np.full((8, 8), 1 / 8)
        code = time_code(c, np.arange(8))
        self.assertEqual(code["numerical_rank"], 0)
        self.assertGreater(code["unregularized_unidentifiable_residual"], 1)
        matches = trajectory_matches(c, c[:1], np.arange(8), assumed_radius=0,
                                     requested_time_resolution=1)
        self.assertEqual(matches[0]["status"], "temporally_ambiguous")
        self.assertEqual(len(matches[0]["candidate_times"]), 8)

    def test_role5_repetition_cannot_identify_cycle(self):
        c = np.eye(5)[np.arange(15) % 5]
        result = trajectory_matches(c, c[[2]], np.arange(15), assumed_radius=0,
                                    requested_time_resolution=1)[0]
        self.assertEqual(result["candidate_times"], [2., 7., 12.])
        self.assertEqual(result["status"], "temporally_ambiguous")
        self.assertEqual(separation(c, np.arange(15), minimum_time_separation=4), 0)
        self.assertGreater(time_code(c, np.arange(15))["training_rmse"], 3)

    def test_rank_deficiency_need_not_destroy_scalar_time(self):
        # Only rank one after centering; enough to encode this scalar coordinate exactly.
        tau = np.arange(9, dtype=float)
        v = tau / tau.max()
        c = np.stack((v, 1 - v), axis=1)
        code = time_code(c, tau)
        self.assertEqual(code["numerical_rank"], 1)
        np.testing.assert_allclose(code["fitted"], tau, atol=2e-14)

    def test_nearly_static_fit_is_ill_conditioned(self):
        tau = np.arange(6, dtype=float)
        eta = 1e-8
        c = (1 - eta) * np.ones((6, 6)) / 6 + eta * np.eye(6)
        exact = time_code(c, tau)
        self.assertLess(exact["training_rmse"], 1e-6)
        self.assertGreater(exact["inverse_l2_gain"], 1e8)
        moved = c[[0]].copy()
        moved[0, 0] -= eta
        moved[0, -1] += eta
        self.assertGreater(abs(read_time(exact, moved)[0] - tau[0]), 4.9)

    def test_linear_readout_noise_bound(self):
        rng = np.random.default_rng(4)
        c = rng.dirichlet(np.ones(7), size=7)
        code = time_code(c, np.arange(7), ridge_relative=.01)
        p = .99 * c + .01 / 7
        changes = abs(read_time(code, p) - read_time(code, c))
        bound = np.linalg.norm(p - c, axis=1) * code["inverse_l2_gain"]
        self.assertTrue(np.all(changes <= bound + 1e-12))

    def test_reference_spatial_holdout_catches_memorized_probe(self):
        c = np.repeat(np.eye(7)[:, None, :], 8, axis=1)
        c[:, 1::2] = np.roll(c[:, 1::2], 2, axis=0)
        result = leave_probe_split(c, np.arange(7), train_probes=[0, 2, 4, 6],
                                  test_probes=[1, 3, 5, 7])
        self.assertLess(result["code"]["training_rmse"], 1e-13)
        self.assertGreater(result["heldout_rmse"], 2)

    def test_reference_holdout_success_does_not_identify_generated_appearance(self):
        c = np.repeat(np.eye(7)[:, None, :], 8, axis=1)
        result = leave_probe_split(c, np.arange(7), train_probes=[0, 2, 4, 6],
                                  test_probes=[1, 3, 5, 7])
        self.assertLess(result["heldout_rmse"], 1e-13)
        # A pose at t=1 with changed appearance yields exactly the fingerprint of t=5.
        # Both time-shift and appearance-only worlds present this identical observation.
        g = c[[5], 0]
        self.assertAlmostEqual(read_time(result["code"], g)[0], 5)
        matched = trajectory_matches(c[:, 0], g, np.arange(7), assumed_radius=0,
                                     requested_time_resolution=0)[0]
        self.assertEqual(matched["candidate_times"], [5.])
        self.assertEqual(matched["status"], "unique_at_requested_resolution")
        # This is a counterexample to semantic validity, not a desired success of the method.

    def test_two_mode_mean_is_not_an_observed_middle_pose(self):
        c = np.eye(7)
        p = .5 * c[[0]] + .5 * c[[6]]
        code = time_code(c, np.arange(7))
        self.assertAlmostEqual(read_time(code, p)[0], 3)
        rejected = trajectory_matches(c, p, np.arange(7), assumed_radius=.1,
                                      requested_time_resolution=1)[0]
        self.assertEqual(rejected["status"], "out_of_reference_support")
        # A looser radius retains disjoint endpoints rather than inventing their midpoint.
        ambiguous = trajectory_matches(c, p, np.arange(7), assumed_radius=.8,
                                       requested_time_resolution=1)[0]
        self.assertEqual(ambiguous["candidate_times"], [0., 6.])
        self.assertEqual(ambiguous["status"], "temporally_ambiguous")

    def test_separation_certificate_and_perturbation(self):
        c = np.eye(6)
        p = .98 * c[[3]] + .02 / 6
        eps = np.linalg.norm(np.sqrt(p[0]) - np.sqrt(c[3]))
        self.assertGreater(separation(c, np.arange(6), minimum_time_separation=1), 2 * eps)
        got = trajectory_matches(c, p, np.arange(6), assumed_radius=eps + 1e-12,
                                 requested_time_resolution=0)[0]
        self.assertEqual(got["candidate_times"], [3.])

    def test_known_content_shift_and_column_permutation(self):
        c = .9 * np.eye(9) + .1 / 9
        indices = np.array([1, 2, 6])
        shifted = c[indices + 1]
        baseline = trajectory_matches(c, shifted, np.arange(9), assumed_radius=0,
                                      requested_time_resolution=0)
        self.assertEqual([x["candidate_times"][0] for x in baseline], [2., 3., 7.])
        permutation = [3, 8, 0, 4, 5, 7, 1, 2, 6]
        same = trajectory_matches(c[:, permutation], shifted[:, permutation], np.arange(9),
                                  assumed_radius=0, requested_time_resolution=0)
        self.assertEqual(same, baseline)

    def test_no_support_intersection_or_silent_normalization(self):
        with self.assertRaises(ValueError):
            trajectory_matches(np.eye(3), np.eye(4), np.arange(3), assumed_radius=0,
                               requested_time_resolution=0)
        with self.assertRaises(ValueError):
            time_code(np.ones((3, 3)), np.arange(3))
        with self.assertRaises(ValueError):
            leave_probe_split(np.repeat(np.eye(3)[:, None], 2, axis=1), np.arange(3),
                              train_probes=[0], test_probes=[0])


if __name__ == "__main__":
    unittest.main()
