import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import gpu_query
import service
from observer_import import t


class Quarantine(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "configs").mkdir()
        for name in ("runtime.json", "gpu_quarantine.json", "GPU_QUARANTINE_HEALTH.json"):
            shutil.copyfile(ROOT / "configs" / name, self.root / "configs" / name)
        self.runtime = json.loads((self.root / "configs/runtime.json").read_text())
        self.policy = gpu_query.policy(self.root, self.runtime)
        self.valid = f"{self.runtime['gpu_uuid']}, 123, 8192\n"
        self.bad = f"{gpu_query.QUARANTINED_UUID}, [N/A], [N/A]\n"

    def test_valid_rows_preserved_including_numeric_quarantined_card(self):
        raw = self.valid + f"{gpu_query.QUARANTINED_UUID}, 456, 12\n"
        rows, unknown = gpu_query.parse_compute(raw, self.policy)
        self.assertEqual([row["pid"] for row in rows], [123, 456])
        self.assertEqual(unknown, [])

    def test_only_exact_evidence_bound_unknown_row_excluded_and_recorded(self):
        rows, snapshot = gpu_query.parse_and_record(
            self.root, self.runtime, self.valid + self.bad)
        self.assertEqual([row["pid"] for row in rows], [123])
        self.assertEqual(snapshot["quarantined_unavailable"][0]["raw"], self.bad.strip())
        self.assertFalse(snapshot["quarantined_device_release_confirmed"])
        first = (self.root / "audit/GPU_QUARANTINE_FIRST.json").read_bytes()
        gpu_query.parse_and_record(self.root, self.runtime, self.bad)
        self.assertEqual(first, (self.root / "audit/GPU_QUARANTINE_FIRST.json").read_bytes())

    def test_selected_and_other_unknown_rows_fail(self):
        for gpu in (self.runtime["gpu_uuid"], self.runtime["decoder_gpu_uuid"],
                    self.runtime["preserved_user_service_gpu"], "GPU-unreviewed"):
            with self.subTest(gpu=gpu), self.assertRaises(ValueError):
                gpu_query.parse_compute(f"{gpu}, [N/A], [N/A]\n", self.policy)

    def test_partial_unknown_on_quarantined_gpu_fails(self):
        for pid, memory in (("[N/A]", "1"), ("12", "[N/A]"), ("N/A", "N/A")):
            with self.subTest(pid=pid, memory=memory), self.assertRaises(ValueError):
                gpu_query.parse_compute(f"{gpu_query.QUARANTINED_UUID}, {pid}, {memory}", self.policy)

    def test_quarantined_selected_preserved_or_requested_device_rejected(self):
        for field in ("gpu_uuid", "decoder_gpu_uuid", "preserved_user_service_gpu"):
            runtime = dict(self.runtime, **{field: gpu_query.QUARANTINED_UUID})
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "selected or preserved"):
                gpu_query.policy(self.root, runtime)
        with self.assertRaises(ValueError):
            gpu_query.policy(self.root, self.runtime, gpu_query.QUARANTINED_UUID)

    def test_evidence_tampering_fails(self):
        (self.root / "configs/GPU_QUARANTINE_HEALTH.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "evidence changed"):
            gpu_query.policy(self.root, self.runtime)

    def test_service_query_path_used_by_cleanup_watchdog_and_own_nvml(self):
        with patch.object(service, "RUN", self.root), patch.object(
                service.subprocess, "run", return_value=SimpleNamespace(stdout=self.valid + self.bad)):
            rows = service.compute_processes()
        self.assertEqual(rows, [{"gpu_uuid": self.runtime["gpu_uuid"], "pid": 123,
                                 "used_memory_mib": "8192"}])

    def test_transport_query_path_used_by_observer_and_decoder(self):
        outputs = [f"{self.runtime['decoder_gpu_uuid']}, 12000, 30000, 30\n",
                   self.valid + self.bad]
        with patch.object(t, "ROOT", self.root), patch.object(
                t.subprocess, "check_output", side_effect=outputs) as query:
            _, rows, snapshot = t.query_resource_state(self.runtime["decoder_gpu_uuid"])
        self.assertEqual([row["pid"] for row in rows], [123])
        self.assertEqual(len(snapshot["quarantine"]["quarantined_unavailable"]), 1)
        self.assertIn("--query-compute-apps=gpu_uuid,pid,used_memory", query.call_args_list[1].args[0])

    def test_transport_selected_unknown_gpu_still_fails(self):
        outputs = [f"{self.runtime['decoder_gpu_uuid']}, 12000, 30000, [N/A]\n",
                   self.valid + self.bad]
        with patch.object(t, "ROOT", self.root), patch.object(
                t.subprocess, "check_output", side_effect=outputs):
            with self.assertRaises(t.AdmissionIntegrityError):
                t.query_resource_state(self.runtime["decoder_gpu_uuid"])


if __name__ == "__main__":
    unittest.main()
