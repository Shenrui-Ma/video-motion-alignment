import importlib.util,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('r135_cleanup_runner',ROOT/'audit/root_run_batch.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class AttemptCleanup(unittest.TestCase):
 def test_failed_receipt_still_stops_owned_service(self):
  owner={'pid':123};primary=ValueError('primary')
  with patch.object(r.service,'write_json',side_effect=OSError('disk full')),patch.object(r.service,'stop') as stop:
   self.assertEqual(r.failure_cleanup(Path('/audit'),primary,owner,'token'),owner)
   stop.assert_called_once_with(expected_record=owner)
 def test_cleanup_and_receipt_failures_preserve_primary_exception(self):
  primary=ValueError('primary')
  with patch.object(r.service,'write_json',side_effect=OSError('disk full')),patch.object(r.service,'stop',side_effect=RuntimeError('cleanup')):
   with self.assertRaises(ValueError) as observed:
    try:raise primary
    except BaseException as error:r.failure_cleanup(Path('/audit'),error,{'pid':123},'token');raise
  self.assertIs(observed.exception,primary)
 def test_owner_assignment_failure_recovers_exact_attempt(self):
  owner={'pid':123}
  with patch.object(r.service,'write_json'),patch.object(r,'recover_attempt_owner',return_value=owner) as recover,patch.object(r.service,'stop') as stop:
   self.assertEqual(r.failure_cleanup(Path('/audit'),ValueError('launch'),None,'unique'),owner)
  recover.assert_called_once_with('unique');stop.assert_called_once_with(expected_record=owner)
 def fixture(self,base,token='same'):
  root=Path(base);(root/'processes').mkdir()
  identity={'uid':os.getuid(),'start_ticks':'4','cmdline':'python3 '+str(root/'scripts/supervise_service.py')}
  (root/'processes/supervisor.json').write_text(json.dumps({'pid':12,'identity':identity,'root_attempt_token':token}))
  owner={'pid':13,'identity':{'uid':os.getuid(),'start_ticks':'5','cmdline':'service'},'root_attempt_token':token,'gpu_uuid':r.service.GPU,'port':r.service.PORT}
  (root/'processes/service.json').write_text(json.dumps(owner));return root,identity,owner
 def test_recovery_binds_attempt_before_touching_any_process(self):
  with tempfile.TemporaryDirectory() as d:
   root,identity,owner=self.fixture(d,'old')
   with patch.object(r,'ROOT',root),patch.object(r.os,'kill') as kill,patch.object(r.service,'current_identity') as lookup:
    self.assertIsNone(r.recover_attempt_owner('new'));kill.assert_not_called();lookup.assert_not_called()
 def test_recovery_stops_exact_supervisor_then_binds_child(self):
  with tempfile.TemporaryDirectory() as d:
   root,identity,owner=self.fixture(d)
   with patch.object(r,'ROOT',root),patch.object(r.os,'kill') as kill,patch.object(r.service,'wait_absent',return_value=True),patch.object(r.service,'current_identity',side_effect=[identity,owner['identity']]),patch.object(r.service,'assert_owned') as owned:
    self.assertEqual(r.recover_attempt_owner('same'),owner)
   kill.assert_called_once_with(12,r.signal.SIGTERM);owned.assert_called_once_with(owner)
 def test_replaced_supervisor_is_never_signalled(self):
  with tempfile.TemporaryDirectory() as d:
   root,identity,owner=self.fixture(d)
   with patch.object(r,'ROOT',root),patch.object(r.os,'kill') as kill,patch.object(r.service,'current_identity',return_value=dict(identity,start_ticks='replacement')):
    with self.assertRaisesRegex(ValueError,'generation differs'):r.recover_attempt_owner('same')
    kill.assert_not_called()

if __name__=='__main__':unittest.main()
