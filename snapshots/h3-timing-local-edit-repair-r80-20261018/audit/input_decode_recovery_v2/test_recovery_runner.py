import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

FILE=Path(__file__).with_name('root_resume_0352.py')
spec=importlib.util.spec_from_file_location('recovery_runner',FILE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.audit=self.root/'audit';self.audit.mkdir()
        (self.root/'processes').mkdir();(self.root/'logs').mkdir()
        self.owner={'pid':123,'identity':{'uid':1,'start_ticks':'2','cmdline':'service'}}
        (self.root/'processes/service.json').write_text(json.dumps(self.owner))
        (self.root/'processes/watchdog.json').write_text(json.dumps({'pid':124,'identity':self.owner['identity']}))
        (self.root/'processes/service.lock').write_text('')
        (self.root/'logs/controller_state.json').write_text('{"status":"failed"}')
    def test_archive_dead_generation_preserves_files_and_logs(self):
        rows=m.archive_old_processes(self.root,self.audit,lookup=lambda p:None,query=lambda:[])
        self.assertEqual({r['pid'] for r in rows},{123,124})
        self.assertTrue((self.audit/'old_processes/service.json').exists())
        self.assertTrue((self.audit/'old_controller_state.json').exists())
        self.assertEqual(list((self.root/'processes').iterdir()),[])
    def test_live_old_pid_rejected_without_mutation(self):
        with self.assertRaisesRegex(ValueError,'still live'):
            m.archive_old_processes(self.root,self.audit,lookup=lambda p:self.owner['identity'] if p==123 else None,query=lambda:[])
        self.assertTrue((self.root/'processes/service.json').exists())
        self.assertFalse((self.audit/'old_processes').exists())
    def test_recycled_pid_rejected_without_signal(self):
        with patch.object(m.os,'kill') as kill:
            with self.assertRaises(ValueError):
                m.archive_old_processes(self.root,self.audit,lookup=lambda p:{'different':'generation'},query=lambda:[])
            kill.assert_not_called()
    def test_cuda_lingering_old_pid_rejected(self):
        with self.assertRaisesRegex(ValueError,'CUDA inventory'):
            m.archive_old_processes(self.root,self.audit,lookup=lambda p:None,query=lambda:[{'pid':123}])
        self.assertTrue((self.root/'processes/service.json').exists())
    def test_foreign_cuda_preserved_and_allowed_for_later_admission(self):
        with patch.object(m.os,'kill') as kill:
            m.archive_old_processes(self.root,self.audit,lookup=lambda p:None,query=lambda:[{'pid':999}])
            kill.assert_not_called()
    def test_archive_receipt_failure_does_not_move_records(self):
        with patch.object(m.service,'write_json',side_effect=OSError('disk')):
            with self.assertRaises(OSError):m.archive_old_processes(self.root,self.audit,lookup=lambda p:None,query=lambda:[])
        self.assertTrue((self.root/'processes/service.json').exists())
    def test_controller_is_current_wrapper_exact_owner_and_single_scope(self):
        with patch.object(m.service,'identity',return_value={'uid':1,'start_ticks':'4','cmdline':'recovery'}):
            value=m.register_recovery_controller(self.root,self.owner,'token')
        self.assertEqual(value['pid'],m.os.getpid())
        self.assertEqual(value['allowed_runs'],[m.RUN_ID])
        self.assertEqual(value['service_identity'],self.owner['identity'])
    def test_status_success_requires_actual_completed(self):
        self.assertTrue(m.successful_status({'status':{'status_str':'success','completed':True}}))
        self.assertFalse(m.successful_status({'status':{'status_str':'success','completed':False}}))
        self.assertFalse(m.successful_status({'status':'pending_or_running'}))
    def test_status_failure_or_unknown_rejected(self):
        for status in ['submission_uncertain','error',{'status_str':'error','completed':False}]:
            with self.assertRaises(ValueError):m.successful_status({'status':status})
    def test_failure_receipt_disk_error_still_calls_exact_cleanup(self):
        with patch.object(m.helpers,'best_effort_receipt',return_value=False), patch.object(m.service,'stop') as stop:
            m.helpers.failure_cleanup(self.audit,RuntimeError('primary'),self.owner,'t')
        stop.assert_called_once_with(expected_record=self.owner)
    def test_partial_launch_recovers_only_this_attempt_owner(self):
        with patch.object(m.helpers,'best_effort_receipt'), patch.object(m.helpers,'recover_attempt_owner',return_value=self.owner) as recover, patch.object(m.service,'stop') as stop:
            m.helpers.failure_cleanup(self.audit,RuntimeError('primary'),None,'exact_token')
        recover.assert_called_once_with('exact_token');stop.assert_called_once_with(expected_record=self.owner)
    def test_missing_history_is_unknown_and_can_complete_on_later_poll(self):
        with patch.object(m.service,'assert_owned'), patch.object(m.job,'status',side_effect=[{'status':'unknown_missing'},{'status':{'status_str':'success','completed':True}}]):
            self.assertFalse(m.poll_completed(self.owner,self.audit))
            self.assertEqual(json.loads((self.audit/'PROGRESS.json').read_text())['observation'],'UNKNOWN')
            self.assertTrue(m.poll_completed(self.owner,self.audit))
    def test_read_transport_failure_waits_without_resetting_deadline(self):
        for error in [TimeoutError('read'),ConnectionResetError('reset'),m.urllib.error.URLError('temporary')]:
            with patch.object(m.service,'assert_owned'), patch.object(m.job,'status',side_effect=error):
                self.assertFalse(m.poll_completed(self.owner,self.audit))
                record=json.loads((self.audit/'PROGRESS.json').read_text())
                self.assertEqual(record['observation'],'UNKNOWN');self.assertFalse(record['deadline_reset'])
    def test_actual_execution_error_remains_failure(self):
        with patch.object(m.service,'assert_owned'), patch.object(m.job,'status',return_value={'status':{'status_str':'error','completed':False}}):
            with self.assertRaises(ValueError):m.poll_completed(self.owner,self.audit)
    def test_identity_change_is_not_swallowed(self):
        with patch.object(m.service,'assert_owned',side_effect=RuntimeError('generation')), patch.object(m.job,'status') as status:
            with self.assertRaisesRegex(RuntimeError,'generation'):m.poll_completed(self.owner,self.audit)
            status.assert_not_called()
    def test_http_server_error_is_not_transport_retry(self):
        error=m.urllib.error.HTTPError('http://local',500,'server',{},None)
        self.assertFalse(m.transport_failure(error))
        with patch.object(m.service,'assert_owned'),patch.object(m.job,'status',side_effect=error):
            with self.assertRaises(m.urllib.error.HTTPError):m.poll_completed(self.owner,self.audit)
    def test_producer_seal_exact(self):
        seal=m.read(m.ROOT/'deploy_manifest.json')
        self.assertEqual(len(seal['files']),61)
        for p,row in seal['files'].items():self.assertEqual(m.sha(m.ROOT/p),row['sha256'],p)

if __name__=='__main__':unittest.main(verbosity=2)
