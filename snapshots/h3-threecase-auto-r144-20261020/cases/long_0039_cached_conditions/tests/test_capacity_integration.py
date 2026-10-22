"""Pre-CUDA readiness and cleanup behavior; no service or model is launched."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import capacity_trial
import root_run_online as runner


class CapacityIntegration(unittest.TestCase):
    def setUp(self):
        self.identity = {"uid": 1004, "start_ticks": "7", "cmdline": "python monitor "}
        self.owner = {"pid": 456, "uid": 1004, "start_ticks": 8, "cmdline_sha256": "a" * 64}
        self.monitor = {"pid": 123, "uid": 1004, "start_ticks": 7, "cmdline_sha256": "b" * 64}
        self.child = Mock(pid=123)
        self.child.poll.return_value = None

    def ready(self, path, owner=None):
        (path / "CAPACITY_MONITOR_READY.json").write_text(json.dumps({
            "passed": True, "owner": owner or self.owner, "monitor_identity": self.monitor,
        }))

    def test_exact_ready_is_required(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            self.ready(path)
            with patch.object(runner.service, "assert_owned"), \
                    patch.object(runner.service, "current_identity", return_value=self.identity), \
                    patch.object(capacity_trial, "bind_service", return_value=self.owner), \
                    patch.object(capacity_trial, "identity", return_value=self.monitor):
                result = runner.capacity_ready(self.child, self.identity, {}, path)
            self.assertTrue(result["passed"])

    def test_stale_ready_rejected_before_go(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            self.ready(path, dict(self.owner, start_ticks=99))
            with patch.object(runner.service, "assert_owned"), \
                    patch.object(runner.service, "current_identity", return_value=self.identity), \
                    patch.object(capacity_trial, "bind_service", return_value=self.owner):
                with self.assertRaises((RuntimeError, ValueError, AssertionError)):
                    runner.capacity_ready(self.child, self.identity, {}, path)

    def test_dead_monitor_rejected_before_go(self):
        self.child.poll.return_value = 2
        with patch.object(runner.service, "assert_owned"):
            with self.assertRaises((RuntimeError, ValueError, AssertionError)):
                runner.capacity_ready(self.child, self.identity, {}, Path("/unused"))

    def test_cleanup_preserves_failed_exit_code(self):
        self.child.wait.return_value = 2
        with patch.object(runner.service, "current_identity", return_value=None):
            result = runner.finish_capacity_monitor(self.child, self.identity)
        self.assertEqual(result["exit_code"], 2)
        self.assertTrue(result["exact_generation_absent"])


if __name__ == "__main__":
    unittest.main()
