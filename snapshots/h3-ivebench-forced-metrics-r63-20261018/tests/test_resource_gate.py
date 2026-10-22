import os,sys,types,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import track_one as m
class Proc:
 def __init__(self,pid):self.pid=pid
 def exists(self):return True
 def stat(self):return types.SimpleNamespace(st_uid=os.getuid() if self.pid in ('1','2') else os.getuid()+1)
class ProcRoot:
 def __truediv__(self,pid):return Proc(pid)
class Admission(unittest.TestCase):
 def check(self,processes,free=20000):
  outputs=iter([subprocess.CompletedProcess([],0,processes,''),subprocess.CompletedProcess([],0,'GPU-selected, '+str(free)+', 40\n','')])
  with patch.dict(os.environ,CUDA_VISIBLE_DEVICES='GPU-selected'),patch.object(m,'Path',return_value=ProcRoot()),patch.object(m.subprocess,'run',side_effect=lambda *a,**k:next(outputs)):
   return m.resource_check('GPU-selected')
 def test_foreign_same_card_and_one_own_other_card_allowed(self):self.assertEqual(self.check('9, GPU-selected\n1, GPU-main\n')['gpu_uuid'],'GPU-selected')
 def test_two_other_owned_cards_rejected(self):
  with self.assertRaisesRegex(ValueError,'two owned'):self.check('1, GPU-main\n2, GPU-extra\n')
 def test_insufficient_actual_headroom_rejected(self):
  with self.assertRaisesRegex(ValueError,'16GiB'):self.check('9, GPU-selected\n',10000)
if __name__=='__main__':unittest.main()
