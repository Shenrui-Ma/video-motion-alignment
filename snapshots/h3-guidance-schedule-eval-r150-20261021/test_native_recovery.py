import copy
import unittest

from common import ROOT, read, bound
from finalize_native_recovery import validate_binding_set, validate_prefix, ROLES
from finalize_parallel import validate_segment


class NativeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.refs = read(ROOT / "audit/FIREFLY_NATIVE_RECOVERY_BINDING.json")
        self.manifest = read(self.refs["migration"]["file"])
        self.deployment = read(self.refs["deployment"]["file"])
        self.partial = read(self.refs["partial_release"]["file"])
        self.evidence = read(self.refs["source_evidence"]["file"])
        self.case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]
                         if c["source_id"] == "firefly06")
        self.bindings = {r: read(ROOT / "runtime/firefly06" / (r + ".json")) for r in ROLES}
        self.native = read(ROOT / "actual/firefly06/native/GATE.json")
        self.record = {k: self.refs[k] for k in
                       ("migration", "deployment", "partial_release", "source_evidence")}
        self.record.update(
            bindings={r: bound(ROOT / "runtime/firefly06" / (r + ".json")) for r in ROLES},
            job_gates={"native": bound(ROOT / "actual/firefly06/native/GATE.json")},
            prefix_artifacts={r: bound(ROOT / "actual/firefly06/native_prefix_evidence" / r)
                              for r in self.manifest["source_evidence"]})

    def prefix(self):
        validate_prefix(self.manifest, self.deployment, self.partial, self.evidence,
                        self.record, self.native)

    def test_actual_native_release_and_new_binding(self):
        validate_binding_set(self.manifest, self.deployment, self.record,
                             self.case, self.bindings)
        self.prefix()

    def test_missing_role_rejected(self):
        del self.bindings["fixed"]
        with self.assertRaises(ValueError):
            validate_binding_set(self.manifest, self.deployment, self.record,
                                 self.case, self.bindings)

    def test_wrong_seal_rejected(self):
        self.bindings["early"]["producer_seal"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            validate_binding_set(self.manifest, self.deployment, self.record,
                                 self.case, self.bindings)

    def test_partial_cannot_claim_six_complete(self):
        self.partial["original_full_COMPLETE"] = True
        with self.assertRaises(ValueError):
            self.prefix()

    def test_cuda_unknown_not_accepted_for_this_normal_exit(self):
        self.partial["CUDA_allocation_absent"] = None
        with self.assertRaises(ValueError):
            self.prefix()

    def test_wrong_native_hash_rejected(self):
        self.record["job_gates"]["native"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            self.prefix()

    def test_recovery_exact_partition_and_owner(self):
        segment = self.manifest["segments"]["recovery"]
        deployed = self.deployment["segments"]["recovery"]
        owner = {"pid": 999, "identity": {"start_ticks": "100"}, "gpu_uuid": "test-only"}
        runs = {r: {"service_owner": owner, "role": r} for r in segment["roles"]}
        gate = dict(schema=segment["aggregate_schema"], passed=True, source_id="firefly06",
                    segment_id=segment["segment_id"],
                    migration_manifest_sha256=self.record["migration"]["sha256"],
                    producer_seal_sha256=deployed["producer_seal_sha256"],
                    phase_displacement=0, same_persistent_service=True,
                    service_owner=owner, runs=runs)
        complete = dict(schema=segment["COMPLETE_schema"], passed=True,
                        segment_id=segment["segment_id"], jobs=segment["run_ids"],
                        migration_manifest_sha256=self.record["migration"]["sha256"],
                        remaining=[], GPU_released=True, runtime_gate_sha256="test-gate",
                        service_owner=owner)
        release = dict(passed=True, owner=owner, process_absent=True,
                       CUDA_allocation_absent=True,
                       cleanup=dict(pid=999, process_absent=True, own_compute_absent=True))
        args = (segment, deployed, runs, gate, complete, release, "test-gate",
                self.record["migration"]["sha256"])
        validate_segment(*args, source_id="firefly06")
        bad = copy.deepcopy(complete)
        bad["jobs"] = bad["jobs"][:-1]
        with self.assertRaises(ValueError):
            validate_segment(segment, deployed, runs, gate, bad, release, "test-gate",
                             self.record["migration"]["sha256"], source_id="firefly06")


if __name__ == "__main__":
    unittest.main()
