import copy
import hashlib
import json
import signal
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import capacity_trial as trial


def sample():
    return {"uid": 1004, "host_available_bytes": 100 * trial.GIB, "ancestors": [{
        "path": "/user.slice", "current_bytes": 99 * trial.GIB,
        "high_bytes": 100 * trial.GIB, "max_bytes": 112 * trial.GIB,
        "stat": {"anon": 55 * trial.GIB, "file": 40 * trial.GIB, "shmem": 0,
                 "active_file": 40 * trial.GIB, "inactive_file": 0,
                 "file_mapped": 0, "file_dirty": 0, "file_writeback": 0},
        "pressure": {"some": {"avg10": 0.0}, "full": {"avg10": 0.0}},
        "events": {"max": 0, "oom": 0, "oom_kill": 0, "high": 0}}]}


def proc(pid=22, uid=1004, start=10, command="a"):
    return {"pid": pid, "uid": uid, "start_ticks": start, "cmdline_sha256": command}


class Tests(unittest.TestCase):
    def test_current_35_47_headroom_admits_trial(self):
        value = trial.assess(sample(), stage="entry")
        self.assertTrue(value["passed"])
        self.assertEqual(value["ancestors"][0]["adjusted_headroom_bytes"],
                         {"high": 35 * trial.GIB, "max": 47 * trial.GIB})

    def test_entry_below_34_46_rejected(self):
        s = sample()
        s["ancestors"][0]["current_bytes"] = 101 * trial.GIB
        self.assertFalse(trial.assess(s, stage="entry")["passed"])

    def test_running_8_20_boundary_stops(self):
        s = sample()
        r = s["ancestors"][0]
        r["current_bytes"] = 100 * trial.GIB
        r["stat"]["file"] = r["stat"]["active_file"] = 14 * trial.GIB
        v = trial.assess(s, stage="running", baseline=sample())
        self.assertFalse(v["passed"])
        self.assertIn("/user.slice adjusted high threshold", v["reasons"])
        self.assertIn("/user.slice adjusted max threshold", v["reasons"])

    def test_raw_and_host_floors(self):
        s = sample()
        s["ancestors"][0]["current_bytes"] = 104 * trial.GIB
        s["host_available_bytes"] = 40 * trial.GIB
        v = trial.assess(s, stage="running", baseline=sample())
        self.assertIn("/user.slice raw max floor", v["reasons"])
        self.assertIn("host MemAvailable threshold", v["reasons"])

    def test_oom_max_or_counter_reset_stops(self):
        for event in ("max", "oom", "oom_kill"):
            s = sample()
            s["ancestors"][0]["events"][event] = 1
            self.assertFalse(trial.assess(s, stage="running", baseline=sample())["passed"])
        base = sample()
        base["ancestors"][0]["events"]["max"] = 5
        self.assertFalse(trial.assess(sample(), stage="running", baseline=base)["passed"])

    def test_high_counter_alone_logged_not_failure(self):
        s = sample()
        s["ancestors"][0]["events"]["high"] = 100
        self.assertTrue(trial.assess(s, stage="running", baseline=sample())["passed"])

    def test_psi_is_diagnostic_at_entry_and_during_running(self):
        s = sample()
        s["ancestors"][0]["pressure"]["some"]["avg10"] = 10.0
        s["ancestors"][0]["pressure"]["full"]["avg10"] = 9.0
        entry = trial.assess(s, stage="entry")
        self.assertTrue(entry["passed"])
        first = trial.assess(s, stage="running", baseline=sample())
        self.assertTrue(first["passed"])
        second = trial.assess(s, stage="running", baseline=sample(), previous_pressure_streak=1)
        self.assertTrue(second["passed"])
        self.assertEqual(second["pressure_streak"], 2)
        self.assertEqual(second["ancestors"][0]["pressure"], s["ancestors"][0]["pressure"])
        clear = trial.assess(sample(), stage="running", baseline=sample(), previous_pressure_streak=1)
        self.assertEqual(clear["pressure_streak"], 0)

    def test_high_psi_does_not_disable_capacity_or_event_stops(self):
        s = sample()
        s["ancestors"][0]["pressure"]["some"]["avg10"] = 10.0
        s["ancestors"][0]["events"]["oom_kill"] = 1
        self.assertFalse(trial.assess(s, stage="running", baseline=sample())["passed"])
        s["ancestors"][0]["events"]["oom_kill"] = 0
        s["host_available_bytes"] = 40 * trial.GIB
        self.assertFalse(trial.assess(s, stage="running", baseline=sample())["passed"])

    def test_reused_pid_never_signalled(self):
        send, open_fd = Mock(), Mock(return_value=99)
        for changed in (proc(start=11), proc(uid=1016), proc(command="different")):
            self.assertFalse(trial.signal_exact(proc(), lookup=lambda _, value=changed: value,
                                                pidfd_open=open_fd, pidfd_signal=send, uid=1004))
        open_fd.assert_not_called()
        send.assert_not_called()

    def test_pid_reuse_between_check_and_pidfd_open_never_signalled(self):
        send, close = Mock(), Mock()
        lookup = Mock(side_effect=[proc(), proc(start=11)])
        self.assertFalse(trial.signal_exact(proc(), lookup=lookup, pidfd_open=lambda *_: 99,
                                            pidfd_signal=send, close=close, uid=1004))
        send.assert_not_called()
        close.assert_called_once_with(99)

    def test_exact_generation_uses_pidfd_not_killpg(self):
        send, close = Mock(), Mock()
        self.assertTrue(trial.signal_exact(proc(), lookup=lambda _: proc(),
                                           pidfd_open=lambda *_: 99, pidfd_signal=send,
                                           close=close, uid=1004))
        send.assert_called_once_with(99, signal.SIGTERM, None, 0)
        close.assert_called_once_with(99)

    def test_protected_or_other_uid_process_never_signalled(self):
        lookup, send = Mock(), Mock()
        for value in (proc(pid=1646285), proc(uid=1016), proc(pid=1)):
            self.assertFalse(trial.signal_exact(value, lookup=lookup, pidfd_signal=send, uid=1004))
        lookup.assert_not_called()
        send.assert_not_called()

    def test_only_registered_descendants_of_this_service_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "audit/observations/step000"
            folder.mkdir(parents=True)
            owned = {**proc(pid=23), "parent": proc(), "command": [str(root / "decode.py")]}
            unrelated = {**proc(pid=24), "parent": proc(pid=777), "command": [str(root / "decode.py")]}
            other_user = {**proc(pid=25, uid=1016), "parent": proc(), "command": [str(root / "decode.py")]}
            protected = {**proc(pid=1646285), "parent": proc(), "command": [str(root / "decode.py")]}
            foreign_path = {**proc(pid=26), "parent": proc(), "command": ["/other/task/decode.py"]}
            for i, row in enumerate((owned, unrelated, other_user, protected, foreign_path)):
                (folder / f"{i}.process.json").write_text(json.dumps(row))
            selected = trial.registered_targets(root, proc())
            self.assertEqual([x["pid"] for x in selected], [22, 23])

    def test_invalid_telemetry_rejected(self):
        s = copy.deepcopy(sample())
        s["ancestors"][0]["stat"].pop("file_mapped")
        with self.assertRaises(KeyError):
            trial.assess(s, stage="entry")

    def test_partial_registration_gets_bounded_retry(self):
        path, sleep = Mock(), Mock()
        path.read_text.side_effect = ['{"pid":', json.dumps(proc())]
        result = trial.read_registration(path, clock=Mock(side_effect=[1.0, 1.001]), sleep=sleep)
        self.assertEqual(result, proc())
        sleep.assert_called_once_with(.01)

    def test_persistent_registration_corruption_fails_closed(self):
        path, sleep = Mock(), Mock()
        path.read_text.return_value = '{"pid":'
        with self.assertRaises(json.JSONDecodeError):
            trial.read_registration(path, clock=Mock(side_effect=[1.0, 1.01, 1.06]), sleep=sleep)
        self.assertEqual(path.read_text.call_count, 2)
        sleep.assert_called_once_with(.01)

    def test_actual_r133_service_observer_decoder_pose_chain(self):
        here = Path(__file__).parent
        fixture = json.loads((here / "R133_ACTUAL_PARENT_CHAIN.json").read_text())
        service = json.loads((here / "R133_ACTUAL_SERVICE.json").read_text())["record"]
        owner = {"pid": service["pid"], "uid": service["identity"]["uid"],
                 "start_ticks": int(service["identity"]["start_ticks"]),
                 "cmdline_sha256": hashlib.sha256(
                     b"\0".join(x.encode() for x in service["command"]) + b"\0").hexdigest()}
        records = [r["record"] for r in fixture["records"]]
        observer = next(r for r in records if r["pid"] == 1940173)
        self.assertTrue(trial.same_identity(observer["parent"], owner))
        command_check = trial.task_command
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "audit/observations/step000"
            directory.mkdir(parents=True)
            for i, row in enumerate(records):
                (directory / f"{i}.process.json").write_text(json.dumps(row))
            # Keep archived commands/identities untouched while relocating only JSON.
            with patch.object(trial, "task_command", side_effect=lambda cmd, _:
                              command_check(cmd, fixture["root"])):
                selected = trial.registered_targets(root, owner)
        self.assertEqual({r["pid"] for r in selected}, {1937158, 1940173, 1940277, 1940884})

    def test_unhandled_monitor_failures_stop_bound_service(self):
        for error in (OSError("log disk full"), PermissionError("ready denied"),
                      ValueError("baseline invalid"), KeyboardInterrupt()):
            with self.subTest(error=repr(error)), \
                    patch.object(trial.os, "pidfd_open", Mock(), create=True), \
                    patch.object(trial.signal, "pidfd_send_signal", Mock(), create=True), \
                    patch.object(trial, "bind_service", return_value=proc()), \
                    patch.object(trial, "monitor_bound", side_effect=error), \
                    patch.object(trial, "signal_exact") as stop:
                with self.assertRaises(type(error)):
                    trial.monitor("/trial", "/trial/log", "/trial/ready")
                stop.assert_called_once_with(proc())

    def test_actual_log_and_ready_write_failures_stop_bound_service(self):
        for failure in ("log_open", "log_write", "ready_open", "ready_replace"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                output, ready = root / "log.jsonl", root / "ready.json"
                original_open = Path.open

                def open_path(path, *args, failure=failure, output=output, ready=ready,
                              original_open=original_open, **kwargs):
                    if (failure == "log_open" and path == output) or (
                            failure == "ready_open" and path == ready.with_name("ready.json.tmp")):
                        raise OSError("injected open failure")
                    if failure == "log_write" and path == output:
                        handle = Mock()
                        handle.__enter__ = Mock(return_value=handle)
                        handle.__exit__ = Mock(return_value=False)
                        handle.write.side_effect = OSError("injected write failure")
                        return handle
                    return original_open(path, *args, **kwargs)

                snapshot_module = types.SimpleNamespace(snapshot=lambda **_: sample())
                with patch.dict("sys.modules", cgroup_memory=snapshot_module), \
                        patch.object(trial.os, "pidfd_open", Mock(), create=True), \
                        patch.object(trial.signal, "pidfd_send_signal", Mock(), create=True), \
                        patch.object(trial, "bind_service", return_value=proc()), \
                        patch.object(trial, "identity", return_value=proc()), \
                        patch.object(trial, "process_memory", return_value=[]), \
                        patch.object(Path, "open", open_path), \
                        patch.object(trial.os, "replace", side_effect=OSError("injected replace failure")), \
                        patch.object(trial, "signal_exact") as stop:
                    with self.assertRaises(OSError):
                        trial.monitor(root, output, ready)
                    stop.assert_called_once_with(proc())

    def test_normal_service_completion_does_not_signal(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict("sys.modules", cgroup_memory=types.SimpleNamespace(snapshot=lambda **_: sample())), \
                patch.object(trial.os, "pidfd_open", Mock(), create=True), \
                patch.object(trial.signal, "pidfd_send_signal", Mock(), create=True), \
                patch.object(trial, "bind_service", return_value=proc()), \
                patch.object(trial, "identity", return_value=None), \
                patch.object(trial, "signal_exact") as stop:
            root = Path(tmp)
            self.assertEqual(trial.monitor(root, root / "log", root / "ready"), 0)
            stop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
