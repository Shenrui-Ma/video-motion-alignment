import copy
import unittest
from unittest.mock import patch
from common import ROOT, read, expected_router
from ingest import validate_job, validate_batch
from summarize_review import event_stats, phase_stats
from prepare_manifest import SCHEDULES
from bind_producer import runtime_binding


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.case = read(ROOT / "EVALUATION_MANIFEST.json")["cases"][0]
        self.schedule = dict(SCHEDULES["early"], id="early")
        sid, seed = self.case["source_id"], self.case["seed"]
        self.binding = {"status": "READY", "source_id": sid, "schedule": "early", "role": "early",
            "run_id": f"r149_{sid}_seed{seed}_early", "steps_0based": list(range(9)), "phase_offset": 0,
            "producer_seal": {"file": "fixture", "sha256": "seal"},
            "producer_verifier": {"file": "fixture", "sha256": "verifier"},
            "producer_runtime": {"file": "fixture", "sha256": "runtime"},
            "gpu_uuid": "test-gpu", "port": 8640,
            "historical_prompt_sha256": self.case["prompt_sha256"],
            "historical_noise_sha256": self.case["historical_initial_noise"]["sha256"],
            "historical_fixed_graph_sha256": self.case["historical_runs"]["fixed"]["graph"]["sha256"],
            "remote_root": "/run/case"}
        self.run = {"schema": "r149-schedule-job-gate-v1", "passed": True,
            "producer_seal_sha256": "seal", "run_id": self.binding["run_id"], "role": "early",
            "NFE": 20, "Euler_updates": 20, "routed_blocks": 450, "alpha": 1,
            "phase_displacement": 0, "actual_routed_steps_zero_based": list(range(9)),
            "valid_frames": self.case["geometry"]["valid_frames"],
            "evaluation_crop_xywh": self.case["geometry"]["crop_xywh"],
            "physical_query_window": [0, 97], "noise_sha256": self.binding["historical_noise_sha256"],
            "sampler_timing": {"passed": True, "run_id": self.binding["run_id"], "sampler_wall_seconds": 10,
                              "callback_steps": [{"step_zero_based": i} for i in range(20)]},
            "binding_artifacts": {"actual_graph": "sha"}, "final_latent": {"sha256": "x"},
            "service_owner": {"pid": 123, "identity": {"start_ticks": "456"},
                              "gpu_uuid": "test-gpu", "port": 8640},
            "video": {"file": "/run/case/output/actual.mp4"}}
        self.mock = patch("ingest.verify_record")
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def test_index_and_call_counts(self):
        for arm, row in SCHEDULES.items():
            self.assertEqual([i - 1 for i in row["steps_1based"]], row["steps_0based"])
            self.assertEqual(len(row["steps_0based"]), 20 if arm == "global_weak" else 9)

    def test_mixed_host_runtime_binding(self):
        root = "/home/researcher/h3_runs/guidance_schedule_r149_host9_20261020/cases/05_real_megumi_v"
        runtime = {"host": "H3_SERVER_A", "remote_root": root, "gpu_index": 1,
                   "gpu_uuid": "test-gpu", "port": 8641}
        self.assertEqual(runtime_binding(runtime, "05_real_megumi_v")["remote_root"], root)
        with self.assertRaises(ValueError):
            runtime_binding(runtime, "short_0252")
        with self.assertRaises(ValueError):
            runtime_binding(dict(runtime, host="H3_SERVER_B"), "05_real_megumi_v")

    def test_third_case_append_preserves_existing_cases_and_events(self):
        before = ROOT / "audit/amendments/add_short_0358/before"
        old = read(before / "EVALUATION_MANIFEST.json")
        current = read(ROOT / "EVALUATION_MANIFEST.json")
        self.assertEqual(current["cases"][:-1], old["cases"])
        self.assertEqual(current["schedules"], old["schedules"])
        old_plan = read(before / "EVALUATION_PLAN.json")
        self.assertEqual(read(ROOT / "EVALUATION_PLAN.json")["cases"][:-1], old_plan["cases"])
        drink = current["cases"][-1]
        self.assertEqual(drink["source_id"], "short_0358")
        self.assertEqual(drink["geometry"]["valid_frames"], 105)
        self.assertEqual([e["source"] for e in drink["events"]], [[14, 18], [37, 40], [80, 84]])
        self.assertEqual([e["native"] for e in drink["events"]], [[14, 19], [46, 49], [91, 94]])
        self.assertEqual([e["fixed"] for e in drink["events"]], [[14, 19], [43, 46], [90, 92]])
        for arm in SCHEDULES:
            self.assertTrue(all(e[arm] is None for e in drink["events"]))
        self.assertEqual(read(ROOT / "MF_PLAN.json")["new_target_trackers"], 12)
        self.assertEqual(read(ROOT / "MF_PLAN.json")["new_source_trackers"], 0)

    def test_pending_refuses(self):
        self.binding["status"] = "PENDING_PRODUCER_CONTRACT"
        with self.assertRaises(ValueError):
            validate_job(self.case, self.schedule, self.binding, self.run)

    def test_exact_job_allows_preview(self):
        self.assertEqual(validate_job(self.case, self.schedule, self.binding, self.run), self.run)

    def test_phase_schedule_noise_and_alpha_rejected(self):
        for key, wrong in [("phase_displacement", -178), ("routed_blocks", 449), ("alpha", .25),
                           ("actual_routed_steps_zero_based", list(range(1, 10))), ("noise_sha256", "bad")]:
            bad = dict(self.run, **{key: wrong})
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_job(self.case, self.schedule, self.binding, bad)

    def test_wrong_output_root_rejected(self):
        bad = dict(self.run, video={"file": "/different/output.mp4"})
        with self.assertRaises(ValueError):
            validate_job(self.case, self.schedule, self.binding, bad)

    def test_global_weak_preserves_actual_meaning(self):
        sam = read(ROOT / "EVALUATION_MANIFEST.json")["cases"][1]
        router = expected_router(sam, {"id": "global_weak"})
        self.assertEqual((router["alpha"], router["start_frame"], router["end_frame"]), (.25, 0, 140))
        self.assertEqual(expected_router(sam, {"id": "early"})["end_frame"], 65)

    def test_global_weak_actual_job(self):
        arm = "global_weak"
        schedule = dict(SCHEDULES[arm], id=arm)
        binding = dict(self.binding, schedule=arm, role=arm, steps_0based=list(range(20)),
                       run_id=self.binding["run_id"].rsplit("_", 1)[0] + "_" + arm)
        timing = dict(self.run["sampler_timing"], run_id=binding["run_id"])
        run = dict(self.run, run_id=binding["run_id"], role=arm, alpha=.25, routed_blocks=1000,
                   actual_routed_steps_zero_based=list(range(20)), sampler_timing=timing)
        validate_job(self.case, schedule, binding, run)
        with self.assertRaises(ValueError):
            validate_job(self.case, schedule, binding, dict(run, alpha=1))

    def test_batch_requires_all_four_same_owner_and_release(self):
        runs = {}
        for arm in SCHEDULES:
            runs[arm] = dict(self.run, role=arm,
                             run_id=self.binding["run_id"].rsplit("_", 1)[0] + "_" + arm)
        gate = {"schema": "r149-fixed-schedule-runtime-gate-v1", "passed": True,
            "source_id": self.case["source_id"], "producer_seal_sha256": "seal",
            "same_persistent_service": True, "phase_displacement": 0,
            "service_owner": self.run["service_owner"], "runs": runs}
        complete = {"schema": "r149-schedule-completion-v1", "passed": True,
            "jobs": [r["run_id"] for r in runs.values()], "remaining": [], "GPU_released": True,
            "runtime_gate_sha256": "gate", "service_owner": self.run["service_owner"]}
        release = {"owner": self.run["service_owner"], "passed": True, "process_absent": True,
            "CUDA_allocation_absent": True,
            "cleanup": {"pid": 123, "process_absent": True, "own_compute_absent": True}}
        validate_batch(self.case, self.binding, self.run, gate, complete, release, "gate")
        for field in ("GPU_released", "runtime_gate_sha256"):
            bad = dict(complete, **{field: False})
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_batch(self.case, self.binding, self.run, gate, bad, release, "gate")
        bad_gate = copy.deepcopy(gate)
        bad_gate["runs"]["late"]["service_owner"] = {"pid": 124}
        with self.assertRaises(ValueError):
            validate_batch(self.case, self.binding, self.run, bad_gate, complete, release, "gate")

    def test_event_shared_source(self):
        result = event_stats([2, 3], [5, 6], [4, 4], 24)
        self.assertEqual(result["absolute_error_frames"], [1, 2])
        self.assertEqual(result["paired_change_vs_fixed_ms"], [-2 * 1000 / 24, -1000 / 24])

    def test_global_shift_cancels_in_phase_duration(self):
        a = {"source": [1, 1], "fixed": [6, 6], "early": [10, 10]}
        b = {"source": [8, 8], "fixed": [13, 13], "early": [17, 17]}
        result = phase_stats(a, b, "early", 24)
        self.assertEqual(result["new_absolute_duration_error_ms"], [0, 0])
        self.assertIsNone(event_stats([1, 2], [2, 3], None, 24))


if __name__ == "__main__":
    unittest.main()
