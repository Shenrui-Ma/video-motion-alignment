import json,os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import parent_stop as p,capacity_trial as c
@unittest.skipUnless(sys.platform=='linux','Linux kernel parent-child semantics')
class ParentStopTests(unittest.TestCase):
 def child(self):
  x=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
  self.addCleanup(lambda:x.poll() is None and x.kill());self.addCleanup(lambda:None)
  for _ in range(50):
   row=c.identity(x.pid)
   if row:return x,row
   time.sleep(.01)
  self.fail('child identity unavailable')
 def finish(self,x):
  x.wait(timeout=3);self.assertEqual(x.returncode,-signal.SIGTERM)
 def test_direct_child_terminates(self):
  x,row=self.child();self.assertTrue(p.direct_child_signal(row,signal.SIGTERM,lookup=c.identity));self.finish(x)
 def test_stale_generation_and_other_uid(self):
  x,row=self.child()
  for bad in [dict(row,start_ticks=row['start_ticks']+1),dict(row,uid=row['uid']+1),dict(row,cmdline_sha256='stale')]:
   self.assertFalse(p.direct_child_signal(bad,signal.SIGTERM,lookup=c.identity))
  self.assertIsNone(x.poll());x.terminate();x.wait()
 def test_nonchild_not_signalled(self):
  row=c.identity(os.getpid())
  self.assertFalse(p.direct_child_signal(row,signal.SIGTERM,lookup=c.identity,kill=lambda *a:self.fail('nonchild signalled')))
 def test_parent_request_then_exact_child_signal(self):
  x,row=self.child()
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'processes').mkdir();owner={'pid':x.pid,'identity':{k:row[k] for k in ('uid','start_ticks','cmdline')}}
   parent=c.identity(os.getpid());registry={'pid':os.getpid(),'identity':{k:parent[k] for k in ('uid','start_ticks','cmdline')},'service_record':owner,'stop_protocol':p.PROTOCOL}
   (root/'processes/service.json').write_text(json.dumps(owner));(root/'processes/supervisor.json').write_text(json.dumps(registry))
   expected={k:row[k] for k in c.KEYS};self.assertTrue(p.request_stop(root,expected,signal.SIGTERM,lookup=c.identity));self.assertTrue(p.consume(root,row,lookup=c.identity));self.finish(x)
 def test_replaced_parent_channel_rejected(self):
  x,row=self.child()
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'processes').mkdir();owner={'pid':x.pid};parent=c.identity(os.getpid())
   (root/'processes/service.json').write_text(json.dumps(owner));(root/'processes/supervisor.json').write_text(json.dumps({'pid':os.getpid(),'identity':dict(parent,start_ticks=parent['start_ticks']+1),'service_record':owner,'stop_protocol':p.PROTOCOL}))
   with self.assertRaisesRegex(ValueError,'generation changed'):p.request_stop(root,row,signal.SIGTERM,lookup=c.identity)
  self.assertIsNone(x.poll());x.terminate();x.wait()
if __name__=='__main__':unittest.main()
