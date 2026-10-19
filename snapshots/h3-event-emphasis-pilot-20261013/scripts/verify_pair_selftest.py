#!/usr/bin/env python3
"""Small CPU tests; fixtures are isolated in auto-deleted temporary directories."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("emphasis_verify_under_test", ROOT / "scripts/verify_pair.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class ArchiveTools(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((ROOT / "configs/preregistered_plan.json").read_text())

    def hook(self, factor=2):
        return {"run_id": verify.RUNS[factor-1], "factor": factor, "expected_num_blocks": 50,
                "formal_planned_sampling_steps": 20, "expected_sampling_steps": 20,
                "started_calls": 1000, "completed_calls": 1000, "completed_forward_calls": 20,
                "calls_by_block": [20] * 50, "calls_by_forward": [50] * 20,
                "native_override_calls": 1000 if factor == 2 else 0,
                "pixel_interval_inclusive": [39, 44], "status": "sampling",
                "validated_layout": {"seq_len": 87583, "key_interval_half_open": [19217, 21103],
                    "query_interval_half_open": [59293, 61179], "latent_interval_half_open": [12, 14],
                    "pixel_interval_inclusive": [39, 44], "position_bin_coverage_inclusive": [39, 46],
                    "frame_rows": 943, "reference_kind": "video"}}

    def test_complete_hook_both_factors(self):
        for factor in (1, 2):
            self.assertEqual(verify.validate_hook(self.hook(factor), verify.RUNS[factor-1], factor, self.plan), [])

    def test_missing_block_is_rejected(self):
        hook = self.hook()
        hook["calls_by_block"][49] = 19
        self.assertIn("hook calls_by_block differs from expected", verify.validate_hook(hook, verify.RUNS[1], 2, self.plan))

    def test_missing_forward_is_rejected(self):
        hook = self.hook()
        hook["completed_forward_calls"] = 19
        self.assertTrue(verify.validate_hook(hook, verify.RUNS[1], 2, self.plan))

    def test_wrong_temporal_span_is_rejected(self):
        hook = self.hook()
        hook["validated_layout"]["key_interval_half_open"] = [19216, 21103]
        self.assertTrue(verify.validate_hook(hook, verify.RUNS[1], 2, self.plan))

    def test_factor_one_override_is_rejected(self):
        hook = self.hook(1)
        hook["native_override_calls"] = 1000
        self.assertTrue(verify.validate_hook(hook, verify.RUNS[0], 1, self.plan))

    def test_failed_hook_is_rejected(self):
        hook = self.hook()
        hook["status"] = "failed"
        self.assertIn("hook reports failure", verify.validate_hook(hook, verify.RUNS[1], 2, self.plan))

    def test_declared_graph_pair_normalizes(self):
        graphs = [json.loads((ROOT / "configs" / (name + ".json")).read_text()) for name in verify.RUNS]
        self.assertEqual(verify.normalize_graph(graphs[0]), verify.normalize_graph(graphs[1]))
        mutated = copy.deepcopy(graphs[1])
        _, ref = verify.one_node(mutated, "H3EventAuditReference")
        ref["prompt"] += "changed"
        self.assertNotEqual(verify.normalize_graph(graphs[0]), verify.normalize_graph(mutated))

    def test_tensor_signature_and_bad_dtype(self):
        value = {"sha256": "a" * 64, "shape": [2, 3], "dtype": "torch.float32", "tensor_file": "x.pt"}
        self.assertEqual(verify.signature(value)["bytes"], 24)
        self.assertEqual(verify.canonical(value), verify.canonical(dict(value, tensor_file="y.pt")))
        value["dtype"] = "unsupported"
        with self.assertRaises(ValueError):
            verify.signature(value)

    def test_raw_storage_hashes_without_pickle(self):
        with tempfile.TemporaryDirectory(prefix="h3-emphasis-storage-test-") as directory:
            path = Path(directory) / "toy.pt"
            data = b"controlled tensor bytes"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("toy/data.pkl", b"THIS IS NOT PICKLE AND MUST NEVER EXECUTE")
                archive.writestr("toy/data/0", data)
            self.assertEqual(verify.raw_storages(path), verify.Counter({(hashlib.sha256(data).hexdigest(), len(data)): 1}))

    def test_empty_archive_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="h3-emphasis-empty-test-") as directory:
            path = Path(directory) / "empty.pt"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("fake/data.pkl", "fake")
            with self.assertRaises(ValueError):
                verify.raw_storages(path)

    def test_only_benchmark_is_pending_not_formal(self):
        with tempfile.TemporaryDirectory(prefix="h3-emphasis-benchmark-test-") as directory:
            root = Path(directory)
            (root / "configs").mkdir()
            (root / "outputs").mkdir()
            (root / "configs/preregistered_plan.json").write_text(json.dumps(self.plan))
            (root / "outputs" / (verify.BENCHMARK + "_00001_.mp4")).write_bytes(b"not a formal video")
            result = verify.validate(root)
            self.assertEqual(result["status"], "pending")
            self.assertEqual(result["formal_count_passed"], 0)
            self.assertEqual(result["technical_output_excluded"], verify.BENCHMARK)
            self.assertEqual(result["errors"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
