import copy
import unittest

import numpy as np

from evaluate_live import validate_events, validate_gate, summarize_live


def fixture():
    plan = {"case_id": "short_0358", "methods": ["native", "global_weak"],
            "source_video_provenance": {"sha256": "a" * 64},
            "events": [{"id": "touch", "source_interval_frames": [2, 3]},
                       {"id": "leave", "source_interval_frames": [4, 5]}]}
    provenance = {"source": {"sha256": "a" * 64}}
    for method in plan["methods"]:
        provenance[method] = {"sha256": ("b" if method == "native" else "c") * 64,
                              "trajectory_id": "new_" + method, "frame_count": 6,
                              "annotation_source": "new_complete_video",
                              "annotation_record_sha256": "d" * 64}
    annotations = {"schema": "h3-live-phase-event-annotations-v1", "plan_sha256": "e" * 64,
                   "case_id": "short_0358", "video_provenance": provenance,
                   "events": [{"id": e["id"], "source": e["source_interval_frames"],
                               **{m: {"status": "observed", "interval": e["source_interval_frames"]}
                                  for m in plan["methods"]}} for e in plan["events"]]}
    contract = {"science_contract_sha256": "f" * 64, "sample_sigmas_video": list(range(20, -1, -1)),
                "noise_sha256": "1" * 64}
    tensor = {"dtype": "torch.float32", "shape": [1, 1, 12], "finite": True, "sha256": "2" * 64}
    captures = []
    for step in (9, 19):
        identity = {"trajectory_id": "new_native", "case": "short_0358", "method": "native",
                    "science_contract_sha256": contract["science_contract_sha256"],
                    "step_zero_based": step, "layer_zero_based": 25,
                    "state_file_sha256": "3" * 64, "packed_x": tensor, "raw_packed_x0": tensor,
                    "sample_sigmas_video": contract["sample_sigmas_video"],
                    "noise_sha256": contract["noise_sha256"]}
        captures.append({"step_zero_based": step, "layer_zero_based": 25,
                         "state_file_sha256": "3" * 64, "qk_sha256": ("4" if step == 9 else "5") * 64,
                         "forward_identity": identity})
    gate = {"schema": "h3-live-phase-trajectory-gate-v1", "passed": True,
            "trajectory_id": "new_native", "case": "short_0358", "method": "native",
            "science_contract_sha256": contract["science_contract_sha256"],
            "actual_video_sha256": "b" * 64, "observation_manifest_sha256": "6" * 64,
            "callback_count": 20, "actual_model_forward_count": 20,
            "completed_blocks": 1000, "extra_model_forward_calls": 0, "captures": captures}
    capture = {"schema": "h3-passive-qk-capture-v1", "case": "short_0358", "method": "native",
               "step_zero_based": 9, "layer_zero_based": 25, "forward_identity": captures[0]["forward_identity"]}
    return plan, annotations, contract, gate, capture


class LiveChecks(unittest.TestCase):
    def test_valid_binding_and_same_numeric_intervals_are_allowed(self):
        p, a, c, g, q = fixture()
        validate_events(a, p, "e" * 64)
        validate_gate(q, "4" * 64, g, a, "native", c)

    def test_historical_gate_and_incomplete_trajectory_rejected(self):
        p, a, c, g, q = fixture()
        for field, bad in (("schema", "h3-passive-replay-release-v1"), ("passed", False),
                           ("callback_count", 19), ("actual_model_forward_count", 21),
                           ("completed_blocks", 999), ("extra_model_forward_calls", 1)):
            changed = copy.deepcopy(g)
            changed[field] = bad
            with self.assertRaises(ValueError, msg=field):
                validate_gate(q, "4" * 64, changed, a, "native", c)

    def test_cross_trajectory_same_file_list_is_rejected(self):
        p, a, c, g, q = fixture()
        for key, bad in (("method", "global_weak"), ("step_zero_based", 9),
                         ("trajectory_id", "old_native"), ("sample_sigmas_video", [1, 0]),
                         ("science_contract_sha256", "a" * 64), ("noise_sha256", "b" * 64)):
            changed = copy.deepcopy(g)
            changed["captures"][1]["forward_identity"][key] = bad
            with self.assertRaises(ValueError, msg=key):
                validate_gate(q, "4" * 64, changed, a, "native", c)

    def test_capture_or_video_substitution_rejected(self):
        p, a, c, g, q = fixture()
        with self.assertRaises(ValueError):
            validate_gate(q, "9" * 64, g, a, "native", c)
        g["actual_video_sha256"] = "c" * 64
        with self.assertRaises(ValueError):
            validate_gate(q, "4" * 64, g, a, "native", c)

    def test_event_deletion_source_change_or_old_annotation_rejected(self):
        p, a, c, g, q = fixture()
        variants = []
        b = copy.deepcopy(a); b["events"].pop(); variants.append(b)
        b = copy.deepcopy(a); b["events"][0]["source"] = [1, 2]; variants.append(b)
        b = copy.deepcopy(a); b["video_provenance"]["native"]["annotation_source"] = "historical"; variants.append(b)
        b = copy.deepcopy(a); b["events"][0]["native"]["interval"] = [2, 6]; variants.append(b)
        for b in variants:
            with self.assertRaises(ValueError):
                validate_events(b, p, "e" * 64)

    def test_missing_event_is_retained_with_fixed_denominator(self):
        p, a, c, g, q = fixture()
        a["events"][1]["native"] = {"status": "not_visible", "reason": "object occluded", "interval": None}
        validate_events(a, p, "e" * 64)
        probs = np.eye(3)[None, :, None, :]
        result = summarize_live(probs, probs, [[0, 1], [2, 3], [4, 5]], [True] * 3, a, "native")
        self.assertEqual(result["expected_event_count"], 2)
        self.assertEqual(result["measured_event_count"], 1)
        self.assertFalse(result["all_events_measured"])
        self.assertEqual(result["events"][1]["status"], "not_visible")
        self.assertNotIn("signed_phase_frames", result["events"][1])


if __name__ == "__main__":
    unittest.main()
