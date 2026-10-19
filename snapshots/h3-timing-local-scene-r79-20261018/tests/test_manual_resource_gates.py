import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import execution_gate as g,service,lease_watchdog,run_queue,start_controller
class Clock:
 def __init__(self):self.value=0.
 def now(self):return self.value
 def sleep(self,t):self.value+=t
class ManualGates(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.r=Path(self.tmp.name);self.n='r79_short_0144_seed2026101701_native';self.f=self.n.replace('_native','_forced');self.other='r79_short_0166_seed2026101701_native';self.runs=[self.n,self.f,self.other];self.jobs={}
  g.atomic(self.r/'configs/runtime.json',{'gpu_uuid':'GPU-test'})
  for name,arm in [(self.n,'native'),(self.f,'forced'),(self.other,'native')]:
   p=self.r/'configs/graphs'/f'{name}.json';g.atomic(p,{'test':name});self.jobs[name]={'arm':arm,'graph_sha256':g.sha(p)}
  self.reg=patch.object(g,'registry',return_value=(self.jobs,self.runs));self.reg.start()
  g.atomic(self.r/'audit/ROOT_SERVICE_APPROVAL.json',{'schema':'r79-service-capacity-trial-v1','root_approved':True,'runtime_profile_sha256':g.sha(self.r/'configs/runtime.json'),'main_gpu_uuid':'GPU-test','required_free_bytes':40*1024**3,'reserve_vram_gib':8,'capacity_status':'ACTUAL_FULL_TRAJECTORY_PENDING'})
 def tearDown(self):self.reg.stop();self.tmp.cleanup()
 def success(self):
  owner={'pid':123,'identity':{'start_ticks':'100','uid':1004}};g.atomic(self.r/'processes/service.json',owner)
  g.atomic(self.r/'logs'/f'{self.n}_job.json',dict(name=self.n,status='success',graph_sha256=self.jobs[self.n]['graph_sha256'],prompt_id='uuid',service_pid=123,service_identity=owner['identity']))
  g.atomic(self.r/'logs'/f'{self.n}_history.json',dict(status={'completed':True,'status_str':'success'},prompt=[0,'uuid',g.read(self.r/'configs/graphs'/f'{self.n}.json')],outputs={'14':{'images':[{'filename':'actual.mp4'}]}}))
 def test_service_does_not_approve_jobs(self):
  self.assertFalse(g.admitted_job(self.n,self.r));self.assertFalse(g.admitted_job(self.f,self.r))
 def test_native_individual_scope(self):
  g.approve_run(self.n,self.r);self.assertTrue(g.admitted_job(self.n,self.r));self.assertFalse(g.admitted_job(self.other,self.r));self.assertFalse(g.admitted_job(self.f,self.r))
 def test_forced_requires_review(self):
  self.success()
  with self.assertRaisesRegex(ValueError,'visual review'):g.approve_run(self.f,self.r)
 def test_review_requires_completed_native(self):
  with self.assertRaises(FileNotFoundError):g.approve_run(self.f,self.r,native_reviewed=True)
 def test_forced_requires_same_generation(self):
  self.success();g.approve_run(self.f,self.r,native_reviewed=True);self.assertTrue(g.admitted_job(self.f,self.r));p=self.r/'processes/service.json';v=g.read(p);v['pid']=124;g.atomic(p,v)
  with self.assertRaisesRegex(ValueError,'generation'):g.admitted_job(self.f,self.r)
 def test_history_rewrite_rejected(self):
  self.success();g.approve_run(self.f,self.r,native_reviewed=True);p=self.r/'logs'/f'{self.n}_history.json';v=g.read(p);v['new']='change';g.atomic(p,v)
  with self.assertRaisesRegex(ValueError,'evidence changed'):g.admitted_job(self.f,self.r)
 def test_incomplete_history_rejected(self):
  self.success();p=self.r/'logs'/f'{self.n}_history.json';v=g.read(p);v['status']['completed']=False;g.atomic(p,v)
  with self.assertRaisesRegex(ValueError,'history has not'):g.approve_run(self.f,self.r,native_reviewed=True)
 def test_changed_runtime_rejected(self):
  g.approve_run(self.n,self.r);g.atomic(self.r/'configs/runtime.json',{'gpu_uuid':'GPU-other'})
  with self.assertRaisesRegex(ValueError,'runtime/device'):g.admitted_job(self.n,self.r)
 def test_changed_graph_rejected(self):
  g.approve_run(self.n,self.r);self.jobs[self.n]['graph_sha256']='changed'
  with self.assertRaisesRegex(ValueError,'graph/runtime'):g.admitted_job(self.n,self.r)
 def test_auto_launchers_disabled(self):
  with self.assertRaisesRegex(RuntimeError,'automatic queue disabled'):run_queue.run()
  with self.assertRaisesRegex(RuntimeError,'automatic controller disabled'):start_controller.main()
class Release(unittest.TestCase):
 def setUp(self):self.c=Clock();self.owner={'pid':123,'identity':{'uid':1004,'start_ticks':'100'}};self.foreign={'pid':999,'gpu_uuid':service.GPU,'used_memory_mib':'4000'};self.own={'pid':123,'gpu_uuid':service.GPU,'used_memory_mib':'100'}
 def wait(self,rows,identity=None):
  with patch.object(service,'compute_processes',side_effect=rows),patch.object(service,'current_identity',return_value=identity),patch.object(service.os,'kill') as kill:
   v=service.wait_compute_release(self.owner,clock=self.c.now,sleep=self.c.sleep);kill.assert_not_called();return v
 def test_transient_tail_waits(self):
  v=self.wait([[self.own,self.foreign],[self.own,self.foreign],[self.foreign]]);self.assertTrue(v['own_compute_absent']);self.assertEqual(v['release_wait_seconds'],1.);self.assertEqual(v['remaining_gpu_processes'],[self.foreign])
 def test_persistent_tail_times_out(self):
  v=self.wait([[self.own]]*61);self.assertFalse(v['own_compute_absent']);self.assertEqual(v['release_wait_seconds'],30.)
 def test_reused_pid_never_signaled(self):
  v=self.wait([],{'uid':1004,'start_ticks':'101'});self.assertTrue(v['pid_reused']);self.assertFalse(v['process_absent'])
 def test_foreign_alone_does_not_delay(self):
  v=self.wait([[self.foreign]]);self.assertTrue(v['own_compute_absent']);self.assertEqual(v['release_wait_seconds'],0.)
class Lease(unittest.TestCase):
 def setUp(self):self.s=dict(started=0,last_http=0,idle_since=None,active_since=None);self.l=dict(max_service_seconds=43200,job_timeout_seconds=14400,idle_hold_seconds=1800)
 def test_idle_bounded(self):
  q={'queue_running':[],'queue_pending':[]};self.assertIsNone(lease_watchdog.reason(self.s,100,q,self.l));self.assertEqual(lease_watchdog.reason(self.s,1900,q,self.l),'bounded_idle_review_expired')
 def test_running_job_exceeds_old_controller_grace(self):
  q={'queue_running':[1],'queue_pending':[]};self.assertIsNone(lease_watchdog.reason(self.s,0,q,self.l));self.assertIsNone(lease_watchdog.reason(self.s,1800,q,self.l));self.assertEqual(lease_watchdog.reason(self.s,14400,q,self.l),'bounded_job_timeout')
 def test_http_unavailable_bounded(self):self.assertEqual(lease_watchdog.reason(self.s,900,None,self.l),'HTTP_unavailable_timeout')
if __name__=='__main__':unittest.main()
