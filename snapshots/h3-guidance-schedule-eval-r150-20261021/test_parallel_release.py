"""Synthetic receipt tests against the real frozen Sam07 partition."""
import copy
import unittest
from common import ROOT, read, bound
from finalize_parallel import (validate_partition, validate_segment, verify_parallel_record,
                               segment_evidence, PARTITION)
from test_dance_intake import DanceIntakeTests


class ParallelReleaseTests(unittest.TestCase):
    def setUp(self):
        self.case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]
                         if c["source_id"] == "sam07")
        self.bindings = {r: read(ROOT / "runtime/sam07" / (r + ".json"))
                         for roles in PARTITION.values() for r in roles}
        binding = self.bindings["split"]
        self.record = {"migration": binding["migration_manifest"],
                       "deployment": binding["migration_deployment"],
                       "base_migration": self.bindings["native"]["migration_manifest"],
                       "base_deployment": self.bindings["native"]["migration_deployment"]}
        self.manifest = read(self.record["migration"]["file"])
        self.deployment = read(self.record["deployment"]["file"])
        self.runs = {}
        for index, (name, roles) in enumerate(PARTITION.items()):
            owner = {"pid": 90001 + index, "identity": {"start_ticks": 1234 + index},
                     "gpu_uuid": self.bindings[roles[0]]["gpu_uuid"]}
            for role in roles:
                run = DanceIntakeTests().fixture("sam07", role)[3]
                run["service_owner"] = owner
                self.runs[role] = run

    def receipts(self, name):
        segment = self.manifest["segments"][name]
        owner = self.runs[segment["roles"][0]]["service_owner"]
        manifest_sha = segment_evidence(self.record, name)[0]["sha256"]
        gate = {"schema": segment["aggregate_schema"], "passed": True, "source_id": "sam07",
                "segment_id": segment["segment_id"], "migration_manifest_sha256": manifest_sha,
                "producer_seal_sha256": self.deployment["segments"][name]["producer_seal_sha256"],
                "phase_displacement": 0, "same_persistent_service": True,
                "service_owner": owner, "runs": {r: self.runs[r] for r in segment["roles"]}}
        complete = {"schema": segment["COMPLETE_schema"], "passed": True,
                    "segment_id": segment["segment_id"], "migration_manifest_sha256": manifest_sha,
                    "jobs": segment["run_ids"], "remaining": [], "GPU_released": True,
                    "runtime_gate_sha256": "synthetic-gate-sha", "service_owner": owner}
        release = {"passed": True, "owner": owner, "process_absent": True,
                   "CUDA_allocation_absent": True,
                   "cleanup": {"pid": owner["pid"], "process_absent": True, "own_compute_absent": True}}
        return gate, complete, release

    def check(self, name, values):
        return validate_segment(self.manifest["segments"][name],
                                self.deployment["segments"][name], self.runs,
                                *values, "synthetic-gate-sha",
                                segment_evidence(self.record, name)[0]["sha256"])

    def test_real_partition_and_two_normal_releases(self):
        validate_partition(self.manifest, self.deployment, self.record, self.case, self.bindings)
        owners = [self.check(name, self.receipts(name)) for name in PARTITION]
        self.assertNotEqual(owners[0], owners[1])

    def test_missing_role_or_extra_role_rejected(self):
        values = copy.deepcopy(self.receipts("prefix"))
        del values[0]["runs"]["native"]
        with self.assertRaises(ValueError):
            self.check("prefix", values)
        values = copy.deepcopy(self.receipts("tail"))
        values[0]["runs"]["early"] = self.runs["early"]
        with self.assertRaises(ValueError):
            self.check("tail", values)

    def test_wrong_seal_or_manifest_rejected(self):
        for field in ("producer_seal_sha256", "migration_manifest_sha256"):
            values = copy.deepcopy(self.receipts("tail"))
            values[0][field] = "0" * 64
            with self.assertRaises(ValueError):
                self.check("tail", values)

    def test_release_owner_and_completion_sha_rejected(self):
        values = copy.deepcopy(self.receipts("prefix"))
        values[2]["owner"] = self.runs["split"]["service_owner"]
        with self.assertRaises(ValueError):
            self.check("prefix", values)
        values = copy.deepcopy(self.receipts("prefix"))
        values[1]["runtime_gate_sha256"] = "wrong"
        with self.assertRaises(ValueError):
            self.check("prefix", values)

    def test_same_service_or_incomplete_case_rejected(self):
        for value in (True, False):
            record = {"schema": "r150-evaluation-parallel-segment-release-v1",
                      "passed": True, "source_id": "sam07", "same_persistent_service": value,
                      "segment_count": 2, "segments": {"prefix": {}}, "bindings": {}, "job_gates": {}}
            with self.assertRaises(ValueError):
                verify_parallel_record(record, self.case)

    def test_graph_and_partition_drift_rejected(self):
        bindings = copy.deepcopy(self.bindings)
        bindings["split"]["graph"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            validate_partition(self.manifest, self.deployment, self.record, self.case, bindings)
        manifest = copy.deepcopy(self.manifest)
        manifest["segments"]["tail"]["roles"] = ["global_weak"]
        with self.assertRaises(ValueError):
            validate_partition(manifest, self.deployment, self.record, self.case, self.bindings)

    def test_prefix_cannot_claim_new_tail_manifest(self):
        values = copy.deepcopy(self.receipts("prefix"))
        values[0]["migration_manifest_sha256"] = self.record["migration"]["sha256"]
        with self.assertRaises(ValueError):
            self.check("prefix", values)
        bindings = copy.deepcopy(self.bindings)
        bindings["native"]["migration_manifest"] = self.record["migration"]
        with self.assertRaises(ValueError):
            validate_partition(self.manifest, self.deployment, self.record, self.case, bindings)

    def test_missing_original_record_and_tensor_drift_rejected(self):
        record = copy.deepcopy(self.record)
        del record["base_migration"]
        with self.assertRaises(ValueError):
            validate_partition(self.manifest, self.deployment, record, self.case, self.bindings)
        for key in ("tail_condition_cache_sha256", "noise_file_sha256", "tensor_sha256"):
            manifest = copy.deepcopy(self.manifest)
            manifest["science"][key] = ["wrong"] if key == "tensor_sha256" else "wrong"
            with self.assertRaises(ValueError):
                validate_partition(manifest, self.deployment, self.record, self.case, self.bindings)

    def test_original_same_host_partition_still_valid(self):
        record = {"migration": self.record["base_migration"],
                  "deployment": self.record["base_deployment"]}
        bindings = copy.deepcopy(self.bindings)
        for role in ("split", "global_weak"):
            bindings[role] = read(ROOT / "audit/binding_history/sam07" /
                                 "1490202cd94f3891802d43c740906d818d10e5c5ed8356ba3c3f19d0b0714cc4" /
                                 (role + ".json"))
        validate_partition(read(record["migration"]["file"]), read(record["deployment"]["file"]),
                           record, self.case, bindings)

if __name__ == "__main__":
    unittest.main()
