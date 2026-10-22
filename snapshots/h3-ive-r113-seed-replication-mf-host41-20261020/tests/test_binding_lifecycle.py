import unittest,sys,copy,subprocess,os
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common,run_batch

def report():
 return dict(passed=True,checkpoint_sha256='dbb9006c0dc89479c34993ac23d37ae0af13deac18be6028009d7483754b2fc3',metric_functions_sha256='same',vendor_manifest_sha256='same',grid_size=55,mask=None,tracks_dtype='torch.float32',tracks_shape=[3025,49,2],timebase=dict(frames=[dict(best_effort_timestamp_time=i/8)for i in range(49)]),case=dict(id='human/fitness/000',role='reference',sha256='src'))
M=dict(canonical_id='human/fitness/000',source_score_sha256='src')
class TestBindings(unittest.TestCase):
 def check(self,r,role='source',target=None):
  with patch.object(common,'sha',return_value='same'):common.validate_flex_report(r,M,role,target)
 def test_valid_source(self):self.check(report())
 def test_wrong_direction(self):
  r=report();r['case']['role']='generated'
  with self.assertRaises(AssertionError):self.check(r)
 def test_wrong_source(self):
  r=report();r['case']['sha256']='other'
  with self.assertRaises(AssertionError):self.check(r)
 def test_generated_binding(self):
  r=report();r['case'].update(role='generated',sha256='target');self.check(r,'target_00',{'score_sha256':'target'})
  with self.assertRaises(AssertionError):self.check(r,'target_00',{'score_sha256':'other'})
 def test_time_shift(self):
  r=report();r['timebase']['frames'][3]['best_effort_timestamp_time']=.5
  with self.assertRaises(AssertionError):self.check(r)
 def test_wrong_grid(self):
  r=report();r['grid_size']=10
  with self.assertRaises(AssertionError):self.check(r)
 def test_wrong_shape(self):
  r=report();r['tracks_shape']=[3025,48,2]
  with self.assertRaises(AssertionError):self.check(r)
 def test_wrong_checkpoint(self):
  r=report();r['checkpoint_sha256']='different'
  with self.assertRaises(AssertionError):self.check(r)
 def test_source_task_mismatch(self):
  r=report();r['case']['id']='human/crouch/000'
  with self.assertRaises(AssertionError):self.check(r)
class TestLifecycle(unittest.TestCase):
 def test_oom_new_and_reset(self):
  b={'ancestors':[dict(path='/user.slice',events={'oom':4,'oom_kill':1})]};a=copy.deepcopy(b);self.assertEqual(run_batch.oom_delta(b,a)['/user.slice']['oom'],0)
  for value in [3,5]:
   a['ancestors'][0]['events']['oom']=value
   with self.assertRaises(AssertionError):run_batch.oom_delta(b,a)
 def test_exact_child_cleanup(self):
  child=subprocess.Popen(['/bin/sleep','30']);ident=dict(pid=child.pid,start_ticks='expected')
  with patch.object(run_batch,'identity',return_value=ident),patch.object(run_batch,'cuda_pids',return_value=set()):r=run_batch.cleanup(child,ident)
  self.assertTrue(r['process_absent']);self.assertIsNotNone(child.poll())
 def test_reused_identity_rejected(self):
  child=subprocess.Popen(['/bin/sleep','30']);ident=dict(pid=child.pid,start_ticks='wrong')
  try:
   with patch.object(run_batch,'identity',return_value=dict(pid=child.pid,start_ticks='expected')),patch.object(run_batch,'cuda_pids',return_value=set()):
    with self.assertRaises(AssertionError):run_batch.cleanup(child,ident)
   self.assertIsNone(child.poll())
  finally:child.terminate();child.wait()
if __name__=='__main__':unittest.main()
