import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
import urllib.error
from unittest.mock import Mock,patch

HERE=Path(__file__).resolve().parents[1]

def load(path,name):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class RequestBoundary(unittest.TestCase):
 def setUp(self):
  with patch.dict(sys.modules,{'service':types.SimpleNamespace(RUN=Path('/unused'),PORT=8536)}):self.job=load(HERE/'scripts/job.py','candidate_job')
 def test_GET_timeout_is_unknown(self):
  with patch.object(self.job.urllib.request,'urlopen',side_effect=TimeoutError('timed out')) as call:
   with self.assertRaises(self.job.StatusUnavailable):self.job.request('/history/p')
   self.assertEqual(call.call_count,1)
 def test_POST_timeout_is_not_automatically_retried_or_relabelled(self):
  with patch.object(self.job.urllib.request,'urlopen',side_effect=TimeoutError('timed out')) as call:
   with self.assertRaises(TimeoutError):self.job.request('/prompt',{'prompt':{}})
   self.assertEqual(call.call_count,1)
 def test_connection_failure_is_unknown_for_GET(self):
  with patch.object(self.job.urllib.request,'urlopen',side_effect=urllib.error.URLError(ConnectionRefusedError())):
   with self.assertRaises(self.job.StatusUnavailable):self.job.request('/queue')
 def test_503_is_unknown_but_403_is_configuration_error(self):
  for code in (503,403):
   error=urllib.error.HTTPError('http://localhost',code,'error',{},io.BytesIO(b'body'))
   with self.subTest(code=code),patch.object(self.job.urllib.request,'urlopen',side_effect=error):
    if code==503:
     with self.assertRaises(self.job.StatusUnavailable):self.job.request('/queue')
    else:
     with self.assertRaises(RuntimeError) as result:self.job.request('/queue')
     self.assertNotIsInstance(result.exception,self.job.StatusUnavailable)

class ControllerWait(unittest.TestCase):
 def exercise(self,statuses,original=False,job_timeout=100,max_service=1000,verify_error=None):
  directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);root=Path(directory.name)
  (root/'logs').mkdir();(root/'processes').mkdir()
  states=[];owner=dict(pid=999,identity={'start_ticks':'42'})
  clock=types.SimpleNamespace(now=0.0)
  def sleep(n):clock.now+=n
  time=types.SimpleNamespace(monotonic=lambda:clock.now,time=lambda:clock.now,sleep=sleep)
  service=types.SimpleNamespace(RUN=root,assert_owned=Mock(),residency_snapshot=Mock(return_value={}),stop=Mock())
  def write(path,value):
   if path.name=='controller_state.json':states.append(value)
  service.write_json=write
  class Unavailable(RuntimeError):pass
  iterator=iter(statuses)
  def status(name):
   val=next(iterator)
   if val=='timeout':raise Unavailable('HTTP timeout')
   if val=='identity':raise RuntimeError('Process identity mismatch')
   if val=='success':return {'status':{'status_str':'success','completed':True}}
   return {'status':val}
  job=types.SimpleNamespace(status=Mock(side_effect=status),submit=Mock(),StatusUnavailable=Unavailable)
  def read(path):
   if path.name=='service.json':return owner
   if path.name=='scientific_contract.json':return {'continuous':{'max_service_seconds':max_service,'idle_hold_seconds':50,'job_timeout_seconds':job_timeout}}
   if path.name=='queue.json':return {'finalize':True}
   if path.name.endswith('_history.json'):return {'status':{'completed':True,'status_str':'success'}}
   raise AssertionError(path)
  modules={'service':service,'job':job,'preflight':types.SimpleNamespace(check=Mock()),'r99_contract':types.SimpleNamespace(registry=lambda r:({'job_one':{'run':'job_one'}},['job_one']),read=read,sha=lambda p:'unused'),'execution_gate':types.SimpleNamespace(admitted_job=lambda *a:True)}
  with patch.dict(sys.modules,modules):
   module=load(HERE/('source_snapshot/http_original' if original else 'scripts')/'run_queue.py','controller_under_test')
   module.time=time;module.wait_controller_registration=lambda *a:None;module.record_resources=lambda *a:None
   module.verify_completed=Mock(side_effect=verify_error)
   try:module.run(999,'42');error=None
   except BaseException as exc:error=exc
  return states,service,job,error
 def test_timeout_unknown_and_missing_history_can_recover_to_success(self):
  states,service,job,error=self.exercise(['timeout','unknown_missing','running','success'])
  self.assertIsNone(error);self.assertEqual(job.submit.call_count,1);self.assertEqual(job.status.call_count,4)
  self.assertEqual([x['status'] for x in states],['observation_unknown','unknown_missing','running','success','final_close'])
  service.stop.assert_called_once()
 def test_failed_pair_gate_stops_before_completed_or_next_submit(self):
  states,service,job,error=self.exercise(['success'],verify_error=ValueError('prefix changed'))
  self.assertIsInstance(error,ValueError);self.assertEqual(job.submit.call_count,1)
  self.assertEqual(states[-1]['status'],'failed');self.assertEqual(states[-1]['completed'],[]);service.stop.assert_called_once()
 def test_old_controller_dies_on_same_first_timeout(self):
  states,service,job,error=self.exercise(['timeout','success'],original=True)
  self.assertIsInstance(error,RuntimeError);self.assertEqual(job.status.call_count,1);self.assertEqual(states[-1]['status'],'failed');service.stop.assert_called_once()
 def test_true_job_error_still_fails(self):
  states,service,job,error=self.exercise(['error'])
  self.assertIsInstance(error,RuntimeError);self.assertIn('error',str(error));service.stop.assert_called_once()
 def test_identity_failure_is_not_swallowed(self):
  states,service,job,error=self.exercise(['identity'])
  self.assertIsInstance(error,RuntimeError);self.assertIn('identity',str(error));service.stop.assert_called_once()
 def test_unknown_retains_original_job_deadline(self):
  states,service,job,error=self.exercise(['timeout']*5,job_timeout=30)
  self.assertIsInstance(error,TimeoutError);self.assertIn('One job',str(error));self.assertEqual(job.submit.call_count,1);service.stop.assert_called_once()
 def test_unknown_retains_total_service_deadline(self):
  states,service,job,error=self.exercise(['timeout']*5,job_timeout=100,max_service=30)
  self.assertIsInstance(error,TimeoutError);self.assertIn('maximum lifetime',str(error));service.stop.assert_called_once()

if __name__=='__main__':unittest.main()
