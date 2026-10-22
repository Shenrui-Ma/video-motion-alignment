import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import bind_producer
from common import ROOT, read, bound, expected_router
from finalize_composite import ARMS, SCHEMA, verify_composite_record
from finalize_batch import batch_evidence_records
from ingest import validate_batch


class SingleArmBindingTests(unittest.TestCase):
    def test_binding_one_arm_preserves_other_three_files(self):
        sid = "05_real_megumi_v"
        binding = read(ROOT / "runtime" / sid / "early.json")
        producer = str(Path(binding["producer_seal"]["file"]).parent)
        with tempfile.TemporaryDirectory(dir=ROOT / "audit") as temporary:
            root = Path(temporary)
            (root / "EVALUATION_MANIFEST.json").write_bytes(
                (ROOT / "EVALUATION_MANIFEST.json").read_bytes())
            folder = root / "runtime" / sid
            folder.mkdir(parents=True)
            preserved = {}
            for arm in ("early", "late", "split"):
                path = folder / (arm + ".json")
                path.write_bytes((ROOT / "runtime" / sid / path.name).read_bytes())
                preserved[arm] = path.read_bytes()
            args = ["bind_producer.py", "--case", sid, "--producer", producer,
                    "--seal-sha256", binding["producer_seal"]["sha256"],
                    "--schedule", "global_weak"]
            with patch.object(bind_producer, "ROOT", root), patch("sys.argv", args):
                with contextlib.redirect_stdout(io.StringIO()):
                    bind_producer.main()
            for arm, before in preserved.items():
                self.assertEqual((folder / (arm + ".json")).read_bytes(), before)
            generated = json.loads((folder / "global_weak.json").read_text())
            self.assertEqual(generated["role"], "global_weak")
            self.assertEqual(generated["steps_0based"], list(range(20)))
            self.assertEqual(generated["producer_seal"], binding["producer_seal"])


class CompositeReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "audit")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]
                         if c["source_id"] == "05_real_megumi_v")
        self.schedules = read(ROOT / "EVALUATION_MANIFEST.json")["schedules"]
        self.old_owner = {"pid": 1, "identity": {"uid": 1016, "start_ticks": "10"},
                          "gpu_uuid": "old-gpu", "port": 8641}
        self.new_owner = {"pid": 2, "identity": {"uid": 1004, "start_ticks": "20"},
                          "gpu_uuid": "new-gpu", "port": 8642}
        graph = self.store("graph", {})
        old_seal = self.store("old_seal", {"files": {}})
        common_file = self.store("common", {})
        sid = self.case["source_id"]
        self.bindings, self.runs = {}, {}
        for arm in ARMS:
            old = arm != "global_weak"
            owner = self.old_owner if old else self.new_owner
            remote = ("/home/test" if old else "/data4/test") + "/cases/" + sid
            run_id = f"r149_{sid}_seed{self.case['seed']}_{arm}"
            binding = {"status": "READY", "source_id": sid, "schedule": arm, "role": arm,
                       "run_id": run_id, "steps_0based": self.schedules[arm]["steps_0based"],
                       "phase_offset": 0, "producer_seal": old_seal,
                       "producer_verifier": common_file, "producer_runtime": common_file,
                       "host": "H3_SERVER_A" if old else "H3_SERVER_B",
                       "remote_root": remote, "gpu_uuid": owner["gpu_uuid"], "port": owner["port"],
                       "graph": graph, "gate_relative_file": "analysis/" + run_id + "_GATE.json",
                       "historical_prompt_sha256": self.case["prompt_sha256"],
                       "historical_noise_sha256": self.case["historical_initial_noise"]["sha256"],
                       "historical_fixed_graph_sha256": self.case["historical_runs"]["fixed"]["graph"]["sha256"]}
            router = expected_router(self.case, {"id": arm})
            run = {"schema": "r149-schedule-job-gate-v1", "passed": True,
                   "run_id": run_id, "role": arm, "producer_seal_sha256": old_seal["sha256"],
                   "NFE": 20, "Euler_updates": 20, "routed_blocks": 1000 if not old else 450,
                   "alpha": router["alpha"], "phase_displacement": 0,
                   "actual_routed_steps_zero_based": binding["steps_0based"],
                   "valid_frames": 141, "evaluation_crop_xywh": [0, 0, 1312, 736],
                   "physical_query_window": [router["start_frame"], router["end_frame"]],
                   "noise_sha256": binding["historical_noise_sha256"],
                   "sampler_timing": {"passed": True, "run_id": run_id, "sampler_wall_seconds": 100,
                                     "callback_steps": [{"step_zero_based": i} for i in range(20)]},
                   "binding_artifacts": {"actual_graph": "fixture"}, "final_latent": {"sha256": "fixture"},
                   "service_owner": owner, "video": {"file": remote + "/output/" + run_id + ".mp4"}}
            self.bindings[arm], self.runs[arm] = binding, run
        source = {"roles": list(ARMS[:3]), "run_ids": [self.runs[a]["run_id"] for a in ARMS[:3]],
                  "host": "H3_SERVER_A", "remote_root": self.bindings["early"]["remote_root"],
                  "producer_seal_sha256": old_seal["sha256"], "service_owner": self.old_owner}
        target = {"roles": ["global_weak"], "run_ids": [self.runs["global_weak"]["run_id"]],
                  "host": "H3_SERVER_B", "remote_root": self.bindings["global_weak"]["remote_root"]}
        manifest = {"schema": "r149-sam-global-weak-migration-v1", "source_id": sid,
                    "segments": {"host9_prefix": source, "host41_global": target},
                    "science": {"seed": self.case["seed"], "noise_file_sha256": self.case["historical_initial_noise"]["sha256"],
                                "prompt_sha256": self.case["prompt_sha256"],
                                "geometry": {"width": 1312, "height": 736, "frames": 141, "fps": 24},
                                "valid_frames": 141, "NFE": 20, "blocks": [0, 50],
                                "schedules": {a: self.bindings[a]["steps_0based"] for a in ARMS},
                                "target_global_graph_sha256": graph["sha256"],
                                "global_weak": {"alpha": 0.25, "physical_query_window": [0, 140], "phase_displacement": 0}},
                    "boundary": {"original_four_arm_COMPLETE_remains_absent": True,
                                 "same_persistent_service_across_hosts": False}}
        manifest_file = self.store("migration", manifest)
        new_seal = self.store("new_seal", {"files": {"configs/MIGRATION_MANIFEST.json":
                                                    {"sha256": manifest_file["sha256"]}}})
        self.bindings["global_weak"]["producer_seal"] = new_seal
        self.runs["global_weak"]["producer_seal_sha256"] = new_seal["sha256"]
        jobs = {a: self.store("job_" + a, r) for a, r in self.runs.items()}
        artifacts = {
            "cleanup": {"service_record": self.old_owner, "pid": 1, "process_absent": True,
                        "own_compute_absent": True, "child_compute_absent": True},
            "root_failure": {"error": "root admission pending", "unix": 20},
            "capacity_monitor_exit": {"exit_code": 0, "exact_generation_absent": True},
            "boundary_request": {"migration_manifest_sha256": manifest_file["sha256"],
                                 "service_owner": self.old_owner, "remaining": target["run_ids"], "created_unix": 10}}
        local_artifacts = {k: self.store(k, v) for k, v in artifacts.items()}
        partial = {"schema": "r149-schedule-partial-release-v1", "passed": True,
                   "source_id": sid, "segment_id": "host9_prefix", "jobs": source["run_ids"],
                   "remaining": target["run_ids"], "service_owner": self.old_owner,
                   "producer_seal_sha256": old_seal["sha256"], "migration_manifest_sha256": manifest_file["sha256"],
                   "process_generation_absent": True, "CUDA_allocation_absent": True, "original_four_arm_COMPLETE": False,
                   "job_gates": {self.runs[a]["run_id"]:
                                 {"file": self.bindings[a]["remote_root"] + "/" + self.bindings[a]["gate_relative_file"],
                                  "sha256": jobs[a]["sha256"]} for a in ARMS[:3]},
                   "registered_generations": {k: {"generation_absent": True, "actual_identity": None,
                                                  "expected_identity": {"start_ticks": "10"}}
                                              for k in ("service", "root_wrapper")},
                   **{k: {**local_artifacts[k], "record": v} for k, v in artifacts.items()}}
        segment = {"schema": "r149-fixed-schedule-segment-gate-v1", "passed": True,
                   "source_id": sid, "segment_id": "sam_global_weak_host41",
                   "migration_manifest_sha256": manifest_file["sha256"], "same_persistent_service": True,
                   "phase_displacement": 0, "producer_seal_sha256": new_seal["sha256"],
                   "runs": {"global_weak": self.runs["global_weak"]}, "service_owner": self.new_owner}
        segment_file = self.store("segment", segment)
        complete = {"schema": "r149-schedule-segment-completion-v1", "passed": True,
                    "segment_id": "sam_global_weak_host41", "migration_manifest_sha256": manifest_file["sha256"],
                    "jobs": target["run_ids"], "remaining": [], "GPU_released": True,
                    "service_owner": self.new_owner, "runtime_gate_sha256": segment_file["sha256"]}
        release = {"owner": self.new_owner, "passed": True, "process_absent": True,
                   "CUDA_allocation_absent": True,
                   "cleanup": {"pid": 2, "process_absent": True, "own_compute_absent": True}}
        deployment = {"schema": "r149-sam-migration-deployment-v1", "source_id": sid,
                      "migration_manifest_sha256": manifest_file["sha256"],
                      "segments": {
                          "host9_prefix": {**source},
                          "host41_global": {**target, "producer_seal_sha256": new_seal["sha256"]}}}
        self.record = {"schema": SCHEMA, "passed": True, "source_id": sid,
                       "same_persistent_service": False, "original_four_arm_COMPLETE": False,
                       "migration": manifest_file, "deployment": self.store("deployment", deployment),
                       "partial_release": self.store("partial", partial), "segment_gate": segment_file,
                       "segment_complete": self.store("complete", complete), "segment_release": self.store("release", release),
                       "job_gates": jobs, "partial_artifacts": local_artifacts,
                       "bindings": {a: self.store("binding_" + a, b) for a, b in self.bindings.items()}}

    def store(self, name, content):
        path = self.folder / (name + ".json")
        path.write_text(json.dumps(content, indent=2) + "\n")
        return bound(path)

    def change(self, field, mutate):
        data = read(self.record[field]["file"])
        mutate(data)
        self.record[field] = self.store(field + "_changed", data)

    def test_valid_three_plus_one(self):
        self.assertEqual(verify_composite_record(self.record, self.case), self.record)
        self.assertIn("prefix_root_failure", batch_evidence_records(self.record))

    def test_changed_file_sha_rejected(self):
        Path(self.record["job_gates"]["early"]["file"]).write_text("{}")
        with self.assertRaises(ValueError):
            verify_composite_record(self.record, self.case)

    def test_missing_role_rejected(self):
        del self.record["job_gates"]["split"]
        with self.assertRaises(ValueError):
            verify_composite_record(self.record, self.case)

    def test_same_service_claim_rejected(self):
        self.record["same_persistent_service"] = True
        with self.assertRaises(ValueError):
            verify_composite_record(self.record, self.case)

    def test_partial_cannot_claim_four_job_completion(self):
        self.change("partial_release", lambda p: p.update(remaining=[], original_four_arm_COMPLETE=True))
        with self.assertRaises(ValueError):
            verify_composite_record(self.record, self.case)

    def test_partial_gate_hash_mismatch_rejected(self):
        self.change("partial_release", lambda p: p["job_gates"][self.runs["early"]["run_id"]].update(sha256="f" * 64))
        with self.assertRaises(ValueError):
            verify_composite_record(self.record, self.case)

    def test_wrong_cleanup_owner_rejected(self):
        self.change("segment_release", lambda p: p.update(owner=self.old_owner))
        with self.assertRaises(ValueError):
            verify_composite_record(self.record, self.case)

    def test_deployment_wrong_actual_seal_rejected(self):
        self.change("deployment", lambda d: d["segments"]["host41_global"].update(producer_seal_sha256="wrong"))
        with self.assertRaises(ValueError):
            verify_composite_record(self.record, self.case)

    def test_embedded_cleanup_cannot_replace_original_file(self):
        self.change("partial_release", lambda p: p["cleanup"]["record"].update(pid=99))
        with self.assertRaises(ValueError):
            verify_composite_record(self.record, self.case)

    def test_selected_presentation_must_match_exact_run(self):
        wrong = dict(self.runs["early"], video={"file": "/different/video.mp4"})
        with self.assertRaises(ValueError):
            verify_composite_record(self.record, self.case, self.bindings["early"], wrong)

    def test_missing_segment_gpu_release_rejected(self):
        self.change("segment_release", lambda r: r.update(CUDA_allocation_absent=False))
        with self.assertRaises(ValueError):
            verify_composite_record(self.record, self.case)

    def test_segment_cannot_be_used_as_old_full_batch(self):
        with self.assertRaises(ValueError):
            validate_batch(self.case, self.bindings["global_weak"], self.runs["global_weak"],
                           read(self.record["segment_gate"]["file"]),
                           read(self.record["segment_complete"]["file"]),
                           read(self.record["segment_release"]["file"]), self.record["segment_gate"]["sha256"])


if __name__ == "__main__":
    unittest.main()
