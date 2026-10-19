import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import track_shared as tracker


class SharedAdmissionTests(unittest.TestCase):
    def query(self, processes='', free=45000, temperature=45, gpu='GPU-selected'):
        return [SimpleNamespace(stdout=processes, stderr=''),
                SimpleNamespace(stdout=f'{gpu}, 1, RTX 6000 Ada, {free}, {temperature}\n', stderr='')]

    def check(self, responses, owners):
        with patch.dict(os.environ, CUDA_VISIBLE_DEVICES='GPU-selected'), \
             patch.object(tracker.subprocess, 'run', side_effect=responses), \
             patch.object(tracker, 'process_uid', side_effect=lambda pid: owners.get(pid)), \
             patch.object(tracker.os, 'getuid', return_value=1000):
            return tracker.resource_check('GPU-selected')

    def test_shared_card_allowed_at_40GiB(self):
        row = self.check(self.query('100, GPU-selected\n200, GPU-selected\n', free=40960), {100:1000, 200:2000})
        self.assertEqual(row['memory_free_mib'], 40960)
        self.assertEqual(row['required_free_bytes'], 40*1024**3)
        self.assertEqual(len(row['processes']), 2)

    def test_own_second_gpu_allowed(self):
        row = self.check(self.query('100, GPU-other\n200, GPU-selected\n'), {100:1000, 200:2000})
        self.assertEqual(row['owned_gpu_uuids_including_selected'], ['GPU-other', 'GPU-selected'])

    def test_own_third_gpu_rejected(self):
        with self.assertRaisesRegex(ValueError, 'two owned'):
            self.check(self.query('100, GPU-one\n101, GPU-two\n'), {100:1000, 101:1000})

    def test_insufficient_memory_or_unhealthy_rejected(self):
        for free, temperature in [(40959,45), (45000,85), (float('nan'),45), (45000,float('nan'))]:
            with self.subTest(free=free, temperature=temperature), self.assertRaises(ValueError):
                self.check(self.query(free=free, temperature=temperature), {})

    def test_wrong_device_rejected(self):
        with self.assertRaises(ValueError):
            self.check(self.query(gpu='GPU-different'), {})
        with patch.dict(os.environ, CUDA_VISIBLE_DEVICES='0'), self.assertRaises(ValueError):
            tracker.resource_check('GPU-selected')

    def test_exited_process_recorded_without_false_occupancy(self):
        row = self.check(self.query('123, GPU-selected\n'), {})
        self.assertTrue(row['processes'][0]['exited_before_uid_read'])

    def test_root_gate_checks_exact_identity_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root/'input.json'
            manifest.write_text('{}')
            control = root/'control'
            arguments = ['--input-manifest', str(manifest), '--output', str(root/'output')]
            def approve(_):
                (control/'go.json').write_bytes((control/'ready.json').read_bytes())
            fake_identity = {'uid':1000, 'start_ticks':'100', 'cmdline_sha256':'abc'}
            with patch.object(tracker, 'verify_runtime'), patch.object(tracker, 'identity', return_value=fake_identity), \
                 patch.object(tracker.time, 'sleep', side_effect=approve):
                record = tracker.register(control, arguments)
            self.assertEqual(record['input_manifest']['sha256'], tracker.sha(manifest))
            self.assertFalse(record['CUDA_started'])
            self.assertEqual(record['required_free_bytes'], 40*1024**3)

    def test_changed_root_gate_fails_before_tracker_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); manifest = root/'input.json'; manifest.write_text('{}'); control = root/'control'
            def alter(_):
                record = json.loads((control/'ready.json').read_text()); record['pid'] += 1
                (control/'go.json').write_text(json.dumps(record))
            with patch.object(tracker, 'verify_runtime'), patch.object(tracker, 'identity', return_value={'uid':1000}), \
                 patch.object(tracker.time, 'sleep', side_effect=alter), self.assertRaisesRegex(ValueError, 'identity differs'):
                tracker.register(control, ['--input-manifest',str(manifest)])


if __name__ == '__main__':
    unittest.main(verbosity=2)
