"""CPU-only safety and queue-race tests; does not contact a server or GPU."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import job
import service


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for directory in ('configs', 'logs', 'processes'):
            (self.root / directory).mkdir()
        self.patches = [patch.object(service, 'RUN', self.root), patch.object(job, 'RUN', self.root)]
        for item in self.patches:
            item.start()
        self.owner = {'pid': 42, 'gpu_uuid': service.GPU, 'port': service.PORT,
                      'identity': {'uid': os.getuid(), 'start_ticks': '100',
                                   'cmdline': f'{service.CORE}/main.py --base-directory {self.root}'}}
        service.write_json(self.root / 'processes/service.json', self.owner)
        self.empty = {'queue_running': [], 'queue_pending': []}
        service.write_json(self.root / 'configs/admission.json',
                           {'permitted_compute_processes': [], 'existing_comfy_port': 8189})
        for item in (patch.object(service, 'compute_processes', return_value=[]),
                     patch.object(service, 'queue_at', return_value=self.empty)):
            item.start()
            self.patches.append(item)

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def call(self, function, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return function(*args)

    def record_job(self):
        value = {'name': 'sample', 'prompt_id': 'abc', 'status': 'queued', 'submitted_unix': 1,
                 'service_pid': 42, 'service_identity': self.owner['identity']}
        service.write_json(self.root / 'logs/sample_job.json', value)

    def test_stop_rejects_identity_mismatch_without_signal(self):
        with patch.object(service, 'current_identity', return_value={'uid': 999}), \
                patch.object(service.os, 'kill') as kill:
            with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
                service.stop()
            kill.assert_not_called()

    def test_existing_pid_blocks_new_start_even_if_reused(self):
        with patch.object(service, 'current_identity', return_value={'uid': 999}):
            with self.assertRaisesRegex(RuntimeError, 'Recorded PID still exists'):
                service.refuse_existing_service()

    def test_absent_recorded_pid_allows_preflight(self):
        with patch.object(service, 'current_identity', return_value=None):
            service.refuse_existing_service()

    def test_admission_rejects_unknown_compute(self):
        rows = [{'pid': 2, 'gpu_uuid': 'another_gpu'}]
        with self.assertRaisesRegex(RuntimeError, 'Unexpected host compute'):
            service.check_admission({'permitted_compute_processes': []}, rows, self.empty)

    def test_admission_rejects_selected_gpu_even_allowlisted(self):
        allowed = {'permitted_compute_processes': [{'pid': 2, 'identity': {'uid': 1}}]}
        with self.assertRaisesRegex(RuntimeError, 'Selected GPU'):
            service.check_admission(allowed, [{'pid': 2, 'gpu_uuid': service.GPU}], self.empty)

    def test_admission_rejects_running_or_pending_existing_queue(self):
        for key in ('queue_running', 'queue_pending'):
            queue = dict(self.empty, **{key: [[0, 'other']]})
            with self.assertRaisesRegex(RuntimeError, 'Existing Comfy'):
                service.check_admission({'permitted_compute_processes': []}, [], queue)

    def test_admission_checks_allowed_process_identity(self):
        expected = {'uid': 1, 'start_ticks': '5', 'cmdline_sha256': 'abc'}
        admission = {'permitted_compute_processes': [{'pid': 2, 'identity': expected}]}
        rows = [{'pid': 2, 'gpu_uuid': 'another_gpu'}]
        with patch.object(service, 'external_identity', return_value=expected):
            service.check_admission(admission, rows, self.empty)
        with patch.object(service, 'external_identity', return_value=dict(expected, start_ticks='6')):
            with self.assertRaises(RuntimeError):
                service.check_admission(admission, rows, self.empty)
        with patch.object(service, 'external_identity', return_value=None):
            service.check_admission(admission, rows, self.empty)

    def test_own_scope_ignores_foreign_other_gpu_without_reading_command(self):
        admission = {'scope': 'own_user_video_jobs', 'permitted_compute_processes': []}
        rows = [{'pid': 55, 'gpu_uuid': 'another_gpu'}]
        with patch.object(service, 'proc_uid', return_value=os.getuid() + 1), \
                patch.object(service, 'external_identity') as identity:
            service.check_admission(admission, rows, self.empty)
        identity.assert_not_called()

    def test_own_scope_still_rejects_foreign_selected_gpu(self):
        admission = {'scope': 'own_user_video_jobs', 'permitted_compute_processes': []}
        rows = [{'pid': 55, 'gpu_uuid': service.GPU}]
        with patch.object(service, 'proc_uid', return_value=os.getuid() + 1), \
                patch.object(service, 'external_identity') as identity:
            with self.assertRaisesRegex(RuntimeError, 'Selected GPU'):
                service.check_admission(admission, rows, self.empty)
        identity.assert_not_called()

    def test_own_scope_rejects_unknown_same_uid_compute(self):
        admission = {'scope': 'own_user_video_jobs', 'permitted_compute_processes': []}
        rows = [{'pid': 55, 'gpu_uuid': 'another_gpu'}]
        with patch.object(service, 'proc_uid', return_value=os.getuid()), \
                patch.object(service, 'external_identity', return_value={'uid': os.getuid()}):
            with self.assertRaisesRegex(RuntimeError, 'Unexpected host compute'):
                service.check_admission(admission, rows, self.empty)

    def test_own_scope_checks_allowlisted_same_uid_identity_and_queue(self):
        expected = {'uid': os.getuid(), 'start_ticks': '5', 'cmdline_sha256': 'abc'}
        admission = {'scope': 'own_user_video_jobs',
                     'permitted_compute_processes': [{'pid': 55, 'identity': expected}]}
        rows = [{'pid': 55, 'gpu_uuid': 'another_gpu'}]
        with patch.object(service, 'proc_uid', return_value=os.getuid()), \
                patch.object(service, 'external_identity', return_value=expected):
            service.check_admission(admission, rows, self.empty)
            with self.assertRaisesRegex(RuntimeError, 'Existing Comfy'):
                service.check_admission(admission, rows,
                                        {'queue_running': [], 'queue_pending': [[0, 'other']]})
        with patch.object(service, 'proc_uid', return_value=os.getuid()), \
                patch.object(service, 'external_identity', return_value=dict(expected, start_ticks='6')):
            with self.assertRaisesRegex(RuntimeError, 'Unexpected host compute'):
                service.check_admission(admission, rows, self.empty)

    def test_start_command_has_isolation_and_opt_in_cache_none(self):
        args = service.command()
        self.assertNotIn('--cache-none', args)
        self.assertNotIn('--highvram', args)
        self.assertIn('--enable-triton-backend', args)
        self.assertEqual(args[args.index('--base-directory') + 1], str(self.root))
        self.assertIn('--cache-none', service.command(True))

    def test_job_names_cannot_escape_paths(self):
        for name in ('../x', '', 'SomeJob', 'a-b', 'a/b', 'x\n'):
            with self.assertRaises(ValueError):
                job.validate_name(name)
        self.assertEqual(job.validate_name('sample_01'), 'sample_01')

    def test_duplicate_submit_never_calls_api(self):
        self.record_job()
        with patch.object(job, 'request') as request:
            with self.assertRaisesRegex(RuntimeError, 'already exists'):
                job.submit('sample')
            request.assert_not_called()

    def test_submit_records_owner_and_exact_graph_hash(self):
        data = b'{"1": {"class_type": "Test", "inputs": {}}}\n'
        (self.root / 'configs/sample.json').write_bytes(data)
        with patch.object(job, 'active_service', return_value=self.owner), \
                patch.object(job, 'request', side_effect=[self.empty, {'prompt_id': 'abc'}]):
            record = self.call(job.submit, 'sample')
        self.assertEqual(record['graph_sha256'], job.hashlib.sha256(data).hexdigest())
        self.assertEqual(record['service_identity'], self.owner['identity'])

    def test_uncertain_submission_cannot_be_retried(self):
        (self.root / 'configs/sample.json').write_text('{"1": {}}')
        with patch.object(job, 'active_service', return_value=self.owner), \
                patch.object(job, 'request', side_effect=[self.empty, TimeoutError('timeout')]):
            with self.assertRaises(TimeoutError):
                job.submit('sample')
        record = json.loads((self.root / 'logs/sample_job.json').read_text())
        self.assertEqual(record['status'], 'submission_uncertain')
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            job.submit('sample')

    def test_submit_rechecks_host_and_rejects_new_compute_before_post_or_record(self):
        (self.root / 'configs/sample.json').write_text('{"1": {}}')
        unexpected = [{'pid': 55, 'gpu_uuid': 'another_gpu'}]
        with patch.object(job, 'active_service', return_value=self.owner), \
                patch.object(job, 'request', return_value=self.empty) as request, \
                patch.object(service, 'compute_processes', return_value=unexpected):
            with self.assertRaisesRegex(RuntimeError, 'Unexpected host compute'):
                job.submit('sample')
        request.assert_called_once_with('/queue')
        self.assertFalse((self.root / 'logs/sample_job.json').exists())

    def test_submit_rechecks_external_queue_before_post_or_record(self):
        (self.root / 'configs/sample.json').write_text('{"1": {}}')
        occupied = {'queue_running': [[0, 'private_other_job']], 'queue_pending': []}
        with patch.object(job, 'active_service', return_value=self.owner), \
                patch.object(job, 'request', return_value=self.empty) as request, \
                patch.object(service, 'queue_at', return_value=occupied):
            with self.assertRaisesRegex(RuntimeError, 'Existing Comfy'):
                job.submit('sample')
        request.assert_called_once_with('/queue')
        self.assertFalse((self.root / 'logs/sample_job.json').exists())

    def test_submit_excludes_owned_compute_from_host_admission(self):
        (self.root / 'configs/sample.json').write_text('{"1": {}}')
        owned_compute = [{'pid': self.owner['pid'], 'gpu_uuid': service.GPU}]
        with patch.object(job, 'active_service', return_value=self.owner), \
                patch.object(job, 'request', side_effect=[self.empty, {'prompt_id': 'abc'}]), \
                patch.object(service, 'compute_processes', return_value=owned_compute), \
                patch.object(service, 'queue_at', return_value=self.empty) as queue_at:
            record = self.call(job.submit, 'sample')
        queue_at.assert_called_once_with(8189)
        self.assertGreater(record['host_admission_checked_unix'], 0)
        self.assertEqual(record['status'], 'queued')

    def test_history_queue_completion_race_is_saved(self):
        self.record_job()
        history = {'status': {'status_str': 'success', 'completed': True}, 'outputs': {'x': {}}}
        with patch.object(job, 'active_service', return_value=self.owner), \
                patch.object(job, 'request', side_effect=[{}, self.empty, {'abc': history}]) as request:
            result = self.call(job.status, 'sample')
        self.assertEqual(result['status']['status_str'], 'success')
        self.assertEqual(request.call_count, 3)
        self.assertEqual(json.loads((self.root / 'logs/sample_history.json').read_text()), history)

    def test_missing_job_reports_unknown_not_running(self):
        self.record_job()
        with patch.object(job, 'active_service', return_value=self.owner), \
                patch.object(job, 'request', side_effect=[{}, self.empty, {}]):
            result = self.call(job.status, 'sample')
        self.assertEqual(result['status'], 'unknown_missing')

    def test_changed_service_blocks_status_api(self):
        self.record_job()
        with patch.object(job, 'active_service', return_value=dict(self.owner, pid=43)), \
                patch.object(job, 'request') as request:
            with self.assertRaisesRegex(RuntimeError, 'another service instance'):
                job.status('sample')
            request.assert_not_called()

    def test_error_history_is_saved_and_available_after_stop(self):
        self.record_job()
        history = {'status': {'status_str': 'error', 'completed': False}, 'outputs': {}}
        with patch.object(job, 'active_service', return_value=self.owner), \
                patch.object(job, 'request', return_value={'abc': history}):
            self.call(job.status, 'sample')
        with patch.object(job, 'active_service') as active, patch.object(job, 'request') as request:
            result = self.call(job.status, 'sample')
        self.assertTrue(result['archived'])
        active.assert_not_called()
        request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
