"""CPU mocks only: no real signals, queue requests, service stop or GPU calls."""
from pathlib import Path
import hashlib
import importlib.util
import io
import json
import signal
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).with_name('drain_current_for_task_review.py')


class DrainCurrentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='drain-cpu-mock-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('processes', 'logs', 'configs', 'audit'):
            (self.root/name).mkdir()
        self.owner = {'pid': 111, 'identity': {'start_ticks': 10, 'cmdline': 'mock-service'}}
        self.controller = {'pid': 222, 'identity': {'start_ticks': 20, 'cmdline': 'mock-controller'},
                           'service_pid': 111, 'service_identity': self.owner['identity']}
        self.queue = {'jobs': ['earlier', 'active', 'pending'], 'finalize': True}
        self.put('processes/service.json', self.owner)
        self.put('processes/controller.json', self.controller)
        self.put('configs/queue.json', self.queue)
        self.put('logs/controller_state.json', {'status':'running','current':'active','completed':['earlier']})
        self.put('logs/earlier_history.json', {'status':{'completed':True,'status_str':'success'}})
        self.put('logs/active_job.json', {'prompt_id':'prompt-current','status':'submitted'})
        self.put('logs/active_history.json', {'status':{'completed':True,'status_str':'success'}})
        self.queue_bytes = (self.root/'configs/queue.json').read_bytes()
        self.identity = self.controller['identity']
        self.paused = False
        self.terminated = False
        self.signal_calls = []
        self.write_fail_names = set()
        self.service = types.ModuleType('service')
        self.service.PORT = 9999
        self.service.assert_owned = Mock()
        self.service.current_identity = Mock(side_effect=lambda pid:self.identity if pid == 222 else self.owner['identity'])
        self.service.queue_at = Mock(side_effect=[{'queue_running':[[0,'prompt-current']], 'queue_pending':[]},
                                                 {'queue_running':[], 'queue_pending':[]}])
        self.service.stop = Mock(return_value={'stopped':True, 'pid':111})
        self.service.wait_absent = Mock(side_effect=lambda pid,timeout:self.identity is None)
        self.service.write_json = Mock(side_effect=self.write_json)
        self.job = types.ModuleType('job')
        self.job.status = Mock(return_value={'status':'success'})
        name = 'drain_test_subject_' + str(id(self))
        spec = importlib.util.spec_from_file_location(name, SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def put(self, relative, value):
        (self.root/relative).write_text(json.dumps(value))

    def write_json(self, path, value):
        if Path(path).name in self.write_fail_names:
            raise OSError('mock audit filesystem failure')
        Path(path).write_text(json.dumps(value))

    def kill(self, pid, sig):
        self.assertEqual(pid,222)
        self.signal_calls.append(sig)
        if sig == signal.SIGSTOP:self.paused=True
        if sig == signal.SIGTERM:self.terminated=True
        if sig == signal.SIGCONT:
            self.paused=False
            if self.terminated:self.identity=None

    def run_main(self):
        before = list(sys.path)
        try:
            with patch.dict(sys.modules,{'service':self.service,'job':self.job}), \
                 patch.object(sys,'argv',[str(SCRIPT),'--root',str(self.root)]), \
                 patch.object(self.module.os,'kill',side_effect=self.kill), \
                 patch.object(self.module.time,'sleep'), \
                 patch('sys.stdout',new_callable=io.StringIO):
                self.module.main()
        finally:
            sys.path[:] = before

    def expect_failure(self):
        with self.assertRaises(BaseException):self.run_main()

    def test_success_drains_only_current_and_preserves_scientific_queue(self):
        self.run_main()
        self.assertEqual(self.signal_calls,[signal.SIGSTOP,signal.SIGTERM,signal.SIGCONT])
        self.service.stop.assert_called_once_with(expected_record=self.owner)
        self.assertEqual((self.root/'configs/queue.json').read_bytes(),self.queue_bytes)
        state=json.loads((self.root/'logs/controller_state.json').read_text())
        self.assertEqual(state['status'],'task_scope_review_hold')
        self.assertEqual(state['completed'],['earlier','active'])
        self.assertFalse((self.root/'logs/pending_history.json').exists())

    def test_preaccepted_no_matching_job_resumes_controller(self):
        (self.root/'logs/active_job.json').unlink()
        self.expect_failure()
        self.assertEqual(self.signal_calls,[signal.SIGSTOP,signal.SIGCONT])
        self.assertFalse(self.paused)
        self.service.stop.assert_not_called()

    def test_preaccepted_pending_queue_resumes_controller(self):
        self.service.queue_at.side_effect=[{'queue_running':[[0,'prompt-current']], 'queue_pending':[[1,'next']]}]
        self.expect_failure()
        self.assertEqual(self.signal_calls,[signal.SIGSTOP,signal.SIGCONT])
        self.service.stop.assert_not_called()

    def test_preaccepted_ambiguous_job_resumes_controller(self):
        self.put('logs/duplicate_job.json',{'prompt_id':'prompt-current'})
        self.expect_failure()
        self.assertEqual(self.signal_calls,[signal.SIGSTOP,signal.SIGCONT])

    def test_owner_identity_failure_never_signals(self):
        self.service.assert_owned.side_effect=ValueError('mock changed owner')
        self.expect_failure()
        self.assertEqual(self.signal_calls,[])
        self.service.stop.assert_not_called()

    def test_controller_identity_failure_never_signals(self):
        self.identity={'start_ticks':999,'cmdline':'replacement'}
        self.expect_failure()
        self.assertEqual(self.signal_calls,[])

    def test_accepted_job_error_cleans_exact_owner_and_controller(self):
        self.job.status.return_value={'status':'error'}
        self.expect_failure()
        self.service.stop.assert_called_once_with(expected_record=self.owner)
        self.assertEqual(self.signal_calls,[signal.SIGSTOP,signal.SIGTERM,signal.SIGCONT])
        self.assertIsNone(self.identity)
        self.assertEqual((self.root/'configs/queue.json').read_bytes(),self.queue_bytes)

    def test_accepted_job_exception_cleans_exact_owner_and_controller(self):
        self.job.status.side_effect=OSError('mock status transport failed')
        self.expect_failure()
        self.service.stop.assert_called_once_with(expected_record=self.owner)
        self.assertIsNone(self.identity)

    def test_preaccepted_audit_failure_still_resumes(self):
        (self.root/'logs/active_job.json').unlink()
        self.write_fail_names.add('FAILURE.json')
        self.expect_failure()
        self.assertFalse(self.paused,'failure receipt I/O must not skip controller recovery')
        self.assertEqual(self.signal_calls,[signal.SIGSTOP,signal.SIGCONT])

    def test_accepted_service_cleanup_error_still_terminates_controller(self):
        self.job.status.return_value={'status':'error'}
        self.service.stop.side_effect=RuntimeError('mock service cleanup failed')
        self.expect_failure()
        self.assertEqual(self.signal_calls,[signal.SIGSTOP,signal.SIGTERM,signal.SIGCONT])
        self.assertIsNone(self.identity)

    def test_accepted_failure_receipt_error_still_cleans(self):
        self.job.status.return_value={'status':'error'}
        self.write_fail_names.add('FAILURE.json')
        self.expect_failure()
        self.service.stop.assert_called_once_with(expected_record=self.owner)
        self.assertIsNone(self.identity)

    def test_controller_service_generation_mismatch_never_signals(self):
        self.controller['service_identity']={'start_ticks':999,'cmdline':'other service generation'}
        self.put('processes/controller.json',self.controller)
        self.expect_failure()
        self.assertEqual(self.signal_calls,[])
        self.service.stop.assert_not_called()

    def test_success_requires_successful_history_status(self):
        self.put('logs/active_history.json',{'status':{'completed':True,'status_str':'error'}})
        self.expect_failure()
        self.assertFalse((self.root/'audit/task_scope_review_hold_20261018/COMPLETE.json').exists())

    def test_failed_earlier_history_is_not_counted_as_completed_success(self):
        self.put('logs/earlier_history.json',{'status':{'completed':True,'status_str':'error'}})
        self.run_main()
        state=json.loads((self.root/'logs/controller_state.json').read_text())
        self.assertEqual(state['completed'],['active'])
        self.assertEqual((self.root/'configs/queue.json').read_bytes(),self.queue_bytes)

    def test_running_then_success_and_dictionary_status(self):
        self.job.status.side_effect=[{'status':'running'},
                                     {'status':{'completed':True,'status_str':'success'}}]
        self.run_main()
        self.assertEqual(self.job.status.call_count,2)
        self.assertEqual(self.signal_calls,[signal.SIGSTOP,signal.SIGTERM,signal.SIGCONT])

    def test_nonempty_final_queue_triggers_accepted_cleanup(self):
        self.service.queue_at.side_effect=[{'queue_running':[[0,'prompt-current']], 'queue_pending':[]},
                                          {'queue_running':[], 'queue_pending':[[1,'unexpected']]}]
        self.expect_failure()
        self.service.stop.assert_called_once_with(expected_record=self.owner)
        self.assertIsNone(self.identity)
        self.assertFalse((self.root/'audit/task_scope_review_hold_20261018/COMPLETE.json').exists())

    def test_accepted_cleanup_does_not_signal_replacement_controller(self):
        def status(_):
            self.identity={'start_ticks':999,'cmdline':'replacement'}
            raise RuntimeError('original status error')
        self.job.status.side_effect=status
        self.expect_failure()
        self.service.stop.assert_called_once_with(expected_record=self.owner)
        self.assertEqual(self.signal_calls,[signal.SIGSTOP])

    def test_original_error_survives_cleanup_error(self):
        self.job.status.side_effect=ValueError('original status error')
        self.service.stop.side_effect=RuntimeError('secondary cleanup error')
        with self.assertRaisesRegex(ValueError,'original status error'):
            self.run_main()
        receipt=json.loads((self.root/'audit/task_scope_review_hold_20261018/FAILURE_CLEANUP.json').read_text())
        self.assertTrue(any('secondary cleanup error' in row for row in receipt['errors']))
        self.assertIsNone(self.identity)

    def test_identity_is_rechecked_after_initial_audit_io(self):
        def write_then_replace(path,value):
            self.write_json(path,value)
            if Path(path).name=='PRIOR.json':
                self.identity={'start_ticks':999,'cmdline':'replacement'}
        self.service.write_json.side_effect=write_then_replace
        self.expect_failure()
        self.assertEqual(self.signal_calls,[])
        self.service.stop.assert_not_called()


if __name__=='__main__':
    before=hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DrainCurrentTests))
    after=hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    receipt={'schema':'drain-current-cpu-mock-review-v1','script':str(SCRIPT),'script_sha256':before,
             'script_unchanged_during_tests':before==after,'tests':result.testsRun,
             'failures':[str(test) for test,_ in result.failures],'errors':[str(test) for test,_ in result.errors],
             'passed':result.wasSuccessful() and before==after,'real_process_signals':0,'real_queue_calls':0,'gpu_started':False}
    target=Path(__file__).with_name('DRAIN_MOCK_REVIEW.json')
    target.write_text(json.dumps(receipt,indent=2)+'\n')
    Path(__file__).with_name('DRAIN_MOCK_TESTS.log').write_text(stream.getvalue())
    print(json.dumps(receipt,indent=2))
    sys.exit(0 if receipt['passed'] else 1)
