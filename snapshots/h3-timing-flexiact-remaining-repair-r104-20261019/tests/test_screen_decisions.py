import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import execution_gate as g
class ScreenDecisions(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.r=Path(self.tmp.name)
  self.sources=('a','b','c');self.jobs={f'r104_{s}_seed2026101701_{a}':{'source_id':s,'arm':a} for s in self.sources for a in ('native','forced')};self.order=list(self.jobs)
  self.owner={'pid':100,'identity':{'uid':10,'start_ticks':'20','cmdline':'test'}}
  g.atomic(self.r/'configs/runtime.json',{'gpu_uuid':'GPU-test'});g.atomic(self.r/'processes/service.json',self.owner)
  g.atomic(self.r/'audit/ROOT_SCREEN_APPROVAL.json',{'schema':'r104-native-screen-approval-v1','root_approved':True,'runtime_profile_sha256':g.sha(self.r/'configs/runtime.json'),'main_gpu_uuid':'GPU-test','registered_runs':self.order,'required_free_bytes':40*1024**3,'reserve_vram_gib':8})
  self.addCleanup(patch.stopall);patch.object(g,'SOURCES',self.sources).start();patch.object(g,'registry',return_value=(self.jobs,self.order)).start()
 def native(self,s):
  run=f'r104_{s}_seed2026101701_native';video=self.r/'output'/(run+'.mp4');video.parent.mkdir(exist_ok=True);video.write_bytes(b'actual'+s.encode())
  artifact=self.r/'audit'/(s+'_noise.pt');artifact.write_bytes(b'noise'+s.encode())
  value={'schema':'r104-native-runtime-gate-v1','source_id':s,'passed':True,'runtime_profile_sha256':g.sha(self.r/'configs/runtime.json'),'service_owner':copy.deepcopy(self.owner),'runs':{'native':{'run_id':run,'NFE':20,'routed_blocks':0,'binding_artifacts':{str(artifact.relative_to(self.r)):g.sha(artifact)},'video':{'file':str(video),'sha256':g.sha(video)}}},'created_unix':1}
  g.atomic(self.r/'analysis/postrun'/s/'NATIVE_RUNTIME_GATE.json',value)
 def pair(self,s):
  g.atomic(self.r/'analysis/postrun'/s/'PAIR_RUNTIME_GATE.json',{'source_id':s,'passed':True,'runs':{'native':{},'forced':{}},'service_owner':self.owner})
 def decide(self,s,choice):return g.write_decision(self.r,s,choice,'root visual review')
 def test_service_memory_profile_binds_new_screen_approval(self):
  import service
  with patch.object(service,'RUN',self.r):v=service.main_memory_profile()
  self.assertEqual(v['profile_sha256'],g.sha(self.r/'audit/ROOT_SCREEN_APPROVAL.json'));self.assertEqual(v['required_free_bytes'],40*1024**3)
 def test_exact_watchdog_idle_expiry_recognized_only_for_review(self):
  import run_queue
  g.atomic(self.r/'audit/watchdog_runtime_v2/STOP_REASON.json',{'reason':'bounded_idle_review_expired','owner':self.owner})
  with patch.object(run_queue.service,'RUN',self.r),patch.object(run_queue.service,'current_identity',return_value=None):
   self.assertTrue(run_queue.expired_review_owner(self.owner,'awaiting_native_review'));self.assertFalse(run_queue.expired_review_owner(self.owner,None))
   changed=copy.deepcopy(self.owner);changed['identity']['start_ticks']='bad';self.assertFalse(run_queue.expired_review_owner(changed,'awaiting_native_review'))
  with patch.object(run_queue.service,'RUN',self.r),patch.object(run_queue.service,'current_identity',return_value=self.owner['identity']):self.assertFalse(run_queue.expired_review_owner(self.owner,'awaiting_native_review'))
 def test_first_native_allowed_but_first_forced_waits_review(self):
  self.assertTrue(g.admitted_job(self.order[0],self.r));self.assertFalse(g.admitted_job(self.order[1],self.r));self.assertFalse(g.admitted_job(self.order[2],self.r))
 def test_decision_before_actual_native_rejected(self):
  with self.assertRaises(FileNotFoundError):self.decide('a','guide')
 def test_skip_creates_only_native_terminal_and_allows_next(self):
  self.native('a');self.decide('a','skip');self.assertFalse(g.admitted_job(self.order[1],self.r));row=g.finish_source(self.r,'a');self.assertEqual(row['status'],'native_only');self.assertIsNone(row['forced_run']);self.assertIsNone(row['pair_gate_sha256']);self.assertTrue(g.admitted_job(self.order[2],self.r))
 def test_later_first_guided_requires_actual_review_before_next(self):
  self.native('a');self.decide('a','skip');g.finish_source(self.r,'a');self.native('b');self.decide('b','guide');self.assertTrue(g.admitted_job(self.order[3],self.r));self.pair('b');g.finish_source(self.r,'b');self.assertFalse(g.admitted_job(self.order[4],self.r));g.write_first_review(self.r);self.assertTrue(g.admitted_job(self.order[4],self.r))
 def test_all_skip_needs_no_guided_capacity_claim(self):
  for s in self.sources:self.native(s);self.decide(s,'skip');g.finish_source(self.r,s)
  self.assertIsNone(g.first_guided(self.r));self.assertEqual(len(g.ledger(self.r)['rows']),3)
 def test_first_guided_review_cannot_precede_pair(self):
  with self.assertRaisesRegex(ValueError,'no actual'):g.write_first_review(self.r)
 def test_future_native_decision_refused(self):
  self.native('b')
  with self.assertRaisesRegex(ValueError,'only current'):self.decide('b','skip')
 def test_decision_cannot_be_rewritten(self):
  self.native('a');self.decide('a','skip')
  with self.assertRaises(FileExistsError):self.decide('a','guide')
 def test_changed_service_generation_refused(self):
  self.native('a');self.decide('a','guide');changed=copy.deepcopy(self.owner);changed['identity']['start_ticks']='21';g.atomic(self.r/'processes/service.json',changed)
  with self.assertRaisesRegex(ValueError,'owner/runtime'):g.admitted_job(self.order[1],self.r)
 def test_changed_noise_cache_refused_before_submit(self):
  self.native('a');self.decide('a','guide');(self.r/'audit/a_noise.pt').write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'evidence changed'):g.admitted_job(self.order[1],self.r)
 def test_changed_video_refused(self):
  self.native('a');self.decide('a','skip');next((self.r/'output').glob('*')).write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'output changed'):g.finish_source(self.r,'a')
 def test_skip_after_any_forced_submission_refused(self):
  self.native('a');self.decide('a','skip');g.atomic(self.r/'logs'/f'{self.order[1]}_job.json',{'status':'submission_uncertain'})
  with self.assertRaisesRegex(ValueError,'skip after'):g.finish_source(self.r,'a')
 def test_gate_recheck_preserves_raw_byte_hash(self):
  p=self.r/'audit/gate.json';v={'passed':True,'created_unix':1,'video':'good'};g.persist_gate(p,v);digest=g.sha(p);v['created_unix']=9;g.persist_gate(p,v);self.assertEqual(g.sha(p),digest);v['video']='changed'
  with self.assertRaisesRegex(ValueError,'evidence changed'):g.persist_gate(p,v)
 def test_tampered_first_pair_review_refused(self):
  self.native('a');self.decide('a','guide');self.pair('a');g.finish_source(self.r,'a');g.write_first_review(self.r);p=self.r/'audit/FIRST_GUIDED_REVIEW.json';v=g.read(p);v['pair_gate_sha256']='bad';g.atomic(p,v)
  with self.assertRaisesRegex(ValueError,'review differs'):g.admitted_job(self.order[2],self.r)
if __name__=='__main__':unittest.main()
