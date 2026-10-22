import copy
import unittest
import numpy as np
from evaluate import diagnostic, common_error, original_time_view


def feature_sequence(shift=0, static=False):
    t = np.clip(np.arange(49) - shift, 0, 48)
    angle = np.zeros(49) if static else .015 * t + .001 * t ** 2
    directions = np.stack([np.cos(angle), np.sin(angle)], -1)[:, None, :].repeat(4, axis=1)
    return {"frames": np.arange(49), "times": np.arange(49) / 8, "raw": {"video": {"fps": 8}},
            "arm_direction": directions, "arm_conf": np.ones((49, 4))}


class PhysicalTimeTests(unittest.TestCase):
    def test_same_time(self):
        source = feature_sequence()
        self.assertEqual(diagnostic(source, source, [0, 48], "arm_direction")["lag_ms"], 0)

    def test_known_delay_on_original_timebase(self):
        self.assertEqual(diagnostic(feature_sequence(), feature_sequence(3), [8, 35], "arm_direction")["lag_ms"], 375)

    def test_known_advance(self):
        self.assertEqual(diagnostic(feature_sequence(), feature_sequence(-2), [8, 35], "arm_direction")["lag_ms"], -250)

    def test_static_sequence_retains_unknown(self):
        source = feature_sequence(static=True)
        self.assertIsNone(diagnostic(source, source, [0, 48], "arm_direction")["lag_ms"])

    def test_missing_detection_retains_unknown(self):
        edited = feature_sequence()
        edited["arm_direction"][:30] = np.nan
        self.assertIsNone(diagnostic(feature_sequence(), edited, [0, 48], "arm_direction")["lag_ms"])

    def test_shared_support(self):
        source = feature_sequence()
        native, auto = feature_sequence(), feature_sequence()
        auto["arm_direction"][:10] = np.nan
        result = common_error(source, {"native": native, "automatic": auto}, [0, 48], "arm_direction")
        self.assertAlmostEqual(result["coverage"], 39 / 49)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["same_time_error"], {"native": 0., "automatic": 0.})

    def test_padding_and_repeated_frames_do_not_change_normalization(self):
        xy = np.zeros((17, 2))
        xy[5], xy[6], xy[11], xy[12] = [-1, 0], [1, 0], [-1, 2], [1, 2]
        xy[7], xy[8], xy[9], xy[10] = [-2, 0], [2, 0], [-3, 0], [3, 0]
        person = {"coco17_xy": xy.tolist(), "coco17_score": np.ones(17).tolist()}
        raw = {"video": {"fps": 24}, "frames": [
            {"frame": i, "time_s": i / 24, "selected_person": 0, "persons": [copy.deepcopy(person)]} for i in range(158)]}
        original = original_time_view(raw, .3)
        for i in range(158):
            if i >= 147 or i % 3:
                raw["frames"][i]["persons"][0]["coco17_xy"] = (xy * 1000).tolist()
        changed = original_time_view(raw, .3)
        self.assertEqual(original["scale"], changed["scale"])
        np.testing.assert_equal(original["body_xy"], changed["body_xy"])
        np.testing.assert_equal(changed["times"], np.arange(49) / 8)
        for invalid in (float("nan"), float("inf")):
            broken = copy.deepcopy(raw)
            broken["frames"][0]["persons"][0]["coco17_score"][5] = invalid
            with self.subTest(confidence=invalid), self.assertRaises(ValueError):
                original_time_view(broken, .3)


if __name__ == "__main__":
    unittest.main()
