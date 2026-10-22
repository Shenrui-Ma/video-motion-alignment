"""CPU-only binding and process-generation regression tests; no model import."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "audit"), str(ROOT / "scripts")]
import bind_automatic
import prepare_cache
import run_batch
from common import read


class ContractTests(unittest.TestCase):
    def test_exactly_three_automatic_targets_no_source_or_baseline_job(self):
        plan = read(ROOT / "configs/PLAN.json")
        self.assertEqual(plan["jobs"], [{"case": name, "role": "automatic"} for name in prepare_cache.CASES])
        for name in plan["groups"]:
            self.assertTrue(read(ROOT / "cases" / name / "INPUTS.json")["source_cache"])

    def test_book_completed_source_promoted_from_uncached_original(self):
        old = read(ROOT / "configs/evidence/long_0039_HISTORICAL_INPUTS.json")
        self.assertIsNone(old["source_cache"])
        new = read(ROOT / "cases/long_0039/INPUTS.json")
        report = read(ROOT / "cases/long_0039/tracks/source/REPORT.json")
        self.assertEqual(new["source_cache"]["tracks_sha256"], report["tracks_sha256"])

    def test_real_source_reports_match_same_official_protocol(self):
        for name in prepare_cache.CASES:
            report = read(ROOT / "cases" / name / "tracks/source/REPORT.json")
            old = read(ROOT / "configs/evidence" / (name + "_HISTORICAL_INPUTS.json"))
            prepare_cache.source_report_valid(report, old)

    def test_source_wrong_checkpoint_time_domain_or_grid_rejected(self):
        old = read(ROOT / "configs/evidence/long_0059_HISTORICAL_INPUTS.json")
        report = read(ROOT / "cases/long_0059/tracks/source/REPORT.json")
        for key, wrong in [("checkpoint_sha256", "wrong"), ("effective_frame_count", 158),
                           ("tracker", dict(prepare_cache.TRACKER, grid_size=12)),
                           ("selection_sha256", "wrong")]:
            bad = copy.deepcopy(report)
            bad[key] = wrong
            with self.assertRaises(AssertionError):
                prepare_cache.source_report_valid(bad, old)

    def gate(self):
        geometry = {"width": 1312, "height": 736, "sampled_frames": 107, "valid_frames": 105}
        service = {"pid": 123, "identity": {"uid": 1004, "start_ticks": "200", "cmdline": "case main.py"}}
        gate = {"schema": "r86-online-runtime-gate-v1", "passed": True, "status": "pass",
                    "cleanup_verified": True, "partial_batch": False, "existing_case_Native_reused": True,
                    "valid_frames": 105, "service_record": service,
                    "cases": [{"run": "r144_short_0358_seed2026101701_visible_only",
                                "arm": "visible_only", "updates": 20}],
                    "video": {"file": "/data4/researcher/h3_runs/threecase_auto_r144_20261020/cases/short_0358/output/actual.mp4",
                               "sha256": "test", "properties": {"width": 1312, "height": 736,
                                                             "avg_frame_rate": "24/1", "nb_read_frames": "107"}}}
        release = {"passed": True, "service": copy.deepcopy(service),
                       "service_cleanup": {"process_absent": True, "own_compute_absent": True},
                       "observer_children": {"all_exact_generations_absent": True,
                                              "all_registered_CUDA_pids_absent": True}}
        return gate, release, geometry

    def test_existing_online_gate_and_exact_exit_receipt_accepted(self):
        gate, release, geometry = self.gate()
        self.assertEqual(bind_automatic.check_gate(gate, release, "short_0358", geometry), gate["video"])

    def test_gate_wrong_case_or_domain_rejected(self):
        gate, release, geometry = self.gate()
        for key, value in [("valid_frames", 107), ("passed", False)]:
            bad = copy.deepcopy(gate)
            bad[key] = value
            with self.assertRaises(AssertionError):
                bind_automatic.check_gate(bad, release, "short_0358", geometry)
        with self.assertRaises(AssertionError):
            bind_automatic.check_gate(gate, release, "long_0039", geometry)

    def test_reused_pid_exit_receipt_is_not_old_generation(self):
        gate, release, geometry = self.gate()
        release["service"]["identity"]["start_ticks"] = "201"
        with self.assertRaises(AssertionError):
            bind_automatic.check_gate(gate, release, "short_0358", geometry)

    def test_incomplete_observer_release_rejected(self):
        gate, release, geometry = self.gate()
        release["observer_children"]["all_registered_CUDA_pids_absent"] = False
        with self.assertRaises(AssertionError):
            bind_automatic.check_gate(gate, release, "short_0358", geometry)

    def test_cleanup_does_not_wait_for_or_signal_reused_pid(self):
        old = {"pid": 123, "uid": 1004, "start_ticks": "200", "cmdline_sha256": "old"}
        newer = {"pid": 123, "uid": 1004, "start_ticks": "201", "cmdline_sha256": "new"}
        child = Mock(pid=123, returncode=0)
        child.poll.return_value = 0
        with patch.object(run_batch, "cuda_process_rows", return_value=[newer]), \
             patch.object(run_batch, "identity", return_value=newer):
            receipt = run_batch.cleanup(child, old)
        self.assertTrue(receipt["process_absent"] and receipt["CUDA_absent"])
        child.terminate.assert_not_called()
        child.kill.assert_not_called()

    def test_cleanup_rejects_live_old_generation(self):
        old = {"pid": 123, "uid": 1004, "start_ticks": "200", "cmdline_sha256": "old"}
        child = Mock(pid=123, returncode=0)
        child.poll.return_value = 0
        with patch.object(run_batch, "cuda_process_rows", return_value=[]), \
             patch.object(run_batch, "identity", return_value=old), \
             self.assertRaises(AssertionError):
            run_batch.cleanup(child, old)
        child.terminate.assert_not_called()
        child.kill.assert_not_called()

    def test_torch_not_imported(self):
        self.assertNotIn("torch", sys.modules)


if __name__ == "__main__":
    unittest.main()
