import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r83_archive', HERE / 'archive_failed_attempt.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('processes', 'logs', 'configs', 'audit/x0/run', 'output', 'temp',
                     'analysis/postrun', 'audit/http_observation_recovery_v2'):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        owner = {'pid': 100, 'identity': {'uid': os.getuid(), 'start_ticks': '321'},
                 'gpu_uuid': 'gpu', 'port': 8549}
        self.put('processes/service.json', owner)
        self.put('processes/service_100.json', owner)
        self.put('processes/watchdog.json', {'pid': 101, 'identity':
                  {'uid': os.getuid(), 'start_ticks': '322'}})
        self.put('configs/runtime.json', {'gpu_uuid': 'gpu', 'port': 8549})
        self.put('configs/scientific_contract.json', {'cases': [{'source_id': 'short_0131'}]})
        self.put('deploy_manifest.json', {'files': {'configs/runtime.json': {}}})
        self.put('logs/' + m.FIRST_RUN + '_job.json', {'status': 'queued'})
        (self.root / 'audit/x0/run/partial.pt').write_bytes(b'preserve tensor evidence')
        (self.root / 'audit/r83_shared_noise.pt').write_bytes(b'noise')
        (self.root / 'analysis/postrun/verify_pair.py').write_text('keep code')
        (self.root / 'audit/first_attempt').mkdir()
        self.put('audit/first_attempt/FAILURE.json', {'error': 'HTTP timeout'})
        self.destination = self.root / 'audit/http_observation_recovery_v2/attempts/attempt1'

    def put(self, path, data):
        (self.root / path).write_text(json.dumps(data))

    def call(self, **kwargs):
        return m.archive(self.root, self.destination, 100, '321',
                         proc_exists=lambda pid: False, query_cuda=lambda: set(), **kwargs)

    def test_dry_run_does_not_mutate(self):
        value = self.call()
        self.assertFalse(self.destination.exists())
        self.assertTrue((self.root / 'processes/service.json').exists())
        self.assertIn('audit/x0/run/partial.pt', value['inventory'])

    def test_archive_preserves_all_evidence_and_scientific_code(self):
        value = self.call(execute=True)
        self.assertEqual(value['status'], 'ARCHIVED_VERIFIED')
        self.assertTrue(value['inventory_equal'])
        self.assertEqual((self.destination / 'payload/audit/x0/run/partial.pt').read_bytes(),
                         b'preserve tensor evidence')
        self.assertFalse((self.root / 'processes/service.json').exists())
        self.assertTrue((self.root / 'processes').is_dir())
        self.assertEqual((self.root / 'analysis/postrun/verify_pair.py').read_text(), 'keep code')
        self.assertTrue((self.root / 'audit/first_attempt/FAILURE.json').exists())

    def test_live_or_recycled_pid_blocks_before_mutation(self):
        with self.assertRaisesRegex(RuntimeError, 'PID still exists'):
            m.archive(self.root, self.destination, 100, '321', execute=True,
                      proc_exists=lambda pid: pid == 101, query_cuda=lambda: set())
        self.assertFalse(self.destination.exists())
        self.assertTrue((self.root / 'processes/service.json').exists())

    def test_cuda_inventory_blocks(self):
        with self.assertRaisesRegex(RuntimeError, 'CUDA inventory'):
            m.archive(self.root, self.destination, 100, '321', execute=True,
                      proc_exists=lambda pid: False, query_cuda=lambda: {100})
        self.assertFalse(self.destination.exists())

    def test_registry_generation_change_blocks(self):
        with self.assertRaisesRegex(RuntimeError, 'different generation'):
            m.archive(self.root, self.destination, 100, '999', execute=True,
                      proc_exists=lambda pid: False, query_cuda=lambda: set())
        self.assertFalse(self.destination.exists())

    def test_sealed_overlap_blocks(self):
        self.put('deploy_manifest.json', {'files': {'logs/frozen.json': {}}})
        with self.assertRaisesRegex(RuntimeError, 'overlaps sealed'):
            self.call(execute=True)
        self.assertFalse(self.destination.exists())

    def test_later_run_blocks(self):
        self.put('logs/r83_short_0131_seed2026101701_forced_job.json', {})
        with self.assertRaisesRegex(RuntimeError, 'later job'):
            self.call(execute=True)
        self.assertFalse(self.destination.exists())

    def test_nested_symlink_is_archived_without_following(self):
        outside = self.root / 'keep.txt'
        outside.write_text('external content')
        (self.root / 'output/link').symlink_to(outside)
        value = self.call(execute=True)
        self.assertEqual(value['inventory']['output/link']['kind'], 'symlink')
        self.assertEqual(outside.read_text(), 'external content')
        self.assertTrue((self.destination / 'payload/output/link').is_symlink())

    def test_top_level_symlink_blocks(self):
        (self.root / 'temp').rmdir()
        (self.root / 'temp').symlink_to(self.root / 'output')
        with self.assertRaisesRegex(RuntimeError, 'cannot be a symlink'):
            self.call(execute=True)

    def test_existing_archive_cannot_be_reused(self):
        self.call(execute=True)
        with self.assertRaisesRegex(RuntimeError, 'destination already exists'):
            self.call(execute=True)

    def test_late_process_reappearance_blocks(self):
        observations = [set(), {100}]
        with self.assertRaisesRegex(RuntimeError, 'CUDA inventory'):
            m.archive(self.root, self.destination, 100, '321', execute=True,
                      proc_exists=lambda pid: False, query_cuda=lambda: observations.pop(0))
        self.assertFalse(self.destination.exists())

    def test_inventory_hash_includes_noise_and_partial(self):
        value = self.call()
        for name in ('audit/r83_shared_noise.pt', 'audit/x0/run/partial.pt'):
            self.assertEqual(value['inventory'][name]['sha256'], m.sha(self.root / name))


if __name__ == '__main__':
    unittest.main()
