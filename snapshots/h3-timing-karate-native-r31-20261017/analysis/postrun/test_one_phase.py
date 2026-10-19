import unittest,sys,tempfile
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parent))
import one_phase as one
class OnePhaseTests(unittest.TestCase):
 def test_default_never_executes(self):
  with mock.patch.object(sys,'argv',['one_phase.py']),mock.patch.object(one,'execute_one') as run:one.main();run.assert_not_called()
 def test_pending_failed_and_stability(self):
  for status in ('pending','failed'):self.assertEqual(one.readiness({'status':status},None,100,60),(status,None))
  snap={'status':'success_files_present','token':'A'};m,s=one.readiness(snap,None,100,60);self.assertEqual(m,'stabilizing');self.assertEqual(one.readiness(snap,s,159,60)[0],'stabilizing');self.assertEqual(one.readiness(snap,s,160,60)[0],'ready');self.assertEqual(one.readiness(dict(snap,token='B'),s,300,60),('stabilizing',{'token':'B','time':300}))
 def test_other_driver_excludes_setup_and_remote(self):
  import fcntl
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   with (p/'unique_consumer.lock').open('a') as held:
    fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with mock.patch.object(one,'HERE',p),mock.patch.object(one,'prepare') as prep,mock.patch.object(one.base,'remote') as remote:
     result=one.execute_one();self.assertEqual(result['status'],'busy');prep.assert_not_called();remote.assert_not_called()
 def test_at_most_one_phase_and_lock_release(self):
  import fcntl
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);cpu=p/'cpu.lock';cpu.touch();one.save(p/'ONE_PHASE_STABILITY.json',{'token':'A','time':0})
   replies=[{'status':'success_files_present','token':'A'},{'phase':'case','run':'only'},{'passed':True}]
   def response(args):return type('Result',(),{'returncode':0,'stdout':one.json.dumps(replies.pop(0)),'stderr':''})()
   with mock.patch.object(one,'HERE',p),mock.patch.object(one.base,'CPU',cpu),mock.patch.object(one,'prepare'),mock.patch.object(one.base,'remote',side_effect=response) as calls,mock.patch.object(one.base,'download') as download:
    result=one.execute_one();self.assertEqual(result['status'],'phase_complete');self.assertEqual(calls.call_args_list,[mock.call(['snapshot']),mock.call(['status']),mock.call(['case','--run','only'])]);download.assert_not_called()
   for lock in (cpu,p/'unique_consumer.lock'):
    with lock.open('a') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
if __name__=='__main__':unittest.main()
