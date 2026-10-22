"""CPU-only acceptance/rejection tests, no real generation or rendering."""
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
        self.case = pc.read(pc.ROOT / "EVALUATION_MANIFEST.json")["cases"][0]
        c, g = self.case, self.case["geometry"]
        self.video = self.root / "combined.mp4"
        self.video.write_bytes(b"synthetic video")
        self.seal = self.root / "seal.json"
        self.seal.write_text("{}")
        self.props = {"width": 1312, "height": 736, "nb_read_frames": "107", "avg_frame_rate": "24/1"}
        self.b = {"status": "READY", "source_id": c["source_id"], "role": "fixed_phase",
            "run_id": c["R148"]["run_id"], "historical_prompt_sha256": c["prompt_sha256"],
            "historical_noise_sha256": c["historical_initial_noise"]["sha256"],
            "historical_fixed_graph_sha256": c["historical_runs"]["fixed"]["graph"]["sha256"],
            "producer_seal": pc.bound(self.seal), "remote_root": "/remote/r148/case",
            "gate_schema": "r148-fixed-phase-runtime-gate-v1", "complete_schema": "test-complete-v9",
            "receipt_files": {"gate": "different/new_gate.json", "complete": "a/done.json", "release": "a/exit.json"},
            "output_relative_file": "output/explicit_filename.mp4",
            "expected_run_fields": {"NFE": 20, "Euler_updates": 20, "routed_blocks": 450}}
        owner = {"pid": 1, "uid": 1004, "start_ticks": "123", "cmdline_sha256": "test"}
        self.gate = {"schema": self.b["gate_schema"], "passed": True, "source_id": c["source_id"],
            "producer_seal_sha256": self.b["producer_seal"]["sha256"], "checks": {"scientific_checks": True},
            "service_owner": owner, "runtime_profile": {"remote_root": self.b["remote_root"]},
            "runs": {"fixed_phase": {"run_id": self.b["run_id"], **self.b["expected_run_fields"],
                "valid_frames": g["valid_frames"], "evaluation_crop_xywh": g["crop_xywh"],
                "video": {"file": self.b["remote_root"] + "/" + self.b["output_relative_file"],
                          "sha256": pc.bound(self.video)["sha256"], "properties": self.props}}}}
        self.complete = {"schema": self.b["complete_schema"], "passed": True, "jobs": [self.b["run_id"]],
                         "remaining": [], "GPU_released": True, "service_owner": owner}
        self.release = {"passed": True, "owner": owner, "process_absent": True, "CUDA_allocation_absent": True,
                        "cleanup": {"pid": 1, "process_absent": True, "own_compute_absent": True}}

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        gate, complete, release, binding = [self.root / name for name in ("new_gate.json", "done.json", "exit.json", "binding.json")]
        gate.write_text(json.dumps(self.gate))
        self.complete["runtime_gate_sha256"] = pc.bound(gate)["sha256"]
        for p, j in ((complete, self.complete), (release, self.release), (binding, self.b)):
            p.write_text(json.dumps(j))
        with patch.object(pc, "inspect", return_value=self.props):
            return pc.validate(self.case, self.video, gate, complete, release, binding)

    def test_explicit_new_schema_and_filenames(self):
        self.assertEqual(self.check()["run_id"], self.b["run_id"])

    def test_pending_contract_rejected(self):
        self.b["status"] = "PENDING_PRODUCER_FREEZE"
        with self.assertRaisesRegex(ValueError, "pending"):
            self.check()

    def test_wrong_historical_noise(self):
        self.b["historical_noise_sha256"] = "other"
        with self.assertRaisesRegex(ValueError, "scientific"):
            self.check()

    def test_wrong_video(self):
        self.video.write_bytes(b"different")
        with self.assertRaisesRegex(ValueError, "video SHA"):
            self.check()

    def test_failed_gate(self):
        self.gate["passed"] = False
        with self.assertRaisesRegex(ValueError, "gate"):
            self.check()

    def test_wrong_owner(self):
        self.release["owner"] = dict(self.release["owner"], start_ticks="124")
        with self.assertRaisesRegex(ValueError, "generation"):
            self.check()

    def test_unreleased(self):
        self.release["cleanup"]["own_compute_absent"] = False
        with self.assertRaisesRegex(ValueError, "release"):
            self.check()

    def test_wrong_valid_domain(self):
        self.gate["runs"]["fixed_phase"]["valid_frames"] = 107
        with self.assertRaisesRegex(ValueError, "domain"):
            self.check()

    def test_incomplete_actual_calls(self):
        self.gate["runs"]["fixed_phase"]["routed_blocks"] = 449
        with self.assertRaisesRegex(ValueError, "Execution"):
            self.check()

    def test_all_five_case_domains_and_scores(self):
        cases = pc.read(pc.ROOT / "EVALUATION_MANIFEST.json")["cases"]
        self.assertEqual([c["geometry"]["valid_frames"] for c in cases], [98, 105, 106, 144, 141])
        self.assertEqual([len(c["events"]) for c in cases], [3, 3, 5, 3, 0])
        self.assertTrue(all(c["official_MF"]["fixed_phase"] is None for c in cases))
        self.assertTrue(all(0 <= c["official_MF"][r]["score"] <= 1 for c in cases[:4] for r in ("native", "fixed")))
        sam = cases[4]
        self.assertIsNone(sam["official_MF"]["native"])
        self.assertIsNone(sam["official_MF"]["fixed"])
        self.assertEqual(sam["geometry"]["crop_xywh"], [0, 0, 1312, 736])
        self.assertEqual(sam["historical_runs"]["fixed"]["router_node_50"]["inputs"]["start_frame"], 50)
        self.assertEqual(sam["historical_runs"]["fixed"]["router_node_50"]["inputs"]["end_frame"], 65)
        self.assertEqual(sam["historical_window_diagnostics"]["windows"][0]["native"]["0.3"], 13)
        self.assertEqual(sam["historical_window_diagnostics"]["windows"][0]["fixed"]["0.3"], 1)


if __name__ == "__main__":
    unittest.main()
