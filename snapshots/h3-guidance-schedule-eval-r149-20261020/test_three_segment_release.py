"""Real first two segments; synthetic future global, confined to temporary fixtures."""
import copy
import tempfile
import unittest
from pathlib import Path
from common import ROOT, read, write, bound, expected_router
from finalize_composite import ARMS, SCHEMA, verify_composite_record, evidence_records
from hardware_prefix import hardware_files


class ThreeSegmentReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "audit")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]
                         if c["source_id"] == "short_0358")
        prefix = ROOT / "audit/hardware_recovery/prefix_evidence"
        middle = ROOT / "audit/three_segment_release/split_evidence"
        prior = read(prefix / "MIGRATION_MANIFEST.json")
        migration = bound(middle / "MIGRATION_MANIFEST.json")
        bindings = {a: read(ROOT / "runtime/short_0358" / (a + ".json")) for a in ARMS}
        self.runs = {a: read(ROOT / "actual/short_0358" / a / "GATE.json") for a in ARMS[:3]}
        b = bindings["global_weak"]
        self.owner = {"pid": 9009, "identity": {"uid": 1004, "start_ticks": "9999"},
                      "port": b["port"], "gpu_uuid": b["gpu_uuid"]}
        run = copy.deepcopy(self.runs["split"])
        router = expected_router(self.case, {"id": "global_weak"})
        run.update(run_id=b["run_id"], role="global_weak", service_owner=self.owner,
                   producer_seal_sha256=b["producer_seal"]["sha256"],
                   actual_routed_steps_zero_based=b["steps_0based"], routed_blocks=1000,
                   alpha=router["alpha"], physical_query_window=[router["start_frame"], router["end_frame"]])
        run["video"] = {"file": b["remote_root"] + "/output/" + b["run_id"] + ".mp4"}
        run["sampler_timing"]["run_id"] = b["run_id"]
        self.runs["global_weak"] = run
        segment = {"schema": "r149-fixed-schedule-segment-gate-v1", "passed": True,
                   "source_id": "short_0358", "segment_id": "drink_final_global_host41",
                   "migration_manifest_sha256": migration["sha256"], "phase_displacement": 0,
                   "same_persistent_service": True, "producer_seal_sha256": b["producer_seal"]["sha256"],
                   "runs": {"global_weak": run}, "service_owner": self.owner}
        gate = self.store("segment", segment)
        complete = {"schema": "r149-schedule-segment-completion-v1", "passed": True,
                    "segment_id": segment["segment_id"], "migration_manifest_sha256": migration["sha256"],
                    "jobs": [b["run_id"]], "remaining": [], "GPU_released": True,
                    "service_owner": self.owner, "runtime_gate_sha256": gate["sha256"]}
        release = {"owner": self.owner, "passed": True, "process_absent": True, "CUDA_allocation_absent": True,
                   "cleanup": {"pid": self.owner["pid"], "process_absent": True, "own_compute_absent": True}}
        self.record = {
            "schema": SCHEMA, "passed": True, "source_id": "short_0358", "segment_count": 3,
            "same_persistent_service": False, "original_four_arm_COMPLETE": False,
            "recovery_two_arm_COMPLETE": False,
            "migration": migration, "deployment": bound(middle / "MIGRATION_DEPLOYMENT.json"),
            "prior_migration": bound(prefix / "MIGRATION_MANIFEST.json"),
            "prior_deployment": bound(prefix / "MIGRATION_DEPLOYMENT.json"),
            "partial_release": bound(prefix / "PREFIX_PARTIAL_RELEASE.json"),
            "partial_artifacts": {k: bound(prefix / p) for k, p in hardware_files(prior).items()},
            "split_partial_release": bound(middle / "SPLIT_PARTIAL_RELEASE.json"),
            "split_source_evidence": bound(middle / "SPLIT_SOURCE_EVIDENCE.json"),
            "split_artifacts": {p: bound(middle / p) for p in read(middle / "SPLIT_SOURCE_EVIDENCE.json")["files"]},
            "segment_gate": gate, "segment_complete": self.store("complete", complete),
            "segment_release": self.store("release", release),
            "bindings": {a: bound(ROOT / "runtime/short_0358" / (a + ".json")) for a in ARMS},
            "job_gates": {a: self.store("gate_" + a, r) for a, r in self.runs.items()}}

    def store(self, name, data):
        path = self.folder / (name + ".json")
        write(path, data)
        return bound(path)

    def change(self, key, fn):
        data = read(self.record[key]["file"])
        fn(data)
        self.record[key] = self.store(key + "_changed", data)

    def rejects(self):
        with self.assertRaises(ValueError):
            verify_composite_record(self.record, self.case)

    def test_actual_two_prefixes_and_synthetic_final_accept(self):
        self.assertEqual(verify_composite_record(self.record, self.case), self.record)
        self.assertIsNone(read(self.record["partial_release"]["file"])["CUDA_allocation_absent"])
        self.assertTrue(read(self.record["split_partial_release"]["file"])["CUDA_allocation_absent"])

    def test_all_split_evidence_is_in_mf_export(self):
        records = evidence_records(self.record)
        self.assertIn("prior_migration", records)
        self.assertIn("split_processes/cleanup.json", records)
        self.assertIn("split_source_evidence", records)

    def test_missing_role_reject(self):
        del self.record["job_gates"]["split"]
        self.rejects()

    def test_same_service_claim_reject(self):
        self.record["same_persistent_service"] = True
        self.rejects()

    def test_old_four_arm_complete_claim_reject(self):
        self.record["original_four_arm_COMPLETE"] = True
        self.rejects()

    def test_middle_two_arm_complete_claim_reject(self):
        self.record["recovery_two_arm_COMPLETE"] = True
        self.rejects()

    def test_wrong_split_gate_sha_reject(self):
        self.record["job_gates"]["split"]["sha256"] = "0" * 64
        self.rejects()

    def test_wrong_deployment_seal_reject(self):
        self.change("deployment", lambda d: d["segments"]["host41_global"].update(producer_seal_sha256="0" * 64))
        self.rejects()

    def test_forged_prefix_cuda_success_reject(self):
        self.change("partial_release", lambda d: d.update(CUDA_allocation_absent=True))
        self.rejects()

    def test_middle_cuda_unknown_reject(self):
        self.change("split_partial_release", lambda d: d.update(CUDA_allocation_absent=None))
        self.rejects()

    def test_final_cuda_unknown_reject(self):
        self.change("segment_release", lambda d: d.update(CUDA_allocation_absent=None))
        self.rejects()

    def test_missing_middle_cleanup_reject(self):
        del self.record["split_artifacts"]["processes/cleanup.json"]
        self.rejects()

    def test_wrong_middle_original_bytes_reject(self):
        self.record["split_artifacts"]["processes/cleanup.json"] = self.store("wrong_cleanup", {})
        self.rejects()

    def test_final_release_cannot_use_middle_owner(self):
        self.change("segment_release", lambda d: d.update(owner=self.runs["split"]["service_owner"]))
        self.rejects()

    def test_final_segment_cannot_include_split(self):
        self.change("segment_gate", lambda d: d["runs"].update(split=self.runs["split"]))
        self.rejects()

    def test_wrong_selected_media_reject(self):
        with self.assertRaises(ValueError):
            verify_composite_record(self.record, self.case, {}, self.runs["split"])


if __name__ == "__main__":
    unittest.main()
