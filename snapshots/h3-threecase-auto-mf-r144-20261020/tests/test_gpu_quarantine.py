"""CPU-only NVML and existing tracker admission-hook regression checks."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import common
import gpu_query
import run_batch
import track


class GPUQuarantine(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "configs").mkdir()
        for name in ("RUNTIME.json", "EXISTING_SERVICES.json", "gpu_quarantine.json",
                     "GPU_QUARANTINE_HEALTH.json"):
            shutil.copyfile(ROOT / "configs" / name, self.root / "configs" / name)
        self.runtime = common.read(self.root / "configs/RUNTIME.json")
        self.policy = gpu_query.policy(self.root, self.runtime)
        self.valid = f"{self.runtime['gpu']}, 123, 8192\n"
        self.unknown = f"{gpu_query.QUARANTINED_UUID}, [N/A], [N/A]\n"

    def test_valid_rows_preserved_and_exact_quarantine_recorded(self):
        raw = self.valid + self.unknown + f"{gpu_query.QUARANTINED_UUID}, 456, 12\n"
        rows, snapshot = gpu_query.parse_and_record(self.root, self.runtime, raw)
        self.assertEqual([row["pid"] for row in rows], [123, 456])
        self.assertEqual(snapshot["quarantined_unavailable"][0]["raw"], self.unknown.strip())
        self.assertFalse(snapshot["quarantined_device_release_confirmed"])
        self.assertEqual(common.read(self.root / "audit/GPU_QUARANTINE_FIRST.json"), snapshot)

    def test_selected_preserved_other_unknown_and_partial_unknown_rejected(self):
        protected = common.read(self.root / "configs/EXISTING_SERVICES.json")["processes"][0]["gpu_uuid"]
        rows = [f"{gpu}, [N/A], [N/A]" for gpu in
                (self.runtime["gpu"], protected, "GPU-unreviewed")]
        rows += [f"{gpu_query.QUARANTINED_UUID}, 123, [N/A]",
                 f"{gpu_query.QUARANTINED_UUID}, [N/A], 0",
                 f"{gpu_query.QUARANTINED_UUID}, N/A, N/A"]
        for row in rows:
            with self.subTest(row=row), self.assertRaises(ValueError):
                gpu_query.parse_compute(row, self.policy)

    def test_quarantine_cannot_be_selected_or_protected(self):
        with self.assertRaises(ValueError):
            gpu_query.policy(self.root, dict(self.runtime, gpu=gpu_query.QUARANTINED_UUID))
        path = self.root / "configs/EXISTING_SERVICES.json"
        value = common.read(path)
        value["processes"][0]["gpu_uuid"] = gpu_query.QUARANTINED_UUID
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            gpu_query.policy(self.root, self.runtime)

    def test_changed_health_evidence_rejected(self):
        (self.root / "configs/GPU_QUARANTINE_HEALTH.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "evidence changed"):
            gpu_query.policy(self.root, self.runtime)

    def test_common_and_pid_helper_use_same_strict_global_parser(self):
        with patch.object(common, "ROOT", self.root), patch.object(
                common.subprocess, "check_output", return_value=self.valid + self.unknown) as query:
            self.assertEqual([row["pid"] for row in common.query_compute_rows()], [123])
            self.assertEqual(run_batch.cuda_pids(), {123})
        for call in query.call_args_list:
            self.assertIn("--query-compute-apps=gpu_uuid,pid,used_memory", call.args[0])

    def test_official_tracker_admission_uses_existing_wrapper_hook(self):
        fake = ModuleType("run_tracks")
        fake.check_gpu = lambda *_: self.fail("unwrapped official query invoked")
        fake.main = lambda args: fake.check_gpu(args.gpu_uuid)
        case = ROOT / "cases/short_0358"
        with patch.dict(sys.modules, {"run_tracks": fake}), patch.object(
                track, "resource_check", return_value={"passed": True}) as guard:
            track.track(case, common.read(case / "INPUTS.json"), "source",
                        self.runtime["gpu"], self.root / "unused")
        guard.assert_called_once_with(self.runtime["gpu"], track.os.getpid())
        self.assertFalse((self.root / "unused").exists())
        self.assertNotIn("torch", sys.modules)


if __name__ == "__main__":
    unittest.main()
