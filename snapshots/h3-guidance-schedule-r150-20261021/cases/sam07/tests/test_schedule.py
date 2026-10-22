import contextlib
import copy
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "extensions")]
import torch
import r132_contract as contract
import service, job, run_queue, start_controller, execution_gate, process_identity
from H3TemporalRouter.schedule import ScheduleState, ScheduleBlockPatch, SCHEDULES
from H3TemporalRouter.core import EventBlockPatch, RouterState, route_attention


class ScheduleTests(unittest.TestCase):
    def test_exact_nine_steps_and_original_override(self):
        self.assertIs(ScheduleBlockPatch.override_class, EventBlockPatch.override_class)
        for name, steps in SCHEDULES.items():
            state = ScheduleState.__new__(ScheduleState)
            state.active_steps = steps
            state.block_start, state.block_end = 0, 50
            selected = []
            for i in range(20):
                state.forward_index = i
                self.assertEqual(sum(state.selected(b) for b in range(50)), 50 if i in steps else 0)
                self.assertFalse(state.selected(-1))
                self.assertFalse(state.selected(50))
                if state.selected(0):
                    selected.append(i)
            self.assertEqual(selected, contract.SCHEDULES[name])
            self.assertEqual(len(selected), len(contract.SCHEDULES[name]))

    def test_original_mid_membership_and_state_isolation(self):
        old = RouterState.__new__(RouterState)
        new = ScheduleState.__new__(ScheduleState)
        old.block_start = new.block_start = 0
        old.block_end = new.block_end = 50
        old.step_start, old.step_end = 6, 15
        new.active_steps = tuple(range(6, 15))
        for i in range(20):
            old.forward_index = new.forward_index = i
            self.assertEqual([old.selected(b) for b in range(50)],
                             [new.selected(b) for b in range(50)])
        second = ScheduleState.__new__(ScheduleState)
        second.active_steps = SCHEDULES["late"]
        new.forward_index = 19
        self.assertFalse(hasattr(second, "forward_index"))

    def test_original_same_bin_qkv_and_alpha_zero(self):
        torch.manual_seed(149)
        q, k, v = [torch.randn(1, 2, 16, 128, dtype=torch.float64) for _ in range(3)]
        original = [x.clone() for x in (q, k, v)]
        plan = {"query_interval_half_open": [12, 16], "reference_video_segment": [2, 8],
                "target_video_segment": [10, 16], "latent_interval_half_open": [1, 3], "frame_rows": 2}
        calls = []
        def dense(q, k, v):
            calls.append(tuple(x.clone() for x in (q, k, v)))
            scores = q @ k.transpose(-1, -2) / math.sqrt(q.shape[-1])
            return scores.softmax(-1) @ v, scores.logsumexp(-1).float()
        route_attention(q, k, v, 2, plan, mode="mass_preserve", attention=dense)
        self.assertTrue(torch.equal(calls[0][0], q))
        self.assertTrue(torch.equal(calls[1][0], q[:, :, 12:16]))
        self.assertTrue(torch.equal(calls[2][0][0:1], q[:, :, 12:14]))
        self.assertTrue(torch.equal(calls[2][0][1:2], q[:, :, 14:16]))
        self.assertTrue(torch.equal(calls[2][1][0:1], k[:, :, 4:6]))
        self.assertTrue(torch.equal(calls[2][1][1:2], k[:, :, 6:8]))
        for a, b in zip((q, k, v), original):
            self.assertTrue(torch.equal(a, b))
        off = route_attention(q, k, v, 2, plan, mode="mass_preserve", alpha=0, attention=dense)
        native = route_attention(q, k, v, 2, plan, mode="native", attention=dense)
        self.assertTrue(torch.equal(off, native))

    def test_registry_and_unchanged_base_loader(self):
        jobs, order = contract.registry()
        graphs = [contract.expected_graph(r) for r in order]
        self.assertEqual(len(jobs), 6)
        for graph in graphs:
            self.assertEqual(graph["50"]["class_type"], "H3FixedSchedule")
            self.assertEqual(graph["50"]["inputs"]["model"], ["41", 0])
        for key in ("1", "3", "4", "8", "9", "41"):
            self.assertTrue(all(g[key] == graphs[0][key] for g in graphs))
        runtime = contract.read(ROOT / "configs/runtime.json")
        self.assertEqual(runtime["expected_gpu_index"], runtime["gpu_index"])


