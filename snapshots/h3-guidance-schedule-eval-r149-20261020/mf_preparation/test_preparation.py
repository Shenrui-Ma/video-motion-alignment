"""CPU checks for R149 plans; never run a tracker or access a host."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
            runtime = module.read(package / "configs/RUNTIME.json")
            if proof["final_inputs_bound"]:
                self.assertEqual(runtime["gpu"], "GPU-REDACTED")
                self.assertEqual(runtime["peer_roots"], [])
            else:
                self.assertIsNone(runtime["gpu"])
        self.assertEqual(count, 12)

    def test_incomplete_batch_cannot_be_frozen(self):
        sid = "short_0252"
        package = P / "batches" / sid
        before = module.bound(package / "configs/PLAN.json")
        # Real cabin results may now be complete. Use an isolated missing-input
        # fixture so the rejection test cannot mutate a live preparation package.
        with tempfile.TemporaryDirectory(dir=module.EVAL / "audit") as temporary:
            empty = Path(temporary)
            (empty / "EVALUATION_MANIFEST.json").write_bytes(
                (module.EVAL / "EVALUATION_MANIFEST.json").read_bytes())
            with patch.object(module, "EVAL", empty), patch.object(module, "ROOT", empty / "mf"):
                with self.assertRaisesRegex(ValueError, "All four actual outputs"):
                    module.prepare(sid, finalize=True, gpu="GPU-placeholder", existing_services=P / "absent.json")
        self.assertEqual(module.bound(package / "configs/PLAN.json"), before)

    def test_final_release_adapter_changes_only_unknown_summary(self):
        original = (module.BASE / "audit/final_release.py").read_text()
        adapter = (P / "admin/final_release.py").read_text()
        expected = original.replace(
            " rows=cuda_process_rows();trackers=[read(x['file'])['identity'] for x in all_releases]",
            " rows=cuda_process_rows();trackers=[read(x['file'])['identity'] for x in all_releases]\n"
            " quarantine=read(ROOT/'audit/GPU_QUARANTINE_LATEST.json');excluded=quarantine['excluded']")
        expected = expected.replace("fresh_own_cuda_absent=not own,other_owned_cuda=own,",
            "fresh_own_cuda_absent=(None if excluded else not own),other_owned_cuda=own,"
            "unqueryable_GPU_allocations=excluded,GPU_query_evidence=bound(ROOT/'audit/GPU_QUARANTINE_LATEST.json'),")
        self.assertEqual(adapter, expected)
        for excluded, own, result in [([], [], True), ([], [1], False), ([1], [], None)]:
            self.assertIs(None if excluded else not own, result)


if __name__ == "__main__":
    unittest.main()
