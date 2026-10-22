"""CPU-only safety tests. No torch import, CUDA allocation, SSH, or live files."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

STAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE / 'scripts'))
import startup_barrier as b
import coordinate_launch as c
import service
import primary_lifecycle as life


def ident(label):
    return {'uid': os.getuid(), 'start_ticks': str(label),
            'cmdline_sha256': hashlib.sha256(str(label).encode()).hexdigest()}


class BarrierTests(unittest.TestCase):
    def test_instance_constants_agree(self):
        self.assertEqual(c.service.RUN, b.RUN)
        self.assertEqual(c.service.PORT, b.PORT)
        self.assertEqual(c.service.GPU, b.GPU)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'transfer'
        self.primary = Path(self.tmp.name) / 'primary'
        for root in (self.root, self.primary):
            (root / 'configs').mkdir(parents=True)
            (root / 'processes').mkdir()
            (root / 'logs').mkdir()
        self.primary_peer = {'pid': 11111, 'identity': ident('primary')}
        self.coordinator = {'pid': os.getpid(), 'identity': ident('coordinator')}
        self.child = {'pid': 22222, 'identity': ident('child')}
        self.identities = {p['pid']: p['identity'] for p in (self.primary_peer, self.coordinator, self.child)}
        self.reader = self.identities.get
        now = time.time()
        self.gate = dict(schema=1, launch_id='a' * 32, root=str(self.root), gpu_uuid=b.GPU,
                         port=b.PORT, primary_root=str(self.primary), primary=self.primary_peer,
                         coordinator=self.coordinator, created_unix=now, expires_unix=now + 30)
        b.atomic_json(self.root / 'processes/pre_cuda_gate.json', self.gate)
        self.ready = {k: self.gate[k] for k in ('schema', 'launch_id', 'root', 'gpu_uuid', 'port')}
        self.ready.update(self.child)
        self.put_admissions()

    def tearDown(self):
        self.tmp.cleanup()

    def put_admissions(self):
        for root, peer in ((self.root, self.primary_peer), (self.primary, self.child)):
            b.atomic_json(root / 'configs/admission.json', dict(scope='own_user_video_jobs',
                          existing_comfy_port=None, permitted_compute_processes=[peer]))

    def release(self):
        return dict(self.ready, expires_unix=self.gate['expires_unix'], primary=self.primary_peer,
                    coordinator=self.coordinator,
                    primary_admission_sha256=b.sha256(self.primary / 'configs/admission.json'),
                    transfer_admission_sha256=b.sha256(self.root / 'configs/admission.json'))

    def test_exact_release_passes(self):
        b.validate_gate(self.root, reader=self.reader)
        b.validate_release(self.root, self.gate, self.ready, self.release(), reader=self.reader)

    def test_stale_pid_start_ticks_hash_gpu_and_nonce_rejected(self):
        for field, value in [('pid', 22223), ('identity', ident('other')),
                             ('gpu_uuid', 'GPU-other'), ('launch_id', 'b' * 32)]:
            with self.subTest(field=field):
                release = self.release()
                release[field] = value
                with self.assertRaisesRegex(RuntimeError, 'Stale/mismatched'):
                    b.validate_release(self.root, self.gate, self.ready, release, reader=self.reader)

    def test_primary_restart_or_absence_rejected(self):
        for value in (None, ident('primary_restart')):
            self.identities[self.primary_peer['pid']] = value
            with self.assertRaisesRegex(RuntimeError, 'Peer missing/restarted'):
                b.validate_release(self.root, self.gate, self.ready, self.release(), reader=self.reader)

    def test_expired_release_rejected(self):
        release = self.release()
        release['expires_unix'] = time.time() - 1
        with self.assertRaisesRegex(RuntimeError, 'Release expired'):
            b.validate_release(self.root, self.gate, self.ready, release, reader=self.reader)

    def test_admission_tamper_rejected(self):
        release = self.release()
        (self.primary / 'configs/admission.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'admission changed'):
            b.validate_release(self.root, self.gate, self.ready, release, reader=self.reader)

    def test_no_broad_or_duplicate_pid_permission(self):
        path = self.primary / 'configs/admission.json'
        for rows in ([], [dict(self.child, identity={})], [self.child, self.child]):
            b.atomic_json(path, dict(scope='own_user_video_jobs', existing_comfy_port=None,
                                    permitted_compute_processes=rows))
            with self.assertRaises(RuntimeError):
                b.require_admitted(path, self.child)

    def test_atomic_compare_restore_preserves_concurrent_edit(self):
        path = self.primary / 'configs/admission.json'
        original = path.read_bytes()
        new = c.add_exact_peer(original, {'pid': 33333, 'identity': ident('new')})
        c.compare_replace(path, original, new)
        self.assertEqual(path.read_bytes(), new)
        c.compare_replace(path, new, original)
        self.assertEqual(path.read_bytes(), original)
        path.write_bytes(b'{"root_edit": true}')
        with self.assertRaisesRegex(RuntimeError, 'changed concurrently'):
            c.compare_replace(path, new, original)
        self.assertEqual(path.read_bytes(), b'{"root_edit": true}')

    def test_unrelated_pid_cleanup_refused(self):
        record = {'pid': 1234, 'identity': {'uid': os.getuid(), 'start_ticks': '1',
                                         'cmdline': str(service.RUN) + '/scripts/run_queue.py'}}
        with mock.patch.object(service, 'current_identity', return_value=dict(record['identity'], start_ticks='2')):
            with mock.patch.object(c.os, 'kill') as kill:
                with self.assertRaisesRegex(RuntimeError, 'changed/unowned'):
                    c.stop_process(record)
                kill.assert_not_called()

    def natural_completion_records(self):
        registry = {'pid': self.primary_peer['pid'], 'identity': {'uid': os.getuid(),
                    'start_ticks': '123', 'cmdline': 'verified primary original command'},
                    'gpu_uuid': c.PRIMARY_GPU, 'port': c.PRIMARY_PORT}
        b.atomic_json(self.primary / 'processes/service.json', registry)
        b.atomic_json(self.primary / 'logs/controller_state.json',
                      {'status': 'all_queued_jobs_complete', 'completed': ['original_jobs']})
        cleanup = {'pid': registry['pid'], 'service_record': registry,
                   'process_absent': True, 'own_compute_absent': True}
        b.atomic_json(self.primary / 'processes/cleanup.json', cleanup)
        return registry, cleanup

    def test_exact_primary_natural_completion_can_continue(self):
        registry, _ = self.natural_completion_records()
        status = life.primary_state(self.primary_peer, registry, self.primary,
                                    reader=lambda _: None, pid_exists=lambda _: False)
        self.assertEqual(status, 'complete')

    def test_live_primary_lifecycle_does_not_require_http_listener(self):
        registry, _ = self.natural_completion_records()
        with mock.patch.object(service, 'queue_at', side_effect=ConnectionRefusedError) as http:
            status = life.primary_state(self.primary_peer, registry, self.primary,
                                        reader=lambda _: self.primary_peer['identity'])
            self.assertEqual(status, 'live')
            http.assert_not_called()
        tree = ast.parse((STAGE / 'scripts/coordinate_launch.py').read_text())
        guards = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'guard']
        self.assertEqual(len(guards), 1)
        names = [n.func.id for n in ast.walk(guards[0]) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        self.assertNotIn('exact_primary', names)

    def test_abnormal_primary_exit_cannot_continue(self):
        registry, _ = self.natural_completion_records()
        b.atomic_json(self.primary / 'logs/controller_state.json', {'status': 'failed'})
        with self.assertRaisesRegex(RuntimeError, 'without completing'):
            life.primary_state(self.primary_peer, registry, self.primary,
                               reader=lambda _: None, pid_exists=lambda _: False)

    def test_primary_new_registry_or_reused_pid_cannot_continue(self):
        registry, _ = self.natural_completion_records()
        b.atomic_json(self.primary / 'processes/service.json', dict(registry, pid=55555))
        with self.assertRaisesRegex(RuntimeError, 'changed/restarted'):
            life.primary_state(self.primary_peer, registry, self.primary,
                               reader=lambda _: None, pid_exists=lambda _: False)
        b.atomic_json(self.primary / 'processes/service.json', registry)
        with self.assertRaisesRegex(RuntimeError, 'identity changed'):
            life.primary_state(self.primary_peer, registry, self.primary,
                               reader=lambda _: ident('reused_pid'), pid_exists=lambda _: True)

    def test_cleanup_wrong_service_or_unverified_absence_never_passes(self):
        registry, cleanup = self.natural_completion_records()
        for update in ({'service_record': dict(registry, pid=8888)},
                       {'process_absent': False}, {'own_compute_absent': False}):
            with self.subTest(update=update):
                b.atomic_json(self.primary / 'processes/cleanup.json', dict(cleanup, **update))
                with self.assertRaisesRegex(RuntimeError, 'remained unverified'):
                    life.observe_primary(self.primary_peer, registry, self.primary, timeout=0.01,
                                         reader=lambda _: None, pid_exists=lambda _: False)

    def test_completion_journal_race_waits_then_passes(self):
        registry, cleanup = self.natural_completion_records()
        path = self.primary / 'processes/cleanup.json'
        path.unlink()
        calls = []
        def reader(pid):
            calls.append(pid)
            if len(calls) == 2:
                b.atomic_json(path, cleanup)
            return None
        status = life.observe_primary(self.primary_peer, registry, self.primary,
                                      timeout=1, reader=reader, pid_exists=lambda _: False)
        self.assertEqual(status, 'complete')
        self.assertGreaterEqual(len(calls), 2)

    def test_direct_service_start_requires_gate_before_gpu_query(self):
        (self.root / 'processes/pre_cuda_gate.json').unlink()
        with mock.patch.object(service, 'RUN', self.root), mock.patch.object(service, 'compute_processes') as query:
            with self.assertRaises(FileNotFoundError):
                service.start()
            query.assert_not_called()

    def test_subprocess_gate_blocks_before_sentinel_then_releases_without_torch(self):
        self._subprocess_gate(release=True)

    def test_subprocess_gate_timeout_never_reaches_sentinel(self):
        self._subprocess_gate(release=False)

    def _subprocess_gate(self, release):
        # Test-only reader injection avoids /proc on macOS; production always uses
        # real Linux UID/start ticks/raw command SHA. The child's actual PID is
        # still captured by the ready file and checked by the release protocol.
        self.gate['created_unix'] = time.time()
        self.gate['expires_unix'] = time.time() + (10 if release else 0.6)
        b.atomic_json(self.root / 'processes/pre_cuda_gate.json', self.gate)
        sentinel = self.root / 'after_barrier.json'
        code = """
