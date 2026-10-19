import importlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
import launch_remote,service
class LaunchGenerationTests(unittest.TestCase):
 def setup_records(self,d):
  root=Path(d);(root/'processes').mkdir();owner={'pid':10,'identity':{'uid':1002,'start_ticks':'own','cmdline':['own']}};sup={'pid':20,'identity':{'uid':1002,'start_ticks':'sup','cmdline':['sup']},'service_pid':10,'service_identity':owner['identity'],'service_record':owner}
  self.put(root/'processes/service.json',owner);self.put(root/'processes/supervisor_20.json',sup);return root,owner,sup
 def put(self,p,v):p.write_text(json.dumps(v))
 def test_existing_live_service_rejected_start_does_not_clean_old(self):
  with tempfile.TemporaryDirectory() as d:
   r,o,s=self.setup_records(d);s.pop('service_record');s.pop('service_pid');s.pop('service_identity');self.put(r/'processes/supervisor_20.json',s)
   with patch.object(service,'stop') as stop:result=launch_remote.cleanup_created_owner(r,20,s['identity'])
   self.assertFalse(result['stopped']);stop.assert_not_called()
 def test_pid_reused_or_registry_new_generation_not_killed(self):
  with tempfile.TemporaryDirectory() as d:
   r,o,s=self.setup_records(d)
   for pid in (10,11):
    other={'pid':pid,'identity':{'uid':1002,'start_ticks':'new','cmdline':['other']}};self.put(r/'processes/service.json',other)
    with patch.object(service,'stop') as stop:result=launch_remote.cleanup_created_owner(r,20,s['identity'])
    self.assertFalse(result['stopped']);stop.assert_not_called()
 def test_no_child_record_or_reused_supervisor_not_killed(self):
  with tempfile.TemporaryDirectory() as d:
   r,o,s=self.setup_records(d)
   with patch.object(service,'stop') as stop:launch_remote.cleanup_created_owner(r,20,{'uid':1002,'start_ticks':'other','cmdline':['sup']})
   stop.assert_not_called();(r/'processes/supervisor_20.json').unlink()
   with patch.object(service,'stop') as stop:launch_remote.cleanup_created_owner(r,20,s['identity'])
   stop.assert_not_called()
 def test_current_child_failure_cleans_only_expected_owner(self):
  with tempfile.TemporaryDirectory() as d:
   r,o,s=self.setup_records(d)
   with patch.object(service,'stop',return_value={'stopped':True}) as stop:result=launch_remote.cleanup_created_owner(r,20,s['identity'])
   self.assertTrue(result['stopped']);stop.assert_called_once_with(expected_record=o)
 def test_fresh_process_runtime_import_has_no_launch_effect(self):
  code="import sys;sys.path.insert(0,sys.argv[1]);import launch_remote,supervise_service,start_controller,service,job,run_queue,preflight,prelaunch_gates;print('IMPORT_PASS')"
  p=subprocess.run([sys.executable,'-c',code,str(R/'scripts')],capture_output=True,text=True,timeout=10);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stdout.strip(),'IMPORT_PASS')
if __name__=='__main__':unittest.main()
