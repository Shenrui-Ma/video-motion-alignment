"""CPU checks for R149 plans; never run a tracker or access a host."""
import importlib.util
import unittest
from pathlib import Path

P = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("r149_mf_prepare", P / "prepare_batch.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PreparationTests(unittest.TestCase):
    def test_twelve_new_targets_reuse_three_exact_source_caches(self):
        count = 0
        for case in module.read(module.EVAL / "EVALUATION_MANIFEST.json")["cases"]:
            sid = case["source_id"]
            package = P / "batches" / sid
            plan = module.read(package / "configs/PLAN.json")
            self.assertEqual(plan["jobs"], [{"case": sid, "role": arm} for arm in module.ARMS])
            self.assertEqual(plan["new_source_trackers"], 0)
            self.assertEqual(plan["source_cache_count"], 1)
            count += len(plan["jobs"])
            proof = module.read(package / "audit/CPU_PREPARATION.json")
            self.assertFalse(proof["GPU_started"])
            self.assertEqual(proof["network_operations"], 0)
            for rel, digest in module.read(package / "ADMIN_DIFF.json")["byte_exact_execution_and_cleanup"].items():
                self.assertEqual(module.bound(package / rel)["sha256"], digest)
                self.assertEqual(module.bound(module.BASE / rel)["sha256"], digest)
            for name in ("report", "tracks"):
                module.verify_record(proof["source_cache"][name])
            self.assertIsNone(module.read(package / "configs/RUNTIME.json")["gpu"])
        self.assertEqual(count, 12)

    def test_incomplete_batch_cannot_be_frozen(self):
        sid = "short_0252"
        package = P / "batches" / sid
        before = module.bound(package / "configs/PLAN.json")
        with self.assertRaisesRegex(ValueError, "All four actual outputs"):
            module.prepare(sid, finalize=True, gpu="GPU-placeholder", existing_services=P / "absent.json")
        self.assertEqual(module.bound(package / "configs/PLAN.json"), before)
        self.assertFalse((package / "SEAL.json").exists())


if __name__ == "__main__":
    unittest.main()
