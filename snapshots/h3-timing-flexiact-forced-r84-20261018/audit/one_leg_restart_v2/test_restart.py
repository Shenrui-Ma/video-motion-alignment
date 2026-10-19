import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location('restart',HERE/'root_restart_one_leg.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RetryTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.r=Path(self.t.name)/'run';self.r.mkdir();self.old=Path(self.t.name)/'native';(self.old/'audit').mkdir(parents=True)
  for d in ['processes','logs','audit/x0/'+m.RUN_ID,'audit/tensor_blobs','audit/router','output','configs','audit/ROOT_JOB_APPROVALS']:(self.r/d).mkdir(parents=True)
  self.owner={'pid':123,'identity':{'uid':1,'start_ticks':'456','cmdline':'service'}};self.write('processes/service.json',self.owner)
  self.case={'baseline_root':str(self.old),'baseline_noise_pair_id':'old_pair','reference_cache_id':'r84_one_leg__movie_man_9_shared'}
  self.job={'name':m.RUN_ID,'status':'pending_or_running','service_pid':123,'service_identity':self.owner['identity'],'prompt_id':'p'}
  self.write('logs/'+m.RUN_ID+'_job.json',self.job);self.write('audit/x0/'+m.RUN_ID+'/manifest.json',{'captures':[{'step_zero_based':i} for i in range(4)],'status':'running'})
  self.write('deploy_manifest.json',{'files':{}})
  (self.old/'audit/old_pair_noise.pt').write_bytes(b'old-noise');(self.r/'audit/old_pair_noise.pt').write_bytes(b'old-noise')
  self.write('configs/HISTORICAL_BINDINGS.json',{m.SOURCE:{'files':{'audit/old_pair_noise.pt':{'sha256':m.sha(self.old/'audit/old_pair_noise.pt'),'bytes':9}}}})
  (self.r/'audit/tensor_blobs/own.pt').write_bytes(b'condition');self.write('audit/'+self.case['reference_cache_id']+'_conditioning.json',{'blob':'own.pt'})
  self.reg=patch.object(m,'registry',return_value=({m.RUN_ID:{'case':self.case}},[m.RUN_ID,'fitness']));self.reg.start();self.addCleanup(self.reg.stop)
 def write(self,p,v):
  f=self.r/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(v))
 def inspect(self,**kwargs):return m.inspect_retry(self.r,123,'456',lookup=lambda p:None,query=lambda:[],**kwargs)
 def test_incomplete_actual_attempt_is_retryable(self):self.assertEqual(self.inspect()['captured_indices'],[0,1,2,3])
 def test_success_job_rejected(self):
  self.job['status']='success';self.write('logs/'+m.RUN_ID+'_job.json',self.job)
  with self.assertRaises(ValueError):self.inspect()
 def test_success_history_rejected(self):
  self.write('logs/'+m.RUN_ID+'_history.json',{'prompt':[None,'p'],'status':{'completed':True,'status_str':'success'}})
  with self.assertRaises(ValueError):self.inspect()
 def test_complete_capture_rejected(self):
  self.write('audit/x0/'+m.RUN_ID+'/manifest.json',{'captures':[{'step_zero_based':i} for i in range(20)],'status':'running'})
  with self.assertRaises(ValueError):self.inspect()
 def test_full_video_rejected_even_if_job_record_stale(self):
  (self.r/'output'/(m.RUN_ID+'_00001.mp4')).write_bytes(b'video')
  with self.assertRaises(ValueError):self.inspect(probe=lambda p:158)
 def test_partial_output_is_recorded(self):
  (self.r/'output'/(m.RUN_ID+'_00001.mp4')).write_bytes(b'partial')
  self.assertEqual(self.inspect(probe=lambda p:12)['outputs'][0]['decoded_frame_count'],12)
 def test_live_or_recycled_pid_rejected(self):
  with self.assertRaises(ValueError):m.inspect_retry(self.r,123,'456',lookup=lambda p:{'other':'generation'},query=lambda:[])
 def test_lingering_cuda_rejected(self):
  with self.assertRaises(ValueError):m.inspect_retry(self.r,123,'456',lookup=lambda p:None,query=lambda:[{'pid':123}])
 def test_wrong_service_generation_rejected(self):
  with self.assertRaises(ValueError):m.inspect_retry(self.r,123,'457',lookup=lambda p:None,query=lambda:[])
 def test_other_case_job_rejected(self):
  self.write('logs/fitness_job.json',{})
  with self.assertRaises(ValueError):self.inspect()
 def test_archive_preserves_partial_and_reconstructs_original_noise(self):
  evidence=self.inspect();a=self.r/'audit/attempt';a.mkdir();native_sha=m.sha(self.old/'audit/old_pair_noise.pt')
  m.archive_attempt(self.r,a,evidence)
  self.assertTrue((a/'previous_attempt/audit/x0'/m.RUN_ID/'manifest.json').exists())
  self.assertTrue((a/'previous_attempt/audit/tensor_blobs/own.pt').exists())
  self.assertEqual(m.sha(self.old/'audit/old_pair_noise.pt'),native_sha)
  self.assertEqual(m.sha(self.r/'audit/old_pair_noise.pt'),native_sha)
  self.assertFalse((self.r/'logs'/(m.RUN_ID+'_job.json')).exists())
 def test_archive_plan_io_failure_preserves_original(self):
  evidence=self.inspect();a=self.r/'audit/attempt';a.mkdir()
  with patch.object(m.service,'write_json',side_effect=OSError('disk')):
   with self.assertRaises(OSError):m.archive_attempt(self.r,a,evidence)
  self.assertTrue((self.r/'logs'/(m.RUN_ID+'_job.json')).exists())
 def test_frozen_file_in_archive_plan_rejected(self):
  evidence=self.inspect();a=self.r/'audit/attempt';a.mkdir();self.write('deploy_manifest.json',{'files':{'audit/tensor_blobs/own.pt':{}}})
  with self.assertRaises(ValueError):m.archive_attempt(self.r,a,evidence)
 def test_timeout_and_unknown_poll_wait(self):
  a=self.r/'audit/poll';a.mkdir()
  for value in [TimeoutError('read'),ConnectionResetError('read'),m.urllib.error.URLError('read')]:
   with patch.object(m.service,'assert_owned'),patch.object(m.job,'status',side_effect=value):self.assertFalse(m.poll_completed(self.owner,a))
  with patch.object(m.service,'assert_owned'),patch.object(m.job,'status',return_value={'status':'unknown_missing'}):self.assertFalse(m.poll_completed(self.owner,a))
 def test_actual_history_error_and_identity_error_rejected(self):
  a=self.r/'audit/poll';a.mkdir()
  with patch.object(m.service,'assert_owned'),patch.object(m.job,'status',return_value={'status':{'status_str':'error'}}):
   with self.assertRaises(ValueError):m.poll_completed(self.owner,a)
  with patch.object(m.service,'assert_owned',side_effect=RuntimeError('identity')):
   with self.assertRaises(RuntimeError):m.poll_completed(self.owner,a)
 def test_failure_receipt_io_failure_still_cleanup(self):
  with patch.object(m.h,'best_effort_receipt',return_value=False),patch.object(m.service,'stop') as stop:m.h.failure_cleanup(self.r/'audit',RuntimeError('primary'),self.owner,'token')
  stop.assert_called_once_with(expected_record=self.owner)
 def test_attempt_token_checks_exact_identity_before_environment(self):
  with patch.object(m.service,'current_identity',return_value={'wrong':'identity'}):
   with self.assertRaises(ValueError):m.h.has_attempt_token(self.owner,'token')
 def test_frozen_63_files_unchanged(self):
  seal=m.read(m.ROOT/'deploy_manifest.json');self.assertEqual(len(seal['files']),63)
  for p,row in seal['files'].items():self.assertEqual(m.sha(m.ROOT/p),row['sha256'],p)
if __name__=='__main__':unittest.main(verbosity=2)
