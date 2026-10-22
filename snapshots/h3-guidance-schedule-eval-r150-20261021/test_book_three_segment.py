"""Actual early/late/split evidence and synthetic future final release only."""
import copy
import unittest
from common import ROOT, read, bound, expected_router
from finalize_composite import ARMS, verify_composite_record
import test_book_recovery as old_tests


class ThreeSegmentTests(unittest.TestCase):
    store = old_tests.BookRecoveryTests.store
    rejects = old_tests.BookRecoveryTests.rejects

    def setUp(self):
        old_tests.BookRecoveryTests.setUp(self)
        middle = ROOT / "actual/long_0039/middle_evidence"
        self.bindings = {a: read(ROOT / "runtime/long_0039" / (a + ".json")) for a in ARMS}
        self.runs = {a: read(ROOT / "actual/long_0039" / a / "GATE.json") for a in ARMS[:3]}
        b = self.bindings["global_weak"]
        owner = dict(pid=9002, identity=dict(uid=1004, start_ticks="456"),
                     port=b["port"], gpu_uuid=b["gpu_uuid"])
        r = copy.deepcopy(self.runs["early"])
        router = expected_router(self.case, {"id": "global_weak"})
        r.update(run_id=b["run_id"], role="global_weak", service_owner=owner,
                 producer_seal_sha256=b["producer_seal"]["sha256"],
                 actual_routed_steps_zero_based=b["steps_0based"], routed_blocks=1000,
                 alpha=router["alpha"], physical_query_window=[router["start_frame"], router["end_frame"]])
        r["video"] = {"file": b["remote_root"] + "/output/" + b["run_id"] + ".mp4"}
        r["sampler_timing"]["run_id"] = b["run_id"]
        self.runs["global_weak"] = r
        manifest = bound(middle / "MIGRATION_MANIFEST.json")
        segment = dict(schema="r149-fixed-schedule-segment-gate-v1", passed=True,
                       source_id="long_0039", segment_id="book_final_global_host41",
                       migration_manifest_sha256=manifest["sha256"], same_persistent_service=True,
                       phase_displacement=0, producer_seal_sha256=b["producer_seal"]["sha256"],
                       service_owner=owner, runs={"global_weak": r})
        segment_record = self.store("three_segment", segment)
        complete = dict(schema="r149-schedule-segment-completion-v1", passed=True,
                        segment_id=segment["segment_id"], migration_manifest_sha256=manifest["sha256"],
                        jobs=[r["run_id"]], remaining=[], GPU_released=True, service_owner=owner,
                        runtime_gate_sha256=segment_record["sha256"])
        release = dict(owner=owner, passed=True, process_absent=True, CUDA_allocation_absent=True,
                       cleanup=dict(pid=owner["pid"], process_absent=True, own_compute_absent=True))
        self.record.update(
            segment_count=3, prior_migration=self.record["migration"], prior_deployment=self.record["deployment"],
            migration=manifest, deployment=bound(middle / "MIGRATION_DEPLOYMENT.json"),
            middle_partial_release=bound(middle / "SECOND_PARTIAL_RELEASE.json"),
            middle_source_evidence=bound(middle / "SECOND_SOURCE_EVIDENCE.json"),
            middle_artifacts={k: bound(middle / k) for k in read(middle / "SECOND_PARTIAL_RELEASE.json")["evidence"]},
            bindings={a: self.store("three_binding_" + a, b) for a, b in self.bindings.items()},
            job_gates={a: self.store("three_gate_" + a, r) for a, r in self.runs.items()},
            segment_gate=segment_record, segment_complete=self.store("three_complete", complete),
            segment_release=self.store("three_release", release))

    def change(self, key, **values):
        item = read(self.record[key]["file"])
        item.update(values)
        self.record[key] = self.store(key + "_changed", item)
        if key == "middle_partial_release":
            dep = read(self.record["deployment"]["file"])
            dep["second_partial_release_sha256"] = self.record[key]["sha256"]
            self.record["deployment"] = self.store("changed_deployment", dep)

    def test_real_two_failed_segments_synthetic_final_passes(self):
        self.assertEqual(verify_composite_record(self.record, self.case), self.record)

    def test_missing_late_rejected(self):
        del self.record["job_gates"]["late"]
        self.rejects()

    def test_middle_cuda_unknown_cannot_be_true(self):
        self.change("middle_partial_release", CUDA_allocation_absent=True)
        self.rejects()

    def test_original_cuda_unknown_cannot_be_true(self):
        self.change("partial_release", CUDA_allocation_absent=True)
        self.rejects()

    def test_final_cuda_unknown_rejected(self):
        self.change("segment_release", CUDA_allocation_absent=None)
        self.rejects()

    def test_wrong_hash_rejected(self):
        self.record["job_gates"]["late"]["sha256"] = "0" * 64
        self.rejects()

    def test_same_service_claim_rejected(self):
        self.record["same_persistent_service"] = True
        self.rejects()

    def test_missing_generation_rejected(self):
        partial = read(self.record["middle_partial_release"]["file"])
        partial["registered_generations"].pop(next(iter(partial["registered_generations"])))
        self.change("middle_partial_release", registered_generations=partial["registered_generations"])
        self.rejects()

    def test_original_complete_claim_rejected(self):
        self.record["original_four_arm_COMPLETE"] = True
        self.rejects()

    def test_wrong_final_owner_rejected(self):
        self.change("segment_release", owner=self.runs["late"]["service_owner"])
        self.rejects()


if __name__ == "__main__":
    unittest.main()
