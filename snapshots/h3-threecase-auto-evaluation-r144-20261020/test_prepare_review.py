"""CPU-only fixtures for the producer receipt chain; no video rendering."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import prepare_review as review


class AutomaticBindingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.automatic = self.root / "automatic.mp4"
        self.automatic.write_bytes(b"local copy of the actual generated video")
        self.complete_path = self.root / "COMPLETE_REVIEW_HOLD.json"
        self.gate_path = self.root / "ONLINE_RUNTIME_GATE.json"
        self.exit_path = self.root / "ROOT_EXIT_RECEIPT.json"
        self.reference_path = self.root / "ROOT_EXIT_REFERENCE.json"
        self.case = {"source_id": "short_0358", "seed": 2026101701,
                     "geometry": {"width": 1312, "height": 736, "fps": 24,
                                  "sampled_frames": 107, "valid_frames": 105}}
        self.run = "r144_short_0358_seed2026101701_visible_only"
        self.remote = "/data4/cases/short_0358_cached_conditions"
        self.attempt = "root_drink_attempt4"
        self.owner = {"pid": 123, "identity": {"uid": 1004, "start_ticks": "456",
                                             "cmdline": "python service_entry.py"},
                      "root_attempt_token": self.attempt,
                      "command": ["python", "main.py", "--base-directory", self.remote]}
        self.properties = {"width": 1312, "height": 736, "avg_frame_rate": "24/1",
                           "nb_read_frames": "107"}
        self.gate = {
            "schema": "r86-online-runtime-gate-v1", "status": "pass", "passed": True,
            "cleanup_verified": True, "partial_batch": False, "verified_runs": [self.run],
            "cases": [{"run": self.run, "arm": "visible_only", "updates": 20, "observations": 20}],
            "service_record": copy.deepcopy(self.owner), "valid_frames": 105,
            "video": {"file": f"{self.remote}/output/{self.run}_00001_.mp4",
                      "sha256": review.bound(self.automatic)["sha256"],
                      "properties": copy.deepcopy(self.properties)},
            "cached_conditioning": {"actual_tensors_exact": True},
            "capacity_trial": {"normal_monitor_exit": True, "samples": 10},
        }
        self.release = {
            "passed": True, "service": copy.deepcopy(self.owner),
            "service_cleanup": {"pid": 123, "service_record": copy.deepcopy(self.owner),
                                "process_absent": True, "own_compute_absent": True},
            "observer_children": {"all_exact_generations_absent": True,
                                  "all_registered_CUDA_pids_absent": True},
            "capacity_monitor": {"exit_code": 0, "exact_generation_absent": True},
        }

    def write_chain(self, gate=None, release=None):
        self.gate_path.write_text(json.dumps(gate or self.gate))
        self.exit_path.write_text(json.dumps(release or self.release))
        self.complete_path.write_text(json.dumps({
            "passed": True, "run_id": self.run, "no_followup_submission": True,
            "gate_sha256": review.bound(self.gate_path)["sha256"],
        }))
        self.reference_path.write_text(json.dumps({
            "file": f"{self.remote}/audit/{self.attempt}/ROOT_EXIT_RECEIPT.json",
            "sha256": review.bound(self.exit_path)["sha256"],
        }))

    def validate(self, properties=None):
        with patch.object(review, "inspect", return_value=properties or self.properties):
            return review.validate_automatic(self.case, self.automatic, self.complete_path,
                                             self.gate_path, self.exit_path)

    def test_complete_cached_chain_accepts_local_copy_and_binds_every_receipt(self):
        self.write_chain()
        result = self.validate()
        self.assertTrue(result["verified_before_render"])
        self.assertEqual(result["run_id"], self.run)
        for key, path in (("completion", self.complete_path), ("runtime_gate", self.gate_path),
                          ("root_exit", self.exit_path), ("exit_reference", self.reference_path)):
            self.assertEqual(result[key], review.bound(path))

    def test_non_cached_158_frame_case_uses_registered_geometry(self):
        self.case.update(source_id="long_0059")
        self.case["geometry"].update(sampled_frames=158, valid_frames=144)
        self.run = "r144_long_0059_seed2026101701_visible_only"
        self.gate.update(verified_runs=[self.run], valid_frames=144)
        self.gate["cases"][0]["run"] = self.run
        self.gate["video"]["file"] = f"{self.remote}/output/{self.run}_00001_.mp4"
        self.properties["nb_read_frames"] = "158"
        self.gate["video"]["properties"] = copy.deepcopy(self.properties)
        del self.gate["cached_conditioning"], self.gate["capacity_trial"]
        del self.release["capacity_monitor"]
        self.write_chain()
        self.assertTrue(self.validate()["verified_before_render"])

    def test_rejects_failed_partial_wrong_run_or_incomplete_gate(self):
        mutations = [
            lambda g: g.update(passed=False), lambda g: g.update(status="failed"),
            lambda g: g.update(partial_batch=True), lambda g: g.update(cleanup_verified=False),
            lambda g: g.update(verified_runs=["another_run"]),
            lambda g: g["cases"][0].update(run="another_run"),
            lambda g: g["cases"][0].update(observations=19),
            lambda g: g["cached_conditioning"].update(actual_tensors_exact=False),
            lambda g: g["capacity_trial"].update(normal_monitor_exit=False),
        ]
        for mutate in mutations:
            gate = copy.deepcopy(self.gate)
            mutate(gate)
            self.write_chain(gate=gate)
            with self.subTest(gate=gate), self.assertRaises(ValueError):
                self.validate()

    def test_rejects_video_hash_and_exact_geometry_mismatches(self):
        self.write_chain()
        self.automatic.write_bytes(b"another output")
        with self.assertRaisesRegex(ValueError, "SHA"):
            self.validate()
        self.automatic.write_bytes(b"local copy of the actual generated video")
        for key, value in (("width", 1280), ("height", 720),
                           ("nb_read_frames", "105"), ("avg_frame_rate", "25/1")):
            info = dict(self.properties, **{key: value})
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "geometry"):
                self.validate(info)
            gate = copy.deepcopy(self.gate)
            gate["video"]["properties"] = info
            self.write_chain(gate=gate)
            with self.subTest(gate_key=key), self.assertRaisesRegex(ValueError, "gate automatic geometry"):
                self.validate()
            self.write_chain()
        self.gate["valid_frames"] = 106
        self.write_chain()
        with self.assertRaisesRegex(ValueError, "valid-frame"):
            self.validate()

    def test_rejects_unrelated_or_escaping_video_and_missing_exit_reference(self):
        for filename in (
            f"{self.remote}/output/another_run_00001_.mp4",
            f"{self.remote}/other/{self.run}_00001_.mp4",
            f"{self.remote}/output/../{self.run}_00001_.mp4",
        ):
            gate = copy.deepcopy(self.gate)
            gate["video"]["file"] = filename
            self.write_chain(gate=gate)
            with self.subTest(filename=filename), self.assertRaisesRegex(ValueError, "outside"):
                self.validate()
        self.write_chain()
        self.reference_path.unlink()
        with self.assertRaises(FileNotFoundError):
            self.validate()

    def test_rejects_failed_release_mixed_owner_and_unreleased_children(self):
        mutations = [
            lambda r: r.update(passed=False), lambda r: r["service"].update(pid=999),
            lambda r: r["service_cleanup"].update(own_compute_absent=False),
            lambda r: r["service_cleanup"]["service_record"]["identity"].update(start_ticks="789"),
            lambda r: r["observer_children"].update(all_registered_CUDA_pids_absent=False),
            lambda r: r["capacity_monitor"].update(exit_code=1),
        ]
        for mutate in mutations:
            release = copy.deepcopy(self.release)
            mutate(release)
            self.write_chain(release=release)
            with self.subTest(release=release), self.assertRaises(ValueError):
                self.validate()

    def test_rejects_tampered_gate_release_and_wrong_attempt_reference(self):
        self.write_chain()
        self.gate_path.write_text(self.gate_path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "does not bind"):
            self.validate()
        self.write_chain()
        self.exit_path.write_text(self.exit_path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "does not bind"):
            self.validate()
        self.write_chain()
        reference = json.loads(self.reference_path.read_text())
        reference["file"] = reference["file"].replace(self.attempt, "root_old_attempt")
        self.reference_path.write_text(json.dumps(reference))
        with self.assertRaisesRegex(ValueError, "does not bind"):
            self.validate()

    def test_failed_receipt_stops_main_before_ffprobe_or_render(self):
        self.write_chain()
        self.complete_path.write_text(json.dumps({"passed": False}))
        binding = self.root / "binding.json"
        binding.write_text("{}")
        case = dict(self.case, input_binding=str(binding),
                    input_binding_sha256=review.bound(binding)["sha256"])
        (self.root / "EVALUATION_PLAN.json").write_text(json.dumps({"cases": [case]}))
        argv = ["prepare_review.py", "--case", "short_0358", "--automatic", str(self.automatic),
                "--run-receipt", str(self.complete_path), "--runtime-gate", str(self.gate_path)]
        with patch.object(review, "ROOT", self.root), patch("sys.argv", argv), \
                patch.object(review, "inspect") as probe, patch.object(review.subprocess, "run") as render:
            with self.assertRaisesRegex(ValueError, "Completed R144"):
                review.main()
            probe.assert_not_called()
            render.assert_not_called()
            self.assertFalse((self.root / "review").exists())


if __name__ == "__main__":
    unittest.main()
