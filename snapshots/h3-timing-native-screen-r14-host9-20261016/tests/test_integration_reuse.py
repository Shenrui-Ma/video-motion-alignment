import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r14_host9_integration', ROOT / 'scripts/integration_reuse.py')
reuse = importlib.util.module_from_spec(spec); spec.loader.exec_module(reuse)

class IntegrationTests(unittest.TestCase):
    def test_pending_is_blocking_not_assumed_from41(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'pending'): reuse.validate(d)

    def test_exact_cpu_evidence_and_tamper_guards(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for folder in ['extensions', 'configs', 'scripts', 'tests', 'audit']: (root / folder).mkdir()
            shutil.copytree(ROOT / 'extensions', root / 'extensions', dirs_exist_ok=True)
            for rel in ['scripts/compatibility_bootstrap.py', 'tests/feedback_wrapper_smoke.py', 'configs/parent_core_hashes.json']:
                shutil.copy2(ROOT / rel, root / rel)
            r = {'success':True, 'actual_node_loader_module_alias_tested':True, 'off_equals_native':True,
                 'fixed_mask_equals_feedback':True, 'expanded_readout_common_x0_and_final_bitwise_equal':True,
                 'device':'cpu', 'CUDA_initialized':False, 'loaded_model_weights':False,
                 'comfy_root':reuse.CORE, 'runtime_sha256':reuse.runtime_hashes(root),
                 'comfy_source_sha256':json.loads((root / 'configs/parent_core_hashes.json').read_text())}
            r['core_sha256'] = r['runtime_sha256']['extensions/H3FeedbackRouter/core.py']
            path = root / reuse.LOG
            def save(): path.write_text('H3_FEEDBACK_CPU_SMOKE=' + json.dumps(r) + '\n')
            save(); self.assertEqual(reuse.validate(root)['status'], 'pass')
            r['comfy_root'] = '/host41/ComfyUI'; save()
            with self.assertRaisesRegex(ValueError, 'wrong Comfy'): reuse.validate(root)
            r['comfy_root'] = reuse.CORE; save()
            p = root / 'extensions/H3FeedbackRouter/core.py'; p.write_text(p.read_text() + '\n# change\n')
            with self.assertRaisesRegex(ValueError, 'runtime changed'): reuse.validate(root)

if __name__ == '__main__': unittest.main()
