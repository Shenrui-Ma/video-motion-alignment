import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('r105_storage_wrapper', ROOT / 'audit/root_run_batch.py')
wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrapper)


class ManagedStoragePeerTests(unittest.TestCase):
    def test_registered_direct_roots_on_both_volumes_allowed(self):
        current = '/home/researcher/h3_runs/r105'
        for folder in ('home', 'data5'):
            path = f'/{folder}/researcher/h3_runs/peer'
            self.assertEqual(wrapper.managed_peer_root(path, current), Path(path).resolve())

    def test_self_rejected(self):
        path = '/home/researcher/h3_runs/r105'
        with self.assertRaises(ValueError):
            wrapper.managed_peer_root(path, path)

    def test_other_user_and_nested_or_other_disk_rejected(self):
        for path in ('/home/another/h3_runs/peer', '/data5/researcher/h3_runs/nested/peer',
                     '/data3/researcher/h3_runs/peer', '/data4/researcher/h3_runs/peer'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                wrapper.managed_peer_root(path)

    def test_runtime_targets_gpu0_and_new_storage(self):
        runtime = json.loads((ROOT / 'configs/runtime.json').read_text())
        self.assertEqual(runtime['expected_gpu_index'], 0)
        self.assertEqual(runtime['gpu_uuid'], 'GPU-REDACTED')
        self.assertEqual(runtime['port'], 8569)
        self.assertEqual(Path(runtime['remote_root']).parent, Path('/home/researcher/h3_runs'))
