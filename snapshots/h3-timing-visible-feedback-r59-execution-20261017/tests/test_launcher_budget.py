import json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import service,launch_remote,service_entry

class Clock:
 def __init__(self):self.value=0
 def now(self):return self.value
 def sleep(self,d):self.value+=d
class Proc:
 pid=40
 def __init__(self):self.stopped=False;self.signals=[]
 def poll(self):return 0 if self.stopped else None
 def terminate(self):self.stopped=True;self.signals.append('TERM')
 def kill(self):self.stopped=True;self.signals.append('KILL')
 def wait(self,timeout):return 0
class LauncherBudget(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'processes').mkdir();self.proc=Proc();self.ident={'uid':os.getuid(),'start_ticks':'77','cmdline':'own supervisor'};self.ext={'uid':os.getuid(),'start_ticks':'77','cmdline_sha256':'hash'}
 def tearDown(self):self.tmp.cleanup()
 def test_resource_wait_longer_than_ten_seconds_can_succeed(self):
  clock=Clock();owner={'pid':41,'identity':{}};gate={'pid':41,'identity':self.ext,'supervisor':{'pid':40,'identity':self.ext}}
  def sleep(d):
   clock.sleep(d)
   if clock.value>=15:
    (self.root/'processes/cuda_gate_ready.json').write_text(json.dumps(gate));(self.root/'processes/service.json').write_text('{}')
  with patch.object(service,'current_identity',return_value=self.ident),patch.object(service,'external_identity',return_value=self.ext),patch.object(service,'assert_owned'),patch.object(launch_remote,'created_owner',return_value=owner):
   result=launch_remote.wait_service_gate(self.root,self.proc,self.ident,clock=clock.now,sleep=sleep)
  self.assertEqual(result,(gate,owner));self.assertGreaterEqual(clock.value,15)
 def test_deadline_stops_exact_waiting_supervisor(self):
  clock=Clock()
  def current(pid):return None if self.proc.stopped else self.ident
  with patch.object(service,'current_identity',side_effect=current),patch.object(launch_remote,'cleanup_created_owner',return_value={'stopped':False,'reason':'not-created'}):
   with self.assertRaises(TimeoutError):launch_remote.wait_service_gate(self.root,self.proc,self.ident,timeout=3,clock=clock.now,sleep=clock.sleep)
   result=launch_remote.cleanup_launch(self.root,self.proc,self.ident)
  self.assertEqual(self.proc.signals,['TERM']);self.assertTrue(result['original_supervisor_absent'])
 def test_cleanup_never_stops_replacement_supervisor(self):
  with patch.object(service,'current_identity',return_value=dict(self.ident,start_ticks='78')):
   with self.assertRaisesRegex(RuntimeError,'replaced supervisor'):launch_remote.cleanup_launch(self.root,self.proc,self.ident)
  self.assertEqual(self.proc.signals,[])
 def test_parent_guard_rejects_dead_or_reused_generation_before_ready(self):
  for actual in [None,dict(self.ext,start_ticks='78')]:
   with self.subTest(actual=actual):
    with self.assertRaisesRegex(RuntimeError,'supervisor generation'):service_entry.require_parent({'pid':40,'identity':self.ext},lambda pid:actual)
 def test_child_exits_during_root_go_wait_when_parent_disappears(self):
  target=self.root/'target.py';target.write_text('# no CUDA\n');lookups=iter([self.ext,None]);parent={'pid':40,'identity':self.ext}
  with self.assertRaisesRegex(RuntimeError,'supervisor generation'):
   service_entry.wait_gate(self.root/'processes',target,identity_fn=lambda:self.ext,parent=parent,parent_lookup=lambda pid:next(lookups))
  self.assertFalse((self.root/'processes/cuda_gate_go.json').exists())
if __name__=='__main__':unittest.main()
