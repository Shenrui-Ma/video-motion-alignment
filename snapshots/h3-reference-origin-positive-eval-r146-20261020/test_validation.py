"""Small CPU tests of the completion chain; synthetic bytes, no inference."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import prepare_comparison as pc


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=pc.ROOT)
        self.root = Path(self.tmp.name)
        self.case = json.loads((pc.ROOT / "EVALUATION_MANIFEST.json").read_text())["cases"][0]
        self.video = self.root / "phase.mp4"
        self.video.write_bytes(b"synthetic video bytes")
        self.seal = self.root / "seal.json"
        self.seal.write_text("{}")
        r, g = self.case["R146"], self.case["geometry"]
        self.props = {"width": 1312, "height": 736, "nb_read_frames": "107", "avg_frame_rate": "24/1"}
        owner = {"pid": 123, "uid": 1004, "start_ticks": "456", "cmdline_sha256": "x"}
        self.gate = {
            "schema": "r132-reference-origin-runtime-gate-v1", "passed": True,
            "source_id": self.case["source_id"], "producer_seal_sha256": pc.bound(self.seal)["sha256"],
            "checks": {"actual_conditions": True}, "service_owner": owner,
            "runtime_profile": {"remote_root": r["remote_root"]},
            "runs": {"reference_origin": {
                "run_id": r["run_id"], "NFE": 20, "Euler_updates": 20, "routed_blocks": 450,
                "original_rope_table_blocks": 1000, "valid_frames": g["valid_frames"],
                "evaluation_crop_xywh": g["crop_xywh"],
                "video": {"file": r["remote_root"] + "/output/" + r["run_id"] + "_00001_.mp4",
                          "sha256": pc.bound(self.video)["sha256"], "properties": self.props}}}}
        self.complete = {
            "schema": "r132-one-output-completion-v1", "passed": True,
            "jobs": [r["run_id"]], "remaining": [], "GPU_released": True, "service_owner": owner}
        self.release = {
            "passed": True, "owner": owner, "process_absent": True, "CUDA_allocation_absent": True,
            "cleanup": {"pid": 123, "process_absent": True, "own_compute_absent": True}}

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        gate_path, complete_path, release_path = [self.root / (s + ".json") for s in ("gate", "complete", "release")]
        gate_path.write_text(json.dumps(self.gate))
        self.complete["runtime_gate_sha256"] = pc.bound(gate_path)["sha256"]
        complete_path.write_text(json.dumps(self.complete))
        release_path.write_text(json.dumps(self.release))
        with patch.object(pc, "inspect", return_value=self.props):
            return pc.validate(self.case, self.video, gate_path, complete_path, release_path, self.seal)

    def test_valid_chain(self):
        self.assertEqual(self.check()["run_id"], self.case["R146"]["run_id"])

    def test_failed_gate(self):
        self.gate["passed"] = False
        with self.assertRaisesRegex(ValueError, "Successful"):
            self.check()

    def test_wrong_video(self):
        self.video.write_bytes(b"other output")
        with self.assertRaisesRegex(ValueError, "SHA"):
            self.check()

    def test_wrong_generation(self):
        self.release["owner"] = dict(self.release["owner"], start_ticks="789")
        with self.assertRaisesRegex(ValueError, "generation"):
            self.check()

    def test_unreleased(self):
        self.release["cleanup"]["own_compute_absent"] = False
        with self.assertRaisesRegex(ValueError, "release"):
            self.check()

    def test_padding_domain(self):
        self.gate["runs"]["reference_origin"]["valid_frames"] = 107
        with self.assertRaisesRegex(ValueError, "domain"):
            self.check()

    def test_incomplete_calls(self):
        self.gate["runs"]["reference_origin"]["routed_blocks"] = 449
        with self.assertRaisesRegex(ValueError, "execution"):
            self.check()

    def test_wrong_seal(self):
        self.seal.write_text('{"modified":true}')
        with self.assertRaisesRegex(ValueError, "seal"):
            self.check()


if __name__ == "__main__":
    unittest.main()
