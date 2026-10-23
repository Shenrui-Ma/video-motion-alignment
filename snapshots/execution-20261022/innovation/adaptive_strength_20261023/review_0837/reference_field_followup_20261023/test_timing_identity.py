import ast, sys, types, unittest, time
from pathlib import Path
from unittest.mock import patch
SOURCE=Path('/workspace/research-user/DevProjects/video-motion-alignment/execution-20261022/inference/package/custom_nodes/H3Study/__init__.py')
class TimerContract(unittest.TestCase):
 def setup_timer(self):
  tree=ast.parse(SOURCE.read_text()); cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Timer')
  self.records=[];ns={'time':time,'atomic':lambda path,data:self.records.append(data)}
  exec(compile(ast.Module(body=[cls],type_ignores=[]),str(SOURCE),'exec'),ns)
  return ns['Timer']('unused.json')
 def test_original_objects_and_all_callbacks_preserved(self):
  t=self.setup_timer();objects=[object() for _ in range(8)];received=[];result=object();calls=[]
  def callback(*a):received.append(a)
  def executor(model,sigmas,extra,cb,noise,latent,mask,disable):
   calls.append((model,sigmas,extra,noise,latent,mask,disable))
   for i in range(20):cb(i,objects[0],objects[1],20)
   return result
  fake=types.SimpleNamespace(cuda=types.SimpleNamespace(synchronize=lambda:None))
  with patch.dict(sys.modules,{'torch':fake}):out=t(executor,*objects[:3],callback,*objects[3:7])
  self.assertIs(out,result);self.assertEqual(len(calls),1);self.assertEqual(len(received),20)
  self.assertEqual(calls[0],tuple(objects[:3]+objects[3:7]))
  self.assertTrue(all(x[1] is objects[0] and x[2] is objects[1] for x in received))
  self.assertTrue(self.records[-1]['passed']);self.assertEqual(len(self.records[-1]['steps']),20)
 def test_exception_preserved_and_failed_recorded(self):
  t=self.setup_timer();err=RuntimeError('original sentinel')
  def executor(*args):raise err
  fake=types.SimpleNamespace(cuda=types.SimpleNamespace(synchronize=lambda:None))
  with patch.dict(sys.modules,{'torch':fake}):
   with self.assertRaises(RuntimeError) as cm:t(executor,None,None,None,None,None)
  self.assertIs(cm.exception,err);self.assertFalse(self.records[-1]['passed'])
if __name__=='__main__':unittest.main()
