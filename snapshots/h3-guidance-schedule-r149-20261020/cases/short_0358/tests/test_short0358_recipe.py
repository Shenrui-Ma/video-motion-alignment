"""CPU regression for historical recipe binding and cross-filesystem noise reuse."""
import copy
import errno
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import r132_contract as contract


class RecipeTests(unittest.TestCase):
    def test_exact_historical_inputs_and_schedule_only_graph_changes(self):
        science = contract.science()
        history = contract.read(ROOT / "design/HISTORICAL_FIXED.json")
        old = history["router_node_50"]["inputs"]
        cached = contract.read(ROOT / "design/parent_cached_graph.json")
        native = contract.read(ROOT / "design/parent_native_graph.json")
        self.assertEqual((old["start_frame"], old["end_frame"], old["step_start"], old["step_end"]),
                         (0, 104, 6, 15))
        self.assertEqual(native["6"]["inputs"]["noise_seed"], 2026101701)
        for c in science["cases"]:
            self.assertEqual(c["prompt"], native["5"]["inputs"]["prompt"])
            self.assertEqual(c["physical_query_window"], [0, 104])
            self.assertEqual(c["valid_frame_count"], 105)
            self.assertEqual(c["phase_displacement"], 0)
            graph = contract.expected_graph(c["run_id"])
            for node in ("1", "3", "4", "7", "8", "9", "10", "11", "12", "13", "41"):
                self.assertEqual(graph[node], cached[node], node)
            self.assertEqual(graph["50"]["inputs"]["positive"], ["51", 0])
            self.assertEqual(graph["50"]["inputs"]["alpha"], .25 if c["arm"] == "global_weak" else 1.)
            self.assertEqual(graph["52"]["inputs"]["length"], 107)
        self.assertEqual(science["parent_noise_sha256"],
                         "5439f8f84b471b7d53e431b886c730fc7e78492b159ce7658e08a2bad046b310")

    def test_noise_cross_filesystem_fallback_and_reuse(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.pt"
            source.write_bytes(b"immutable original video+audio noise")
            scientific = {"parent_noise_file": str(source), "parent_noise_sha256": contract.sha(source),
                          "noise_pair_id": "pair"}
            with patch.object(contract, "validate_job", return_value={"run": "test"}), \
                 patch.object(contract, "science", return_value=scientific), \
                 patch.object(contract.os, "link", side_effect=OSError(errno.EXDEV, "cross filesystem")):
                contract.prepare_loader_inputs("test", root)
                contract.prepare_loader_inputs("test", root)
            target = root / "audit/pair_noise.pt"
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(contract.sha(target), scientific["parent_noise_sha256"])
            self.assertFalse(target.is_symlink())

    def test_different_noise_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.pt"
            source.write_bytes(b"noise")
            scientific = {"parent_noise_file": str(source), "parent_noise_sha256": "0" * 64,
                          "noise_pair_id": "pair"}
            with patch.object(contract, "validate_job", return_value={}), \
                 patch.object(contract, "science", return_value=scientific):
                with self.assertRaisesRegex(ValueError, "original AV noise differs"):
                    contract.prepare_loader_inputs("test", root)
            self.assertFalse((root / "audit/pair_noise.pt").exists())


if __name__ == "__main__":
    unittest.main()
