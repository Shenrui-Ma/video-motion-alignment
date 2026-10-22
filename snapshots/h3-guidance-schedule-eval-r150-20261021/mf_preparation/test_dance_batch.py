"""CPU checks for new-source ordering and incomplete-input rejection."""
import copy
import unittest

from prepare_dance_batch import ROLES, plan_for


class DanceBatchTests(unittest.TestCase):
    def inputs(self, cached):
        return {"targets": [{"role": x} for x in ROLES],
                "valid_frames": 141, "evaluation_frames": 141,
                "evaluation_fps": 24, "crop_xywh": [0, 0, 1312, 736],
                "source_cache": {"tracks_sha256": "frozen"} if cached else None}

    def test_musk_reuses_exact_source_and_scores_old_native(self):
        plan = plan_for("musk05", self.inputs(True))
        self.assertEqual([j["role"] for j in plan["jobs"]], list(ROLES))
        self.assertEqual(plan["new_source_trackers"], 0)

    def test_new_sources_tracked_once_before_targets(self):
        for sid in ("firefly06", "sam07"):
            plan = plan_for(sid, self.inputs(False))
            self.assertEqual([j["role"] for j in plan["jobs"]], ["source"] + list(ROLES))
            self.assertEqual(plan["unique_targets"], 6)

    def test_missing_or_duplicated_control_rejected(self):
        for targets in (self.inputs(True)["targets"][1:],
                        [{"role": "early"}] * 6):
            inputs = self.inputs(True)
            inputs["targets"] = targets
            with self.assertRaises(Exception):
                plan_for("musk05", inputs)

    def test_cache_policy_and_domain_cannot_be_silently_changed(self):
        for key, value in (("source_cache", None), ("evaluation_frames", 140),
                           ("evaluation_fps", 25), ("crop_xywh", [16, 8, 1280, 720])):
            inputs = copy.deepcopy(self.inputs(True))
            inputs[key] = value
            with self.assertRaises(Exception):
                plan_for("musk05", inputs)


if __name__ == "__main__":
    unittest.main()