import sys, os, json
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import startup_barrier as b
root=Path(sys.argv[2]); gate=b.read_json(root/'processes/pre_cuda_gate.json')
child_identity=json.loads(sys.argv[3])
def reader(pid):
    if pid==os.getpid(): return child_identity
    for k in ('primary','coordinator'):
        if pid==gate[k]['pid']: return gate[k]['identity']
    return None
assert 'torch' not in sys.modules
b.wait_for_release(root,reader=reader,poll_seconds=0.01)
b.atomic_json(root/'after_barrier.json',{'torch_imported':'torch' in sys.modules,'pid':os.getpid()})
"""
        proc = subprocess.Popen([sys.executable, '-c', code, str(STAGE / 'scripts'), str(self.root), json.dumps(ident('child'))],
                                env=dict(os.environ, CUDA_VISIBLE_DEVICES=b.GPU, PYTHONDONTWRITEBYTECODE='1'),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready_path, release_path = b.paths(self.root, self.gate['launch_id'])
            deadline = time.monotonic() + 5
            while not ready_path.exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(ready_path.exists())
            self.assertFalse(sentinel.exists())
            actual_ready = b.read_json(ready_path)
            self.assertEqual(actual_ready['pid'], proc.pid)
            if release:
                self.child = {'pid': proc.pid, 'identity': ident('child')}
                self.ready = actual_ready
                self.put_admissions()
                b.atomic_json(release_path, self.release())
            stdout, stderr = proc.communicate(timeout=5)
            if release:
                self.assertEqual(proc.returncode, 0, stderr)
                self.assertEqual(b.read_json(sentinel), {'torch_imported': False, 'pid': proc.pid})
            else:
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn('timed out', stderr)
                self.assertFalse(sentinel.exists())
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    def test_bootstrap_gate_precedes_torch_install(self):
        tree = ast.parse((STAGE / 'scripts/compatibility_bootstrap.py').read_text())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        barrier_line = next(n.lineno for n in ast.walk(main) if isinstance(n, ast.Call)
                            and isinstance(n.func, ast.Name) and n.func.id == 'wait_for_release')
        install_line = next(n.lineno for n in ast.walk(main) if isinstance(n, ast.Call)
                            and isinstance(n.func, ast.Name) and n.func.id == 'install')
        self.assertLess(barrier_line, install_line)
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module]
                self.assertFalse(any(name and name.split('.')[0] in ('torch', 'av', 'comfy', 'comfy_kitchen') for name in names))



if __name__ == '__main__':
    unittest.main(verbosity=2)
