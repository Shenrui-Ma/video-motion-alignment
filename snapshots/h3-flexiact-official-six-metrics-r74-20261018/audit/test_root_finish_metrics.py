"""CPU-only administrative regressions; no NVIDIA commands or model imports."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


def load_runner():
    path = Path(__file__).with_name('root_finish_metrics.py')
    fake_service = types.SimpleNamespace()
    spec = importlib.util.spec_from_file_location('root_metric_admin_under_test', path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'service': fake_service}):
        spec.loader.exec_module(module)
    return module, fake_service


class MetricAdministrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.m, self.service = load_runner()
        self.m.ROOT = self.root
        self.m.PEER_ROOTS = (self.root / 'r72', self.root / 'r76')
        self.current = {}
        self.hashed = {}
        self.rows = []
        self.uids = {}
        self.service.current_identity = lambda pid: self.current.get(pid)
        self.service.external_identity = lambda pid: self.hashed.get(pid)
        self.service.compute_processes = lambda: self.rows
        self.service.proc_uid = lambda pid: self.uids.get(pid)
        self.child = {'uid': os.getuid(), 'start_ticks': '801', 'cmdline_sha256': 'child-hash'}

    def peer(self, index=0, pid=775202, gpu='GPU-peer', ticks='8073061'):
        root = self.m.PEER_ROOTS[index]
        current = {'uid': os.getuid(), 'start_ticks': ticks,
                   'cmdline': f'python {root}/scripts/service_entry.py /known/core/main.py --base-directory {root}'}
        identity = {'uid': os.getuid(), 'start_ticks': ticks, 'cmdline_sha256': str(pid) + '-hash'}
        runtime = {'remote_root': str(root), 'uid': os.getuid(), 'gpu_uuid': gpu,
                   'port': 8539 + index, 'core': '/known/core'}
        self.m.save(root / 'configs/runtime.json', runtime)
        self.m.save(root / 'processes/service.json',
                    {'pid': pid, 'identity': current, 'gpu_uuid': gpu, 'port': 8539 + index})
        self.m.save(root / 'configs/admission.json',
                    {'scope': 'own_user_video_jobs', 'permitted_compute_processes': []})
        self.current[pid] = current
        self.hashed[pid] = identity
        self.uids[pid] = os.getuid()
        return root

    def test_no_services(self):
        self.assertEqual(self.m.live_peers(), [])

    def test_restarted_service_uses_current_registry(self):
        self.peer()
        peers = self.m.live_peers()
        self.assertEqual(peers[0]['pid'], 775202)
        self.assertEqual(peers[0]['identity']['start_ticks'], '8073061')

    def test_both_known_producers_are_supported(self):
        self.peer()
        self.peer(1, pid=880001)
        self.assertEqual(len(self.m.live_peers()), 2)

    def test_absent_old_pid_is_skipped(self):
        self.peer(pid=999999991)
        self.current.clear()
        self.assertEqual(self.m.live_peers(), [])

    def test_reused_pid_refused(self):
        self.peer()
        self.current[775202] = {**self.current[775202], 'start_ticks': 'new-generation'}
        with self.assertRaisesRegex(AssertionError, 'reused'):
            self.m.live_peers()

    def test_root_command_binding_required(self):
        root = self.peer()
        self.current[775202]['cmdline'] = 'python unrelated.py'
        record = self.m.read(root / 'processes/service.json')
        record['identity'] = self.current[775202]
        self.m.save(root / 'processes/service.json', record)
        with self.assertRaises(AssertionError):
            self.m.live_peers()

    def test_owner_and_runtime_device_required(self):
        root = self.peer()
        runtime = self.m.read(root / 'configs/runtime.json')
        runtime['gpu_uuid'] = 'GPU-other'
        self.m.save(root / 'configs/runtime.json', runtime)
        with self.assertRaises(AssertionError):
            self.m.live_peers()

    def test_foreign_compute_allowed_without_reading_command(self):
        self.rows = [{'pid': 12, 'gpu_uuid': 'GPU-foreign', 'used_memory_mib': '123'}]
        self.uids[12] = os.getuid() + 1
        self.service.external_identity = lambda pid: self.fail('foreign identity was read')
        result = self.m.check_owned_compute([], 42, self.child)
        self.assertEqual(result['owned_compute'], [])

    def test_unknown_own_compute_refused(self):
        self.rows = [{'pid': 12, 'gpu_uuid': 'GPU-other'}]
        self.uids[12] = os.getuid()
        with self.assertRaisesRegex(AssertionError, 'Unregistered'):
            self.m.check_owned_compute([], 42, self.child)

    def test_current_known_peer_and_child_allowed(self):
        self.peer()
        self.rows = [{'pid': 775202, 'gpu_uuid': 'GPU-peer'}, {'pid': 42, 'gpu_uuid': self.m.GPU}]
        self.uids[42] = os.getuid()
        self.hashed[42] = self.child
        result = self.m.check_owned_compute(self.m.live_peers(), 42, self.child)
        self.assertEqual(len(result['owned_gpu_uuids_including_reserved_services']), 2)

    def test_cuda_identity_and_device_must_still_match(self):
        self.peer()
        peers = self.m.live_peers()
        self.rows = [{'pid': 775202, 'gpu_uuid': 'GPU-peer'}]
        self.hashed[775202] = {**self.hashed[775202], 'start_ticks': 'new'}
        with self.assertRaisesRegex(AssertionError, 'identity changed'):
            self.m.check_owned_compute(peers, 42, self.child)
        self.hashed[775202] = peers[0]['identity']
        self.rows[0]['gpu_uuid'] = 'GPU-unexpected'
        with self.assertRaisesRegex(AssertionError, 'device differs'):
            self.m.check_owned_compute(peers, 42, self.child)

    def test_three_devices_refused_even_before_peer_cuda_load(self):
        self.peer(gpu='GPU-peer-A')
        self.peer(1, pid=880001, gpu='GPU-peer-B')
        with self.assertRaisesRegex(AssertionError, 'exceed two'):
            self.m.check_owned_compute(self.m.live_peers(), 42, self.child)

    def test_register_and_cleanup_preserve_unrelated_entries(self):
        root = self.peer()
        unrelated = {'pid': 24, 'identity': {'uid': os.getuid(), 'start_ticks': '45', 'cmdline_sha256': 'keep'}}
        original = self.m.read(root / 'configs/admission.json')
        original['permitted_compute_processes'] = [unrelated]
        self.m.save(root / 'configs/admission.json', original)
        self.m.register(root, 42, self.child, True)
        self.m.register(root, 42, self.child, True)
        self.assertEqual(len(self.m.read(root / 'configs/admission.json')['permitted_compute_processes']), 2)
        self.m.register(root, 42, self.child, False)
        self.assertEqual(self.m.read(root / 'configs/admission.json'), original)

    def test_registration_pid_collision_refused(self):
        root = self.peer()
        self.m.register(root, 42, self.child, True)
        with self.assertRaises(AssertionError):
            self.m.register(root, 42, {**self.child, 'start_ticks': 'new'}, True)

    def test_cpu_lock_contention_retries_and_then_completes(self):
        audit = self.root / 'lock_audit'
        audit.mkdir()
        lock = self.root / 'consumer.lock'
        holder = lock.open('w')
        self.addCleanup(holder.close)
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        script = self.root / 'lock_child.py'
        # Use a real competing flock. macOS reports EAGAIN=35; the deployed
        # Linux scoring subprocess reports 11, so normalize only this test child.
        script.write_text('import fcntl, sys\nf=open(sys.argv[1],"w")\n'
                          'try:\n fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)\n'
                          'except BlockingIOError as e:\n raise BlockingIOError(11, str(e)) from e\n'
                          'print("locked")\n')
        waits = []
        def release(seconds):
            waits.append(seconds)
            fcntl.flock(holder, fcntl.LOCK_UN)
        with patch.object(self.m.time, 'sleep', release):
            self.m.cpu_command([sys.executable, str(script), str(lock)], dict(os.environ), audit, 'score')
        self.assertEqual(waits, [10])
        self.assertIn('BlockingIOError: [Errno 11]', (audit / 'score_attempt1.log').read_text())
        self.assertIn('locked', (audit / 'score_attempt2.log').read_text())

    def test_cpu_nonlock_failure_is_not_retried(self):
        audit = self.root / 'failure_audit'
        audit.mkdir()
        with patch.object(self.m.time, 'sleep', side_effect=AssertionError('unexpected retry')):
            with self.assertRaisesRegex(RuntimeError, 'CPU command failed'):
                self.m.cpu_command([sys.executable, '-c', 'raise ValueError("bad input")'],
                                   dict(os.environ), audit, 'score')
        self.assertEqual(len(list(audit.glob('*.log'))), 1)

    def test_cpu_lock_timeout_is_bounded(self):
        audit = self.root / 'timeout_audit'
        audit.mkdir()
        result = subprocess.CompletedProcess(['mock'], 1, '',
                                             'flock\nBlockingIOError: [Errno 11] locked')
        with patch.object(self.m.subprocess, 'run', return_value=result), \
                patch.object(self.m.time, 'monotonic', side_effect=[0, 7201]), \
                patch.object(self.m.time, 'sleep', side_effect=AssertionError('unexpected retry')):
            with self.assertRaises(RuntimeError):
                self.m.cpu_command(['mock'], {}, audit, 'score')


if __name__ == '__main__':
    unittest.main(verbosity=2)
