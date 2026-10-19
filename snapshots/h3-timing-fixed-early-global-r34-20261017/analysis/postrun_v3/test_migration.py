import json,subprocess,sys,tempfile,unittest
from pathlib import Path
import contract as c
import bind_auto_parent as binder
import consume
import test_postrun as parent_tests
class MigrationTests(unittest.TestCase):
 def test_only_parent_protocol_path_changes(self):
  old=c.HERE.parent/'postrun';a=c.read(old/'PROTOCOL.json');b=c.read(c.HERE/'PROTOCOL.json');self.assertNotEqual(a['auto_parent_root'],b['auto_parent_root']);a['auto_parent_root']=b['auto_parent_root'];self.assertEqual(a,b)
  for name in ('remote_consume.py','contract.py','outcome.py','timing_metrics.py','scan_current_pose.py','pairwise_gain.py','physical_tolerance.py','evaluate_helpers.py'):
   self.assertEqual((old/name).read_bytes(),(c.HERE/name).read_bytes())
 def test_actual_new_summary_parent_path_and_old_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);b,p=parent_tests.ParentTests().fixture(root);new='/data5/producer/analysis/postrun_bounded_v2/captured/auto';p['auto_parent_root']=new
   c.save(root/'final/FINAL_SUMMARY.json',{'pose':new+'/final/pose/f.pose.json','video':new+'/output/auto_00001_.mp4','pose_sha256':b['pose_sha256'],'video_sha256':b['video_sha256']})
   result=binder.build(root,p);self.assertEqual(result['parent_root'],new);self.assertEqual(result['pose_relative'],'final/pose/f.pose.json')
   p['auto_parent_root']=new.replace('postrun_bounded_v2','postrun')
   with self.assertRaises(ValueError):binder.build(root,p)
 def test_new_remote_shared_lock_and_fresh_authorization(self):
  self.assertTrue(consume.REMOTE.endswith('/analysis/postrun_v3'));self.assertIn("analysis/postrun/unique_consumer.lock",(c.HERE/'one_phase.py').read_text());self.assertFalse(c.read(c.HERE/'BINDING.template.json')['approved_for_consumer_start']);self.assertEqual(c.read(c.HERE/'BINDING.template.json')['protocol_sha256'],c.sha(c.HERE/'PROTOCOL.json'));self.assertFalse((c.HERE/'BINDING.json').exists())
 def test_fresh_all_imports(self):
  r=subprocess.run([sys.executable,'-c','import consume,one_phase,remote_consume,bind_auto_parent,outcome,contract,evaluate_helpers,scan_current_pose,pairwise_gain,timing_metrics,physical_tolerance'],cwd=c.HERE,capture_output=True,text=True,timeout=20);self.assertEqual(r.returncode,0,r.stderr)
if __name__=='__main__':unittest.main()