class LifecycleTests(unittest.TestCase):
    def test_http_registered_schema_and_missing_node(self):
        info = {n["class_type"]: {} for n in contract.expected_graph(contract.RUN_ID).values()}
        with patch.object(start_controller.urllib.request, "urlopen",
                          return_value=io.BytesIO(json.dumps(info).encode())):
            self.assertTrue(start_controller.check_http_schema(ROOT, 8640)["passed"])
        del info["H3FixedSchedule"]
        with patch.object(start_controller.urllib.request, "urlopen",
                          return_value=io.BytesIO(json.dumps(info).encode())):
            with self.assertRaisesRegex(ValueError, "H3FixedSchedule"):
                start_controller.check_http_schema(ROOT, 8640)

    def test_three_jobs_same_exact_service_then_one_stop(self):
        jobs, order = contract.registry()
        owner = {"pid": 123, "identity": {"uid": 1004, "start_ticks": "456", "cmdline": "owned"}}
        posts = []
        histories = {}
        def http(req, timeout=30):
            route = req.full_url.rsplit("/", 1)[-1]
            if route == "queue":
                value = {"queue_running": [], "queue_pending": []}
            elif route == "prompt":
                body = json.loads(req.data)
                posts.append(body)
                pid = "test-" + str(len(posts))
                histories[pid] = {"status": {"status_str": "success", "completed": True}, "outputs": {}}
                value = {"prompt_id": pid}
            elif route in histories:
                value = {route: histories[route]}
            else:
                raise AssertionError(req.full_url)
            return io.BytesIO(json.dumps(value).encode())
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            root = Path(tmp)
            for d in ("configs/graphs", "processes", "logs"):
                (root / d).mkdir(parents=True)
            def write(rel, value):
                (root / rel).write_text(json.dumps(value))
            copied = copy.deepcopy(jobs)
            for run in order:
                path = root / "configs/graphs" / (run + ".json")
                write(str(path.relative_to(root)), contract.expected_graph(run))
                copied[run]["graph_sha256"] = contract.sha(path)
            write("configs/queue.json", {"jobs": order, "finalize": True})
            write("configs/scientific_contract.json", contract.science())
            write("processes/service.json", owner)
            for target, name, value in ((service, "RUN", root), (job, "RUN", root)):
                stack.enter_context(patch.object(target, name, value))
            for target, name, kwargs in (
                (run_queue, "wait_controller_registration", {"return_value": {}}),
                (run_queue.preflight, "check", {"return_value": {}}),
                (run_queue, "registry", {"return_value": (copied, order)}),
                (service, "assert_owned", {}), (service, "residency_snapshot", {}),
                (run_queue, "record_resources", {}), (service, "stop", {}),
                (execution_gate, "admitted_job", {"return_value": True}),
                (contract, "validate_job", {"side_effect": lambda run: copied[run]}),
                (contract, "prepare_loader_inputs", {"side_effect": lambda run: copied[run]}),
                (job, "wait_host_admission", {"return_value": 0}),
                (job.urllib.request, "urlopen", {"side_effect": http}),
                (run_queue.subprocess, "run", {"return_value": Mock(returncode=0)})):
                stack.enter_context(patch.object(target, name, **kwargs))
            with contextlib.redirect_stdout(io.StringIO()):
                run_queue.run(123, "456")
            self.assertEqual([x["prompt"]["50"]["inputs"]["schedule"] for x in posts],
                             ['native', 'fixed', 'early', 'late', 'split', 'global_weak'])
            self.assertEqual([x["prompt"]["50"]["inputs"]["run_id"] for x in posts], order)
            self.assertEqual(run_queue.subprocess.run.call_count, 7)
            self.assertEqual(json.loads((root / "logs/controller_state.json").read_text())["completed"], order)
            service.stop.assert_called_once_with(expected_record=owner)

    def test_stale_generation_rejected(self):
        old = {"pid": 123, "identity": {"uid": 1004, "start_ticks": "100", "cmdline": "owned"}}
        for actual in (
            {"pid": 123, "identity": {"uid": 1004, "start_ticks": "101", "cmdline": "owned"}},
            {"pid": 123, "identity": {"uid": 1005, "start_ticks": "100", "cmdline": "owned"}}):
            with self.assertRaisesRegex(RuntimeError, "stale service"):
                job.require_generation(actual, old)


if __name__ == "__main__":
    unittest.main()
