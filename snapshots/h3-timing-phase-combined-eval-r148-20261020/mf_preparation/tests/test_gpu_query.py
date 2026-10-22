import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import gpu_query
import run_batch
import peer_support


class QueryTests(unittest.TestCase):
    def test_exact_non_target_double_na_is_recorded_not_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = gpu_query.parse_and_record(
                tmp, "GPU-selected", "GPU-other, [N/A], [N/A]\nGPU-selected, 123, 900")
            self.assertEqual(rows, [{"gpu_uuid": "GPU-selected", "pid": 123, "used_memory_mib": 900}])
            excluded = json.loads((Path(tmp) / "audit/GPU_QUARANTINE_LATEST.json").read_text())["excluded"]
            self.assertEqual(len(excluded), 1)
            self.assertIs(excluded[0]["release_confirmed"], False)

    def test_selected_unavailable_is_rejected(self):
        with self.assertRaises(ValueError):
            gpu_query.parse_compute("GPU-selected, [N/A], [N/A]", "GPU-selected")

    def test_every_other_malformed_row_is_rejected(self):
        for row in ("GPU-other, 123, [N/A]", "GPU-other, [N/A], 9",
                    "GPU-other, 0, 9", "GPU-other, -3, 9", "GPU-other, 123, -1",
                    "unknown, [N/A], [N/A]", "GPU-other, 123"):
            with self.subTest(row=row), self.assertRaises(ValueError):
                gpu_query.parse_compute(row, "GPU-selected")

    def test_cleanup_uses_same_query_path(self):
        with patch.object(run_batch, "cuda_process_rows", return_value=[{"pid": 4}, {"pid": 7}]) as query:
            self.assertEqual(run_batch.cuda_pids(), {4, 7})
            query.assert_called_once_with()

    def test_only_two_lifecycle_query_functions_differ(self):
        base = ROOT.parent.parent / "h3-oxygen-generic-retention-mf-r141b-20261020/scripts"
        for name, changed in (("common.py", "cuda_process_rows"), ("run_batch.py", "cuda_pids")):
            old = ast.parse((base / name).read_text())
            new = ast.parse((ROOT / "scripts" / name).read_text())
            old.body = [n for n in old.body if not isinstance(n, ast.FunctionDef) or n.name != changed]
            new.body = [n for n in new.body if not isinstance(n, ast.FunctionDef) or n.name != changed]
            self.assertEqual(ast.dump(old), ast.dump(new))
        audit = json.loads((ROOT / "ADMIN_DIFF.json").read_text())
        for name, row in audit["scripts"].items():
            got = hashlib.sha256((ROOT / "scripts" / name).read_bytes()).hexdigest()
            self.assertEqual(got, row["prepared_sha256"])
            if name not in ("common.py", "run_batch.py", "peer_support.py"):
                self.assertEqual(got, row["original_sha256"])

    def test_nested_peer_allowlist_keeps_every_identity_check(self):
        base = ROOT.parent.parent / "h3-oxygen-generic-retention-mf-r141b-20261020/scripts/peer_support.py"
        expected = base.read_text().replace(
            "allowed = {Path('/data4/researcher/h3_runs')}",
            "allowed = {Path('/data4/researcher/h3_runs'),\n"
            "               Path('/data4/researcher/h3_runs/timing_phase_combined_r148_20261020/cases')}")
        self.assertEqual((ROOT / "scripts/peer_support.py").read_text(), expected)
        class UnusedIdentity:
            pass
        with patch.object(Path, "exists", return_value=False):
            self.assertEqual(peer_support.peers(
                ["/data4/researcher/h3_runs/timing_phase_combined_r148_20261020/cases/05_real_megumi_v"],
                UnusedIdentity()), [])
            with self.assertRaises(AssertionError):
                peer_support.peers(["/data4/researcher/unknown/cases/05_real_megumi_v"], UnusedIdentity())


if __name__ == "__main__":
    unittest.main()
