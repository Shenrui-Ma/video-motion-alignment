import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import execution_gate as gate
import job
import launch_remote
import lease_watchdog
import r79_contract
import service


class Submission(unittest.TestCase):
    def exercise(self, change_at):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('processes', 'logs', 'configs/graphs'):
                (root / folder).mkdir(parents=True)
            name = 'r79_short_0144_seed2026101701_forced'
            graph_path = root / 'configs/graphs' / (name + '.json')
            graph_path.write_text('{"node": {"inputs": {}}}')
            (root / 'configs/queue.json').write_text('[]')
            original = dict(pid=1, identity=dict(uid=1004, start_ticks='10'))
            replacement = dict(pid=2, identity=dict(uid=1004, start_ticks='20'))
            current = [original]
            admitted_calls = []

            def admitted(*args):
                admitted_calls.append(current[0])
                if change_at == 'before_post' and len(admitted_calls) == 3:
                    raise ValueError('paired Native evidence changed')
                if current[0] != original:
                    raise ValueError('paired Native service generation changed')
                return True

            def prepare(*args):
                if change_at == 'before_lock':
                    current[0] = replacement

            def wait(*args):
                if change_at == 'during_wait':
                    current[0] = replacement
                return 100

            request = Mock(return_value={'queue_running': [], 'queue_pending': [], 'prompt_id': 'pid'})
            with patch.object(job, 'RUN', root), patch.object(job, 'active_service', side_effect=lambda: current[0]), patch.object(job, 'wait_host_admission', side_effect=wait), patch.object(job, 'request', request), patch.object(gate, 'admitted_job', side_effect=admitted), patch.object(r79_contract, 'validate_job', return_value={'graph_sha256': gate.sha(graph_path)}), patch.object(r79_contract, 'prepare_loader_inputs', side_effect=prepare), contextlib.redirect_stdout(io.StringIO()):
                if change_at:
                    with self.assertRaisesRegex((ValueError, RuntimeError), 'generation|evidence'):
                        job.submit(name)
                    self.assertFalse(any(call.args[0] == '/prompt' for call in request.call_args_list))
                else:
                    result = job.submit(name)
                    self.assertEqual(result['service_pid'], 1)
                    self.assertEqual(result['status'], 'queued')
                    self.assertGreaterEqual(len(admitted_calls), 3)

    def test_replacement_after_outer_admission_rejected(self):
        self.exercise('before_lock')

    def test_replacement_during_admission_wait_rejected(self):
        self.exercise('during_wait')

    def test_unchanged_owner_rechecks_approval_and_posts(self):
        self.exercise(None)

    def test_native_evidence_changed_before_post_rejected(self):
        self.exercise('before_post')


class Watchdog(unittest.TestCase):
    def test_reason_write_failure_still_stops_exact_owner(self):
        owner = dict(pid=10, identity={'start_ticks': '20'})
        limits = dict(max_service_seconds=1, job_timeout_seconds=1, idle_hold_seconds=1)
        with patch.object(lease_watchdog, 'read', side_effect=[owner, {'continuous': limits}, owner]), patch.object(service, 'current_identity', return_value=owner['identity']), patch.object(service, 'queue_at', return_value={'queue_running': [], 'queue_pending': []}), patch.object(lease_watchdog.time, 'monotonic', side_effect=[0, 2]), patch.object(service, 'write_json', side_effect=OSError('disk full')), patch.object(service, 'assert_owned') as assert_owned, patch.object(service, 'stop') as stop:
            with self.assertRaisesRegex(OSError, 'disk full'):
                lease_watchdog.main()
            assert_owned.assert_called_once_with(owner)
            stop.assert_called_once_with(expected_record=owner)


class Launcher(unittest.TestCase):
    def test_cleanup_receipt_failure_preserves_primary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'configs').mkdir()
            (root / 'configs/parent_core_hashes.json').write_text('{}')
            for name in ('H3EventAudit', 'H3PairAudit', 'H3TemporalRouter', 'H3X0Readout'):
                p = root / 'extensions' / name
                p.mkdir(parents=True)
                (p / '__init__.py').write_text('')
            child = Mock(pid=123)
            primary = RuntimeError('original launch failure')

            def write(path, value):
                if 'launch_cleanup_error' in str(path):
                    raise OSError('receipt disk full')

            with patch.object(sys, 'argv', ['launch_remote.py', '--service-only']), patch.object(service, 'RUN', root), patch.object(service, 'RUNTIME', {'kj_nodes': str(root)}), patch.object(service, 'write_json', side_effect=write), patch.object(service, 'bind_child', return_value={'uid': 1}), patch.object(launch_remote.preflight, 'check'), patch.object(r79_contract, 'registry', return_value=({}, [])), patch.object(launch_remote.subprocess, 'Popen', return_value=child), patch.object(launch_remote, 'wait_service_gate', side_effect=primary), patch.object(launch_remote, 'cleanup_launch', side_effect=RuntimeError('cleanup failure')), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError) as raised:
                    launch_remote.main()
                self.assertIs(raised.exception, primary)


if __name__ == '__main__':
    unittest.main()
