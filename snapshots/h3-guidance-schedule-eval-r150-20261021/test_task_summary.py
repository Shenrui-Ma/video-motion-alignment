import unittest
from summarize_tasks import classify, interval_error


class TaskSummaryTests(unittest.TestCase):
    def test_missing_event_prevents_numeric_gain(self):
        events = [{"source": [1, 3], "native": [5, 7], "early": None}]
        result = classify({"source_id": "example"}, "early",
                          {"task_verdict": "PASS_CORE_EDIT", "events": events})
        self.assertIsNone(result["new_error"])
        self.assertFalse(result["error_reduced_with_core_edit"])

    def test_partial_edit_not_counted_as_qualified_timing_gain(self):
        events = [{"source": [1, 3], "native": [5, 7], "early": [1, 3]}]
        result = classify({"source_id": "example"}, "early",
                          {"task_verdict": "PARTIAL_EDIT", "events": events})
        self.assertEqual(result["new_error"], 0)
        self.assertFalse(result["error_reduced_with_core_edit"])

    def test_broad_phases_never_produce_numeric_lag(self):
        self.assertIsNone(interval_error([{"source": None, "early": None}], "early"))

    def test_absent_first_action_kept_separate(self):
        result = classify({"source_id": "firefly06"}, "early", {
            "task_verdict": "PASS_CORE_EDIT",
            "events": [{"id": "early_eye_insert", "native": None, "early": None},
                       {"id": "later_v_pose_and_leg_raise", "early": [52, 67]}]})
        self.assertFalse(result["missing_action_restored"])

    def test_matched_native_preservation_overrides_historical_delay(self):
        case = {"source_id": "sam07", "_initial_group": "preservation",
                "events": [{"id": "pose"}]}
        review = {"task_verdict": "PASS_CORE_EDIT",
                  "events": [{"id": "pose", "source": [60, 61], "early": [60, 61]}],
                  "preservation_observations": [
                      {"id": "pose", "new_phase_present_in_same_range": True}]}
        result = classify(case, "early", review)
        self.assertEqual(result["group"], "preservation")
        self.assertTrue(result["preserved"])
        self.assertNotIn("error_reduced_with_core_edit", result)


if __name__ == "__main__":
    unittest.main()
