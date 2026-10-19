import importlib.util
from pathlib import Path
import tempfile
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r9_warmup_reuse', ROOT / 'scripts/warmup_reuse.py')
warmup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(warmup)


class WarmupTests(unittest.TestCase):
    def test_archived_success_and_backend_identity(self):
        result = warmup.validate(ROOT)
        self.assertEqual(result['status'], 'pass')
        self.assertFalse(result['new_gpu_warmup'])

    def test_changed_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'configs').mkdir()
            shutil.copy2(ROOT / 'configs/warmup_reuse_manifest.json', root / 'configs/warmup_reuse_manifest.json')
            shutil.copytree(ROOT / 'audit/r6_warmup', root / 'audit/r6_warmup')
            p = root / 'audit/r6_warmup/warmup_gate.json'
            p.write_text(p.read_text() + ' ')
            with self.assertRaisesRegex(ValueError, 'changed archived'):
                warmup.validate(root)


if __name__ == '__main__':
    unittest.main()
