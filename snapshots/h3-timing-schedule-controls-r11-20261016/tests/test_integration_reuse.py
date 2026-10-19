import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r11_integration_reuse', ROOT / 'scripts/integration_reuse.py')
reuse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reuse)


class IntegrationReuseTests(unittest.TestCase):
    def test_r9_real_cpu_pass_and_runtime_identity(self):
        result = reuse.validate(ROOT)
        self.assertEqual(result['status'], 'pass')
        self.assertFalse(result['new_gpu_benchmark'])
        self.assertIn('extensions/H3FeedbackRouter/core.py', result['runtime_files_checked'])

    def test_changed_runtime_cannot_reuse_old_integration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['configs', 'audit']:
                (root / name).mkdir()
            for name in ['configs/integration_reuse_manifest.json', 'audit/parent_r9_bundle_manifest.json',
                         'audit/parent_r9_real_comfy_cpu_smoke.log']:
                shutil.copy2(ROOT / name, root / name)
            shutil.copytree(ROOT / 'extensions', root / 'extensions',
                            ignore=shutil.ignore_patterns('__pycache__'))
            path = root / 'extensions/H3FeedbackRouter/core.py'
            path.write_text(path.read_text() + '\n# changed implementation\n')
            with self.assertRaisesRegex(ValueError, 'runtime changed'):
                reuse.validate(root)


if __name__ == '__main__':
    unittest.main()
