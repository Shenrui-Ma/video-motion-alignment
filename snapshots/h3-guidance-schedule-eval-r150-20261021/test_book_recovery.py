"""Real failed prefix plus synthetic future target receipts; no output-completion claim."""
import copy
import tempfile
import unittest
from pathlib import Path
from common import ROOT, read, write, bound, expected_router
from finalize_composite import ARMS, SCHEMA, verify_composite_record


class BookRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "audit")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.prefix = ROOT / "actual/long_0039/prefix_evidence"
        self.case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]
                         if c["source_id"] == "long_0039")
        self.bindings = {a: read(ROOT / "runtime/long_0039" / (a + ".json")) for a in ARMS}
        self.bindings["global_weak"] = read(ROOT / "audit/binding_history/long_0039/70023888e520ac448b9bab5ec3d2324677bb61a0584ef1ad375d7db9fb1842f8/global_weak.json")
        self.runs = {"early": read(ROOT / "actual/long_0039/early/GATE.json")}
        target = self.bindings["global_weak"]
        self.owner = {"pid": 9001, "identity": {"uid": 1004, "start_ticks": "123"},
                      "port": target["port"], "gpu_uuid": target["gpu_uuid"]}
        for arm in ARMS[1:]:
            r = copy.deepcopy(self.runs["early"])
            b, router = self.bindings[arm], expected_router(self.case, {"id": arm})
            r.update(run_id=b["run_id"], role=arm, service_owner=self.owner,
                     producer_seal_sha256=b["producer_seal"]["sha256"],
                     actual_routed_steps_zero_based=b["steps_0based"],
                     routed_blocks=50 * len(b["steps_0based"]), alpha=router["alpha"],
                     physical_query_window=[router["start_frame"], router["end_frame"]])
            r["video"] = {"file": b["remote_root"] + "/output/" + b["run_id"] + ".mp4"}
            r["sampler_timing"]["run_id"] = b["run_id"]
            self.runs[arm] = r
        mfile = bound(self.prefix / "MIGRATION_MANIFEST.json")
        manifest = read(mfile["file"])
        seg = dict(schema="r149-fixed-schedule-segment-gate-v1", passed=True, source_id="long_0039",
                   segment_id="book_late_split_global_host41", migration_manifest_sha256=mfile["sha256"],
                   same_persistent_service=True, phase_displacement=0,
                   producer_seal_sha256=target["producer_seal"]["sha256"],
                   service_owner=self.owner, runs={a: self.runs[a] for a in ARMS[1:]})
        segfile = self.store("segment", seg)
        complete = dict(schema="r149-schedule-segment-completion-v1", passed=True,
                        segment_id=seg["segment_id"], migration_manifest_sha256=mfile["sha256"],
                        jobs=[self.runs[a]["run_id"] for a in ARMS[1:]], remaining=[],
                        GPU_released=True, service_owner=self.owner, runtime_gate_sha256=segfile["sha256"])
        release = dict(owner=self.owner, passed=True, process_absent=True, CUDA_allocation_absent=True,
                       cleanup=dict(pid=self.owner["pid"], process_absent=True, own_compute_absent=True))
        self.record = dict(schema=SCHEMA, passed=True, source_id="long_0039",
                           same_persistent_service=False, original_four_arm_COMPLETE=False,
                           migration=mfile, deployment=bound(self.prefix / "MIGRATION_DEPLOYMENT.json"),
                           partial_release=bound(self.prefix / "PREFIX_PARTIAL_RELEASE.json"),
                           segment_gate=segfile, segment_complete=self.store("complete", complete),
                           segment_release=self.store("release", release),
                           bindings={a: self.store("binding_" + a, b) for a, b in self.bindings.items()},
                           job_gates={a: self.store("gate_" + a, r) for a, r in self.runs.items()},
                           partial_artifacts={"source_evidence": bound(self.prefix / "SOURCE_EVIDENCE.json"),
                                              **{k: bound(self.prefix / k)
                                                 for k in manifest["failure"]["source_evidence"]}})

    def store(self, name, value):
        path = self.folder / (name + ".json")
        write(path, value)
        return bound(path)

    def change(self, key, fn):
        j = read(self.record[key]["file"])
        fn(j)
        self.record[key] = self.store(key + "_changed", j)
        if key == "partial_release":
            d = read(self.record["deployment"]["file"])
            d["prefix_partial_release_sha256"] = self.record[key]["sha256"]
            self.record["deployment"] = self.store("deployment_changed", d)

    def rejects(self):
        with self.assertRaises(ValueError):
            verify_composite_record(self.record, self.case)

    def test_real_prefix_synthetic_target_passes(self):
        self.assertEqual(verify_composite_record(self.record, self.case), self.record)

    def test_missing_role_rejected(self):
        del self.record["job_gates"]["late"]
        self.rejects()

    def test_old_cuda_unknown_must_not_become_true(self):
        self.change("partial_release", lambda r: r.update(CUDA_allocation_absent=True))
        self.rejects()

    def test_new_cuda_unknown_rejected(self):
        self.change("segment_release", lambda r: r.update(CUDA_allocation_absent=None))
        self.rejects()

    def test_same_service_claim_rejected(self):
        self.record["same_persistent_service"] = True
        self.rejects()

    def test_wrong_sha_rejected(self):
        self.record["job_gates"]["early"]["sha256"] = "0" * 64
        self.rejects()

    def test_original_batch_completion_claim_rejected(self):
        self.change("partial_release", lambda r: r.update(original_four_arm_COMPLETE=True))
        self.rejects()

    def test_wrong_target_owner_rejected(self):
        self.change("segment_release", lambda r: r.update(owner=self.runs["early"]["service_owner"]))
        self.rejects()

    def test_missing_cleanup_failure_rejected(self):
        key = next(k for k in self.record["partial_artifacts"] if k.endswith("/CLEANUP_FAILURE.json"))
        del self.record["partial_artifacts"][key]
        self.rejects()

    def test_target_cannot_omit_late(self):
        self.change("segment_gate", lambda r: r["runs"].pop("late"))
        self.rejects()


if __name__ == "__main__":
    unittest.main()
