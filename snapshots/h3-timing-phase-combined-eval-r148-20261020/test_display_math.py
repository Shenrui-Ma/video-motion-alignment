import unittest

from build_html import duration_frames, event_label, latency_ms
from prepare_comparison import screenshot_selection


class DisplayMathTests(unittest.TestCase):
    def test_late_event_interval_in_physical_time(self):
        low, high = latency_ms([95, 98], [111, 114], 24)
        self.assertAlmostEqual(low, 13 * 1000 / 24)
        self.assertAlmostEqual(high, 19 * 1000 / 24)

    def test_identical_intervals_preserve_annotation_range(self):
        self.assertEqual(latency_ms([42, 45], [42, 45], 24), [-125, 125])

    def test_duration_removes_constant_shift(self):
        self.assertEqual(duration_frames([9, 12], [24, 26]), [12, 17])
        self.assertEqual(duration_frames([25, 28], [40, 42]), [12, 17])

    def test_missing_event_is_not_zero(self):
        self.assertIsNone(latency_ms([1, 2], None, 24))
        self.assertIsNone(duration_frames(None, [4, 5]))

    def test_handkerchief_label_translation(self):
        self.assertEqual(event_label({"label": "hand_leaves_face"}), "手离开面部")

    def test_full_frame_export_does_not_hit_ffmpeg_expression_depth(self):
        for total in (98, 105, 106, 141, 144):
            self.assertEqual(screenshot_selection(list(range(total)), total), "1")
        self.assertEqual(screenshot_selection([42, 48, 69], 98), r"eq(n\,42)+eq(n\,48)+eq(n\,69)")


if __name__ == "__main__":
    unittest.main()
