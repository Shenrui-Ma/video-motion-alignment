"""CPU regression checks for the shared foreign-occupied GPU admission policy."""
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PACKAGE = HERE / "host60_batches/short_0085"
sys.path.insert(0, str(PACKAGE / "scripts"))
import common
import peer_support


class Host60AdmissionTests(unittest.TestCase):
    def test_numerical_sources_are_identical(self):
        for sid in ("short_0085", "long_0039"):
            for name in ("track.py", "score.py"):
                self.assertEqual((HERE / "host9_batches" / sid / "scripts" / name).read_bytes(),
                                 (HERE / "host60_batches" / sid / "scripts" / name).read_bytes())

    def resource(self, free):
        gpu = common.read(PACKAGE / "configs/RUNTIME.json")["gpu_uuid"]
        runtime = common.read(PACKAGE / "configs/RUNTIME.json")
        answers = [f"{99999999}, {gpu}\n", f"{gpu}, NVIDIA A100-PCIE-40GB, {free}, 67\n"]
        fake_capacity = SimpleNamespace(snapshot=lambda: {}, assess=lambda *args: {"passed": True})
        with patch.object(common, "ROOT", PACKAGE), patch.object(common.os, "getuid", return_value=1015), \
             patch.object(common.socket, "gethostname", return_value=runtime["host"]), \
             patch.dict(common.os.environ, CUDA_VISIBLE_DEVICES=gpu), \
             patch.dict(sys.modules, capacity=fake_capacity), \
             patch.object(common.subprocess, "check_output", side_effect=answers), \
             patch.object(peer_support, "peers", return_value=[]):
            return common.resource_check(gpu)

    def test_20gib_threshold_exact(self):
        self.assertEqual(self.resource(20480)["memory_free_mib"], 20480)
        with self.assertRaises(AssertionError):
            self.resource(20479)

    def test_foreign_same_card_allowed_without_identity_or_mutation(self):
        identity = SimpleNamespace(snapshot=lambda pid: self.fail("Foreign identity inspected"))
        gpu = "GPU-target"
        with patch.object(peer_support.os, "getuid", return_value=1015):
            value = peer_support.owned_check(
                {"processes": [{"pid": 123, "uid": 9999, "gpu_uuid": gpu}]}, [], identity, gpu)
        self.assertEqual(value["owned_devices"], [gpu])

    def test_unregistered_owned_compute_rejected(self):
        with patch.object(peer_support.os, "getuid", return_value=1015):
            with self.assertRaises(AssertionError):
                peer_support.owned_check(
                    {"processes": [{"pid": 123, "uid": 1015, "gpu_uuid": "GPU-target"}]},
                    [], None, "GPU-target")

    def test_oom_stops_batch_and_cleanup_binds_exact_child(self):
        text = (PACKAGE / "scripts/run_batch.py").read_text()
        self.assertIn("if error is not None:raise error", text)
        self.assertIn("assert identity(child.pid)==bound_id;child.terminate()", text)
        self.assertIn("assert identity(child.pid)==bound_id;child.kill()", text)
        self.assertNotIn("pkill", text)
        self.assertNotIn("killall", text)


if __name__ == "__main__":
    unittest.main()
