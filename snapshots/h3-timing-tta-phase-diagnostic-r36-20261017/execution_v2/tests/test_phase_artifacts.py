import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import phase_artifacts as pa
import contract


def setup(root):
 (root/'FREEZE.json').write_text('{}');dest=root/'views/test/flip';a=pa.create_attempt(dest)
 (a/'inverse.pose.json').write_text('{}');(a/'pose.log').write_text('complete')
 entry={'id':'test','video_sha256':'v','identity_pose_sha256':'p'}
 c={'status':'complete','phase':'pose:test:flip','attempt':str(a.relative_to(dest)),'freeze_sha256':contract.sha(root/'FREEZE.json'),'input_video_sha256':'v','identity_pose_sha256':'p','files':{n:contract.sha(a/n) for n in ('inverse.pose.json','pose.log')},'inverse_pose_sha256':contract.sha(a/'inverse.pose.json')}
 (a/'VALIDATED.json').write_text(json.dumps(c))
 return dest,a,entry,c

class TestPhaseArtifacts(unittest.TestCase):
 def test_commit_crash_recovers_without_new_attempt(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   with patch.object(pa,'ROOT',root):
    dest,a,e,c=setup(root);out=pa.completed_or_recover(dest,e,'flip');self.assertTrue((dest/'COMPLETE.json').exists());self.assertEqual(out['attempt'],c['attempt']);self.assertEqual(len(list((dest/'attempts').iterdir())),1)
    self.assertEqual(pa.completed_or_recover(dest,e,'flip'),out)
 def test_completed_corruption_refuses_reuse(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   with patch.object(pa,'ROOT',root):
    dest,a,e,c=setup(root);pa.completed_or_recover(dest,e,'flip');(a/'pose.log').write_text('changed')
    with self.assertRaisesRegex(ValueError,'changed'):pa.completed_or_recover(dest,e,'flip')
 def test_wrong_view_or_input_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   with patch.object(pa,'ROOT',root):
    dest,a,e,c=setup(root)
    for entry,view in [(e|{'video_sha256':'wrong'},'flip'),(e,'pad16')]:
     with self.assertRaises(ValueError):pa.completed_or_recover(dest,entry,view)
 def test_extra_file_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   with patch.object(pa,'ROOT',root):
    dest,a,e,c=setup(root);(a/'extra').write_text('x')
    with self.assertRaisesRegex(ValueError,'inventory'):pa.completed_or_recover(dest,e,'flip')
 def test_live_matching_worker_refuses_duplicate(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'v';a=pa.create_attempt(dest);(a/'CHILD.json').write_text(json.dumps({'identity':{'pid':123}}))
   with patch.object(pa,'owner_alive',return_value=True):
    with self.assertRaisesRegex(RuntimeError,'live phase'):pa.completed_or_recover(dest,{'id':'test'},'flip')
 def test_dead_attempt_preserved_next_directory_distinct(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'v';a=pa.create_attempt(dest);(a/'FAILURE.json').write_text('{}');(a/'CHILD.json').write_text(json.dumps({'identity':{'pid':123}}))
   with patch.object(pa,'owner_alive',return_value=False):self.assertIsNone(pa.completed_or_recover(dest,{'id':'test'},'flip'))
   b=pa.create_attempt(dest);self.assertNotEqual(a,b);self.assertTrue((a/'FAILURE.json').exists())
 def test_path_escape_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   with patch.object(pa,'ROOT',root):
    dest,a,e,c=setup(root);c['attempt']='../outside'
    with self.assertRaisesRegex(ValueError,'Attempt path'):pa.validate_record(dest,c,e,'flip')
 def test_pose_child_inherits_remote_cpu_lock(self):
  # Static contract ties parent-loss safety to the actual Popen call.
  import ast
  tree=ast.parse((ROOT/'scripts/run_pose_phase.py').read_text());calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='Popen']
  self.assertEqual(len(calls),1);self.assertIn('pass_fds',[k.arg for k in calls[0].keywords])


class TestActualInheritedLock(unittest.TestCase):
 def test_child_keeps_lock_after_parent_fd_closes(self):
  import fcntl,subprocess
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'lock';f=path.open('a');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   child=subprocess.Popen([sys.executable,'-c','import sys; print("ready",flush=True); sys.stdin.read()'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,pass_fds=(f.fileno(),))
   try:
    self.assertEqual(child.stdout.readline().strip(),'ready');f.close()
    with path.open('a') as other:
     with self.assertRaises(BlockingIOError):fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
    child.stdin.close();child.wait(timeout=3)
    with path.open('a') as other:fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
   finally:
    if not f.closed:f.close()
    if child.poll() is None:child.kill();child.wait()
    child.stdout.close()

if __name__=='__main__':unittest.main()
