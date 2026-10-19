import importlib.util,json,os,subprocess,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/os.environ.get('CANDIDATE_SOURCE','overlay')/'scripts'
class ResourceUnavailable(ValueError):
 def __init__(self,message,snapshot):super().__init__(message);self.snapshot=snapshot
class Clock:
 def __init__(self):self.now=0
 def monotonic(self):return self.now
 def sleep(self,seconds):self.now+=seconds
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  for folder in ('scripts','configs','logs','processes'):(self.root/folder).mkdir()
  runtime={'core':str(self.root/'core'),'python':'python3','dependencies':'deps','models':'models','gpu_uuid':'main','decoder_uuid':'decoder','port':8516}
  (self.root/'configs/runtime.json').write_text(json.dumps(runtime))
  self.owner={'pid':123,'identity':{'uid':os.getuid(),'start_ticks':'456','cmdline':'owned'},'cache_none':False}
  (self.root/'processes/service.json').write_text(json.dumps(self.owner))
  (self.root/'configs/admission.json').write_text(json.dumps({'existing_comfy_port':None,'permitted_compute_processes':[]}))
  self.transport=types.SimpleNamespace(ResourceUnavailable=ResourceUnavailable,DECODER_UUID='decoder',admission_document=Mock())
  self.modules=patch.dict(sys.modules,{'observer_import':types.SimpleNamespace(t=self.transport),'preflight':types.SimpleNamespace(check=Mock()),'r55_contract':types.SimpleNamespace(registry=Mock(),read=Mock(),sha=Mock())});self.modules.start()
  for name in ('service','job','run_queue'):
   p=self.root/'scripts'/(name+'.py');p.write_bytes((SOURCES/(name+'.py')).read_bytes())
   spec=importlib.util.spec_from_file_location(name,p);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);setattr(self,name,module)
 def tearDown(self):
  for name in ('service','job','run_queue'):sys.modules.pop(name,None)
  self.modules.stop();self.tmp.cleanup()
 def wait(self,check,timeout=5,owners=None):
  clock=Clock()
  with patch.object(self.job,'active_service',side_effect=owners or [self.owner]*20),patch.object(self.job,'check_host_admission',side_effect=check),patch.object(self.job.time,'monotonic',clock.monotonic),patch.object(self.job.time,'sleep',clock.sleep):
   return self.job.wait_host_admission(self.owner,timeout=timeout)
 def test_exited_pid_typed_resource_then_success(self):
  self.assertEqual(self.wait([ResourceUnavailable('ownership unavailable',{'pid':9}),123.5]),123.5)
  rows=[json.loads(x) for x in (self.root/'logs/submission_admission_wait.jsonl').read_text().splitlines()];self.assertEqual(len(rows),1)
 def test_resource_wait_has_finite_deadline(self):
  with self.assertRaises(TimeoutError):self.wait(ResourceUnavailable('resource unavailable',{}))
 def test_admission_does_not_succeed_after_deadline(self):
  clock=Clock()
  def check(owner):clock.now=7;return 1
  with patch.object(self.job,'active_service',return_value=self.owner),patch.object(self.job,'check_host_admission',side_effect=check),patch.object(self.job.time,'monotonic',clock.monotonic),patch.object(self.job.time,'sleep',clock.sleep):
   with self.assertRaises(TimeoutError):self.job.wait_host_admission(self.owner,timeout=5)
 def test_invalid_wait_budget_rejected(self):
  for duration in (0,-1,601,float('inf'),float('nan')):
   with self.subTest(duration=duration),self.assertRaises(ValueError):self.wait([1],timeout=duration)
 def test_changed_service_generation_during_wait_is_hard(self):
  changed=dict(self.owner,identity={'start_ticks':'different'})
  with self.assertRaisesRegex(RuntimeError,'stale service generation'):self.wait([ResourceUnavailable('transient',{})],owners=[self.owner,changed])
 def test_identity_graph_and_legacy_text_errors_are_hard(self):
  for error in (RuntimeError('Unexpected own compute identity 9'),ValueError('graph changed'),RuntimeError('Unexpected host compute PID 9')):
   with self.subTest(error=str(error)),self.assertRaises(type(error)):self.wait(error)
 def test_nvidia_query_timeout_becomes_typed_resource_error(self):
  with patch.object(self.service,'compute_processes',side_effect=subprocess.TimeoutExpired(['nvidia-smi'],10)):
   with self.assertRaises(ResourceUnavailable):self.job.check_host_admission(self.owner)
 def test_nvidia_query_nonzero_becomes_typed_resource_error(self):
  with patch.object(self.service,'compute_processes',side_effect=subprocess.CalledProcessError(1,['nvidia-smi'])):
   with self.assertRaises(ResourceUnavailable):self.job.check_host_admission(self.owner)
 def test_query_parse_and_missing_binary_are_hard(self):
  for error in (ValueError('malformed process PID'),FileNotFoundError('nvidia-smi')):
   with patch.object(self.service,'compute_processes',side_effect=error),self.assertRaises(type(error)):self.job.check_host_admission(self.owner)
 def test_dead_snapshot_pid_and_two_gpu_limit_remain_strict(self):
  with patch.object(self.service,'proc_uid',return_value=None):
   with self.assertRaises(ResourceUnavailable):self.service.check_admission({'permitted_compute_processes':[]},[{'pid':9,'gpu_uuid':'main'}],{'queue_running':[],'queue_pending':[]})
  identity={'uid':os.getuid(),'start_ticks':'1','cmdline_sha256':'x'}
  with patch.object(self.service,'proc_uid',return_value=os.getuid()),patch.object(self.service,'external_identity',return_value=identity):
   with self.assertRaises(ResourceUnavailable):self.service.check_admission({'permitted_compute_processes':[{'pid':9,'identity':identity}]},[{'pid':9,'gpu_uuid':'third'}],{'queue_running':[],'queue_pending':[]})
 def test_own_pid_exits_between_uid_and_identity_read(self):
  with patch.object(self.service,'proc_uid',return_value=os.getuid()),patch.object(self.service,'external_identity',return_value=None):
   with self.assertRaises(ResourceUnavailable):self.service.check_admission({'permitted_compute_processes':[]},[{'pid':9,'gpu_uuid':'decoder'}],{'queue_running':[],'queue_pending':[]})
 def test_reused_or_unregistered_own_identity_is_hard(self):
  actual={'uid':os.getuid(),'start_ticks':'new','cmdline_sha256':'new'}
  for permitted in ([],[{'pid':9,'identity':dict(actual,start_ticks='old')}]):
   with patch.object(self.service,'proc_uid',return_value=os.getuid()),patch.object(self.service,'external_identity',return_value=actual),self.assertRaisesRegex(RuntimeError,'Unexpected own compute identity'):
    self.service.check_admission({'permitted_compute_processes':permitted},[{'pid':9,'gpu_uuid':'decoder'}],{'queue_running':[],'queue_pending':[]})
 def test_service_generation_changed_inside_successful_query_is_hard(self):
  changed=dict(self.owner,identity={'start_ticks':'different'})
  with self.assertRaisesRegex(RuntimeError,'stale service generation'):self.wait([123.5],owners=[self.owner,changed])
 def test_noncritical_residency_query_can_be_unavailable(self):
  with patch.object(self.service,'assert_owned'),patch.object(self.service,'compute_processes',side_effect=subprocess.TimeoutExpired('nvidia-smi',10)):
   r=self.service.residency_snapshot('during_test')
  self.assertFalse(r['compute_snapshot_available']);self.assertIsNone(r['own_compute'])
 def test_residency_owner_mismatch_still_hard(self):
  with patch.object(self.service,'assert_owned',side_effect=RuntimeError('Process identity mismatch')),self.assertRaisesRegex(RuntimeError,'identity mismatch'):self.service.residency_snapshot('test')
 def test_residency_malformed_data_still_hard(self):
  with patch.object(self.service,'assert_owned'),patch.object(self.service,'compute_processes',side_effect=ValueError('bad process data')),self.assertRaises(ValueError):self.service.residency_snapshot('test')
 def run_controller(self,statuses,stats,history=None):
  r=self.run_queue;clock=Clock();stopped=Mock();submitted=Mock()
  def read(p):
   if p.name=='service.json':return self.owner
   if p.name=='scientific_contract.json':return {'continuous':{'max_service_seconds':60,'idle_hold_seconds':10,'job_timeout_seconds':50}}
   if p.name=='queue.json':return {'finalize':True}
   if p.name.endswith('_history.json'):
    if isinstance(history,Exception):raise history
    return history or {'status':{'completed':True}}
   raise AssertionError(p)
  self.controller_stop=stopped;self.controller_submit=submitted
  with patch.object(r,'read',side_effect=read),patch.object(r,'registry',return_value=({'case':{'frozen':1}},['case'])),patch.object(self.service,'assert_owned'),patch.object(self.service,'residency_snapshot',return_value={}),patch.object(self.service,'stop',stopped),patch.object(self.job,'submit',submitted),patch.object(self.job,'status',side_effect=[{'status':v} for v in statuses]),patch.object(r.subprocess,'run',side_effect=stats),patch.object(r.time,'monotonic',clock.monotonic),patch.object(r.time,'sleep',clock.sleep):r.run(123,'456')
 def test_transient_stats_do_not_abort_or_resubmit_running_job(self):
  self.run_controller(['pending_or_running','success'],[subprocess.TimeoutExpired('nvidia-smi',20),subprocess.CompletedProcess([],0,'main, 123, 5, 40\n','')])
  self.controller_submit.assert_called_once();self.controller_stop.assert_called_once_with(expected_record=self.owner)
  rows=[json.loads(x) for x in (self.root/'logs/resources.jsonl').read_text().splitlines()];self.assertIsNone(rows[0]['sample']);self.assertFalse(rows[0]['sample_available']);self.assertTrue(rows[1]['sample_available'])
 def test_nonzero_telemetry_does_not_mask_real_job_error(self):
  with self.assertRaisesRegex(RuntimeError,'case: error'):self.run_controller(['error'],[subprocess.CalledProcessError(1,'nvidia-smi')])
  self.controller_stop.assert_called_once_with(expected_record=self.owner)
 def test_history_missing_and_incomplete_are_still_hard(self):
  for history in (FileNotFoundError('missing history'),{'status':{'completed':False}}):
   expected=FileNotFoundError if isinstance(history,Exception) else ValueError
   with self.subTest(history=history),self.assertRaises(expected):self.run_controller(['success'],[subprocess.CompletedProcess([],0,'main, 123, 5, 40\n','')],history)
   self.controller_stop.assert_called_once_with(expected_record=self.owner)
 def test_unknown_missing_stays_hard(self):
  with self.assertRaisesRegex(RuntimeError,'unknown_missing'):self.run_controller(['unknown_missing'],[subprocess.CompletedProcess([],0,'main, 123, 5, 40\n','')])
 def test_missing_telemetry_binary_stays_hard(self):
  with self.assertRaises(FileNotFoundError):self.run_controller(['pending_or_running'],[FileNotFoundError('nvidia-smi')])
if __name__=='__main__':unittest.main()
