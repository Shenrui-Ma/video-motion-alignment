import unittest
import numpy as np
from paired_readout import compare, cross_key_decomposition


class PairedReadoutTests(unittest.TestCase):
    def setUp(self):
        self.spans = [[i, i] for i in range(6)]
        self.valid = [True] * 6
        self.events = [{"id": "fixed", "source_interval_frames": [2, 3]}]
        self.eye = np.eye(6)[None, :, None, :]

    def test_uniform_distribution_cannot_invent_repair_from_late_event_labels(self):
        p = np.ones((1, 6, 1, 6)) / 6
        # Old event-selected e(t)=t-E[reference] would change by 3 for t=1->4,
        # despite no content dependence. Paired common-row analysis stays zero.
        self.assertEqual((4 - 2.5) - (1 - 2.5), 3)
        report, arrays = compare(p, p, self.eye, self.eye, self.spans, self.valid, self.events)
        self.assertEqual(report["events"][0]["weak_minus_native_reference_mean_frames"]["mean"], 0)
        np.testing.assert_array_equal(arrays["weak_minus_native"], 0)

    def test_known_content_delay_has_correct_sign_at_common_rows(self):
        delayed = np.zeros_like(self.eye)
        for i in range(6):
            delayed[0, i, 0, max(i - 2, 0)] = 1
        report, _ = compare(delayed, self.eye, self.eye, self.eye, self.spans, self.valid, self.events)
        self.assertEqual(report["events"][0]["weak_minus_native_reference_mean_frames"]["mean"], 2)

    def test_reference_only_drift_is_reported_and_contrast_zero(self):
        shifted = np.roll(self.eye, 1, axis=-1)
        report, _ = compare(self.eye, shifted, self.eye, shifted, self.spans, self.valid, self.events)
        row = report["events"][0]
        self.assertEqual(row["weak_minus_native_reference_mean_frames"]["mean"], 1)
        self.assertEqual(row["self_drift_subtracted_diagnostic"]["mean"], 0)

    def test_time_shuffling_changes_signal_but_does_not_change_event_rows(self):
        report, arrays = compare(self.eye[:, ::-1], self.eye, self.eye, self.eye,
                                 self.spans, self.valid, self.events)
        self.assertEqual(report["events"][0]["common_query_bins"], [2, 3])
        self.assertFalse(np.all(arrays["weak_minus_native"] == 0))

    def test_constant_appearance_bias_is_separate_from_temporal_diagnostic(self):
        p = np.zeros_like(self.eye); p[..., 1] = 1
        q = np.zeros_like(self.eye); q[..., 3] = 1
        report, arrays = compare(p, q, self.eye, self.eye, self.spans, self.valid, self.events)
        self.assertEqual(report["events"][0]["weak_minus_native_reference_mean_frames"]["mean"], 2)
        np.testing.assert_array_equal(arrays["time_constant_bias_removed"], 0)

    def test_missing_source_support_stays_missing(self):
        events = self.events + [{"id": "outside", "source_interval_frames": [9, 10]}]
        report, _ = compare(self.eye, self.eye, self.eye, self.eye, self.spans, self.valid, events)
        self.assertEqual(report["expected_event_count"], 2)
        self.assertEqual(report["measured_event_count"], 1)
        self.assertEqual(report["events"][1]["status"], "missing_source_bin_support")

    def test_cross_key_decomposition_detects_key_only_change(self):
        # Qnative == Qweak, so swapping Q at fixed K cannot change retrieval.
        shifted = np.roll(self.eye, 1, axis=-1)
        result = cross_key_decomposition(self.eye, shifted, self.eye, shifted, self.spans, self.valid)
        np.testing.assert_array_equal(result["query_contribution"], 0)
        np.testing.assert_array_equal(result["key_contribution"], result["paired_total"])
        self.assertEqual(result["max_decomposition_error"], 0)

    def test_cross_key_decomposition_detects_query_only_change(self):
        shifted = np.roll(self.eye, 1, axis=-1)
        result = cross_key_decomposition(self.eye, shifted, shifted, self.eye, self.spans, self.valid)
        np.testing.assert_array_equal(result["key_contribution"], 0)
        np.testing.assert_array_equal(result["query_contribution"], result["paired_total"])

    def test_cross_key_decomposition_rejects_head_broadcast(self):
        full = np.repeat(self.eye, 56, axis=0)
        with self.assertRaises(ValueError):
            cross_key_decomposition(full, full, self.eye, self.eye, self.spans, self.valid)


if __name__ == "__main__":
    unittest.main()
