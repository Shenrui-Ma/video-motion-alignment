import os,sys,unittest
from pathlib import Path
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import service,resource_gate,job
class Clock:
 def __init__(self):self.value=0
 def now(self):return self.value
 def sleep(self,dt):self.value+=dt
class AdmissionResample(unittest.TestCase):
 def setUp(self):
  self.admission={'scope':'own_user_video_jobs','ready_for_launch':True,'permitted_compute_processes':[]};self.queue={'queue_running':[],'queue_pending':[]};self.clock=Clock()
 def test_exited_pid_is_resampled_then_absent(self):
  query=Mock(side_effect=[[{'gpu_uuid':'g','pid':123,'used_memory_mib':'1'}],[]])
  with patch.object(resource_gate,'admission_document'),patch.object(service,'proc_uid',return_value=None) as uid:
   r=service.wait_admission_snapshot(self.admission,self.queue,query=query,clock=self.clock.now,sleep=self.clock.sleep)
  self.assertEqual(query.call_count,2);self.assertEqual(uid.call_count,1);self.assertEqual(r['processes'],[]);self.assertEqual(r['attempts'],2)
 def test_repeated_unknown_uid_times_out_closed(self):
  query=Mock(return_value=[{'gpu_uuid':'g','pid':123,'used_memory_mib':'1'}])
  with patch.object(resource_gate,'admission_document'),patch.object(service,'proc_uid',return_value=None):
   with self.assertRaises(TimeoutError) as error:service.wait_admission_snapshot(self.admission,self.queue,query=query,timeout=.3,clock=self.clock.now,sleep=self.clock.sleep)
  self.assertIsInstance(error.exception.__cause__,resource_gate.ResourceUnavailable);self.assertGreater(query.call_count,1)
 def test_new_own_process_after_race_is_rejected(self):
  query=Mock(return_value=[{'gpu_uuid':'g','pid':123,'used_memory_mib':'1'}])
  with patch.object(resource_gate,'admission_document'),patch.object(service,'proc_uid',side_effect=[None,os.getuid()]),patch.object(service,'external_identity',return_value={'uid':os.getuid(),'start_ticks':'new','cmdline_sha256':'x'}):
   with self.assertRaisesRegex(RuntimeError,'Unexpected own compute'):service.wait_admission_snapshot(self.admission,self.queue,query=query,clock=self.clock.now,sleep=self.clock.sleep)
  self.assertEqual(query.call_count,2)
 def test_complete_retry_rechecks_every_foreign_owner(self):
  query=Mock(return_value=[{'gpu_uuid':'g','pid':12,'used_memory_mib':'1'},{'gpu_uuid':'g','pid':13,'used_memory_mib':'1'}])
  with patch.object(resource_gate,'admission_document'),patch.object(service,'proc_uid',side_effect=[os.getuid()+1,None,os.getuid()+1,os.getuid()+1]) as uid:
   r=service.wait_admission_snapshot(self.admission,self.queue,query=query,clock=self.clock.now,sleep=self.clock.sleep)
  self.assertEqual(uid.call_count,4);self.assertEqual(query.call_count,2);self.assertEqual(r['attempts'],2)
 def test_submission_uses_complete_admission_retry(self):
  with patch.object(job,'RUN',ROOT),patch.object(service,'queue_at',return_value=self.queue),patch.object(service,'wait_admission_snapshot') as retry:
   job.check_host_admission({'pid':77})
  self.assertEqual(retry.call_args.kwargs['exclude_pid'],77)
if __name__=='__main__':unittest.main()
