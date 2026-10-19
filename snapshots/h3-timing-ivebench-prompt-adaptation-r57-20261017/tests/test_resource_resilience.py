"""Resource races and optional NVIDIA statistics must not alter science or identity gates."""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import service,job,run_queue

class Clock:
 def __init__(self):self.value=0
 def now(self):return self.value
 def sleep(self,value):self.value+=value

class Resources(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  for name in ['logs','processes','configs']:(self.root/name).mkdir()
  self.owner={'pid':9,'identity':{'uid':os.getuid(),'start_ticks':'100','cmdline':'owned'},'cache_none':False}
  (self.root/'processes/service.json').write_text(json.dumps(self.owner))
  self.admission={'permitted_compute_processes':[],'scope':'own_user_video_jobs','existing_comfy_port':None}
  (self.root/'configs/admission.json').write_text(json.dumps(self.admission))
  self.q={'queue_running':[],'queue_pending':[]}
  import shutil
  (self.root/'configs/memory_evidence').mkdir()
  shutil.copyfile(ROOT/'configs/native_memory_profile.json',self.root/'configs/native_memory_profile.json')
  shutil.copyfile(ROOT/'configs/memory_evidence/r54_native_resources.jsonl',self.root/'configs/memory_evidence/r54_native_resources.jsonl')
  self.s=patch.object(service,'RUN',self.root);self.s.start();self.j=patch.object(job,'RUN',self.root);self.j.start()
 def tearDown(self):self.j.stop();self.s.stop();self.tmp.cleanup()
 def test_foreign_on_selected_gpu_is_allowed_at_identity_gate(self):
  with patch.object(service,'proc_uid',return_value=os.getuid()+1):service.check_admission(self.admission,[{'pid':3,'gpu_uuid':service.GPU}],self.q)
 def test_foreign_three_cards_do_not_expand_own_gpu_cap(self):
  rows=[{'pid':i,'gpu_uuid':str(i)} for i in [3,4,5]]
  with patch.object(service,'proc_uid',return_value=os.getuid()+1):service.check_admission(self.admission,rows,self.q)
 def test_disappearing_compute_pid_is_transient(self):
  with patch.object(service,'proc_uid',return_value=None):
   with self.assertRaises(service.ResourceUnavailable):service.check_admission(self.admission,[{'pid':3,'gpu_uuid':service.GPU}],self.q)
 def test_disappears_between_uid_and_identity(self):
  with patch.object(service,'proc_uid',return_value=os.getuid()),patch.object(service,'external_identity',return_value=None):
   with self.assertRaises(service.ResourceUnavailable):service.check_admission(self.admission,[{'pid':3,'gpu_uuid':service.GPU}],self.q)
 def test_unregistered_own_identity_is_hard(self):
  with patch.object(service,'proc_uid',return_value=os.getuid()),patch.object(service,'external_identity',return_value={'uid':os.getuid(),'start_ticks':'101','cmdline_sha256':'x'}):
   with self.assertRaisesRegex(RuntimeError,'Unexpected own'):service.check_admission(self.admission,[{'pid':3,'gpu_uuid':service.GPU}],self.q)
 def test_reused_registered_pid_is_hard(self):
  allowed={'pid':3,'identity':{'uid':os.getuid(),'start_ticks':'100','cmdline_sha256':'x'}};self.admission['permitted_compute_processes']=[allowed]
  with patch.object(service,'proc_uid',return_value=os.getuid()),patch.object(service,'external_identity',return_value=dict(allowed['identity'],start_ticks='101')):
   with self.assertRaisesRegex(RuntimeError,'Unexpected own'):service.check_admission(self.admission,[{'pid':3,'gpu_uuid':service.GPU}],self.q)
 def test_more_than_two_own_cards_waits(self):
  identity={'uid':os.getuid(),'start_ticks':'100','cmdline_sha256':'x'};self.admission['permitted_compute_processes']=[{'pid':i,'identity':identity} for i in [3,4]]
  with patch.object(service,'proc_uid',return_value=os.getuid()),patch.object(service,'external_identity',return_value=identity):
   with self.assertRaises(service.ResourceUnavailable):service.check_admission(self.admission,[{'pid':3,'gpu_uuid':'other1'},{'pid':4,'gpu_uuid':'other2'}],self.q)
 def test_existing_queue_hard_error(self):
  with self.assertRaisesRegex(RuntimeError,'queued/running'):service.check_admission(self.admission,[],{'queue_running':[1],'queue_pending':[]})
 def test_job_transient_query_then_success(self):
  clock=Clock()
  with patch.object(job,'active_service',return_value=self.owner),patch.object(job,'check_host_admission',side_effect=[service.ResourceUnavailable('gone',{}),42]),patch.object(job.time,'monotonic',clock.now),patch.object(job.time,'sleep',clock.sleep):
   self.assertEqual(job.wait_host_admission(self.owner,timeout=3),42)
 def test_job_resource_wait_is_bounded(self):
  clock=Clock()
  with patch.object(job,'active_service',return_value=self.owner),patch.object(job,'check_host_admission',side_effect=service.ResourceUnavailable('gone',{})),patch.object(job.time,'monotonic',clock.now),patch.object(job.time,'sleep',clock.sleep):
   with self.assertRaises(TimeoutError):job.wait_host_admission(self.owner,timeout=3)
  self.assertEqual(clock.value,3)
 def test_job_hard_error_not_retried(self):
  with patch.object(job,'active_service',return_value=self.owner),patch.object(job,'check_host_admission',side_effect=ValueError('bad scientific data')) as query:
   with self.assertRaisesRegex(ValueError,'scientific'):job.wait_host_admission(self.owner)
  self.assertEqual(query.call_count,1)
 def test_service_generation_recheck_after_admission(self):
  other=dict(self.owner,identity=dict(self.owner['identity'],start_ticks='101'))
  with patch.object(job,'active_service',side_effect=[self.owner,other]),patch.object(job,'check_host_admission',return_value=1):
   with self.assertRaisesRegex(RuntimeError,'stale service'):job.wait_host_admission(self.owner)
 def test_compute_query_timeout_typed(self):
  with patch.object(service,'compute_processes',side_effect=subprocess.TimeoutExpired('nvidia-smi',20)):
   with self.assertRaises(service.ResourceUnavailable):job.check_host_admission(self.owner)
 def test_memory_gate_accepts_busy_gpu_with_enough_free(self):
  clock=Clock();answer=SimpleNamespace(stdout=f'{service.GPU}, 100, 48401, 88, 50\n',stderr='')
  with patch.object(service,'compute_processes',return_value=[{'pid':3,'gpu_uuid':service.GPU}]),patch.object(service,'proc_uid',return_value=os.getuid()+1),patch.object(service.subprocess,'run',return_value=answer):
   record=service.gpu_readiness(self.admission,self.q,clock=clock.now,sleep=clock.sleep)
  self.assertEqual(record['required_free_mib'],48401)
 def test_memory_gate_low_free_bounded(self):
  clock=Clock();answer=SimpleNamespace(stdout=f'{service.GPU}, 1000, 48400, 20, 50\n',stderr='')
  with patch.object(service,'compute_processes',return_value=[]),patch.object(service.subprocess,'run',return_value=answer):
   with self.assertRaises(TimeoutError):service.gpu_readiness(self.admission,self.q,clock=clock.now,sleep=clock.sleep,timeout=3)
  self.assertEqual(clock.value,3)
 def test_nvidia_timeout_then_gpu_admission_success(self):
  clock=Clock();answer=SimpleNamespace(stdout=f'{service.GPU}, 0, 48494, 0, 50\n',stderr='')
  with patch.object(service,'compute_processes',return_value=[]),patch.object(service.subprocess,'run',side_effect=[subprocess.TimeoutExpired('nvidia-smi',20),answer]):
   result=service.gpu_readiness(self.admission,self.q,clock=clock.now,sleep=clock.sleep,timeout=3)
  self.assertEqual(result['status'],'admitted');self.assertEqual(clock.value,2)
 def test_late_job_query_success_is_not_accepted(self):
  clock=Clock()
  def query(owner):clock.value=4;return 1
  with patch.object(job,'active_service',return_value=self.owner),patch.object(job,'check_host_admission',side_effect=query),patch.object(job.time,'monotonic',clock.now):
   with self.assertRaises(TimeoutError):job.wait_host_admission(self.owner,timeout=3)
 def test_memory_evidence_tamper_is_hard(self):
  (self.root/'configs/memory_evidence/r54_native_resources.jsonl').write_text('{}\n')
  with self.assertRaisesRegex(ValueError,'evidence changed'):service.native_memory_profile()
 def test_wrong_uuid_hard(self):
  clock=Clock();answer=SimpleNamespace(stdout='GPU-WRONG, 0, 50000, 0, 50\n',stderr='')
  with patch.object(service,'compute_processes',return_value=[]),patch.object(service.subprocess,'run',return_value=answer):
   with self.assertRaisesRegex(RuntimeError,'UUID'):service.gpu_readiness(self.admission,self.q,clock=clock.now,sleep=clock.sleep)
 def test_resource_poll_failure_records_null(self):
  with patch.object(run_queue.subprocess,'run',side_effect=subprocess.CalledProcessError(1,'nvidia-smi')):run_queue.record_resources('case')
  row=json.loads((self.root/'logs/resources.jsonl').read_text());self.assertIsNone(row['sample']);self.assertFalse(row['sample_available'])
 def test_residency_query_failure_preserves_exact_service(self):
  with patch.object(service,'assert_owned') as owned,patch.object(service,'compute_processes',side_effect=subprocess.TimeoutExpired('nvidia-smi',20)):
   result=service.residency_snapshot('test')
  owned.assert_called_once_with(self.owner);self.assertFalse(result['compute_snapshot_available']);self.assertIsNone(result['own_compute'])
 def test_residency_identity_error_still_hard(self):
  with patch.object(service,'assert_owned',side_effect=RuntimeError('identity mismatch')):
   with self.assertRaisesRegex(RuntimeError,'identity'):service.residency_snapshot('test')
 def test_queue_success_survives_optional_statistics_error(self):
  (self.root/'configs/scientific_contract.json').write_text(json.dumps({'continuous':{'max_service_seconds':100,'idle_hold_seconds':50,'job_timeout_seconds':30}}))
  (self.root/'configs/queue.json').write_text(json.dumps({'jobs':['case'],'finalize':True}))
  (self.root/'logs/case_history.json').write_text(json.dumps({'status':{'completed':True}}))
  with patch.object(run_queue,'wait_controller_registration'),patch.object(run_queue.preflight,'check'),patch.object(service,'assert_owned'),patch.object(run_queue,'registry',return_value=({'case':{}},['case'])),patch.object(service,'residency_snapshot',return_value={'service':self.owner}),patch.object(job,'submit'),patch.object(job,'status',return_value={'status':'success'}),patch.object(run_queue.subprocess,'run',side_effect=subprocess.TimeoutExpired('nvidia-smi',20)),patch.object(service,'stop') as stop:
   run_queue.run(9,'100')
  row=json.loads((self.root/'logs/controller_state.json').read_text());self.assertEqual(row['status'],'final_close');self.assertEqual(row['completed'],['case']);stop.assert_called_once_with(expected_record=self.owner)
if __name__=='__main__':unittest.main()
