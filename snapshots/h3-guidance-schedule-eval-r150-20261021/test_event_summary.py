import unittest

from summarize_review import event_stats


class EventSummaryTests(unittest.TestCase):
    def test_pending_fixed_retains_source_error(self):
        result = event_stats([54, 68], None, [52, 67], 24)
        self.assertEqual(result["absolute_error_frames"], [0, 16])
        self.assertIsNone(result["paired_change_vs_fixed_ms"])

    def test_missing_event_is_not_a_delay(self):
        self.assertIsNone(event_stats([39, 44], None, None, 24))

    def test_existing_fixed_comparison_unchanged(self):
        result = event_stats([10, 10], [15, 15], [11, 11], 25)
        self.assertEqual(result, {"absolute_error_frames": [1, 1],
                                 "paired_change_vs_fixed_ms": [-160.0, -160.0]})


if __name__ == "__main__":
    unittest.main()
