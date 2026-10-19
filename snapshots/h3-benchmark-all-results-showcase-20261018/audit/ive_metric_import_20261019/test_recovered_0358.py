import copy,unittest
from unittest.mock import patch
from pathlib import Path
import import_recovered_0358 as m
class RecoveredBinding(unittest.TestCase):
 def setUp(self):self.item=copy.deepcopy(next(x for x in m.read(m.ROOT/'inventory/ivebench.json')['items'] if x['id']=='r89_short_0358'))
 def test_actual_binding(self):
  r=m.verify(self.item);self.assertEqual(r['status'],'complete');self.assertEqual(r['delta'],r['guided']-r['native'])
 def test_other_output_rejected(self):
  self.item['media_sha256']['guided_video_path']='0'*64
  with self.assertRaisesRegex(ValueError,'media bytes'):m.verify(self.item)
 def test_failed_gate_rejected(self):
  load=m.Evidence.load
  def altered(e,p,digest=None):
   v=copy.deepcopy(load(e,p,digest))
   if Path(p).name=='PAIR_RUNTIME_GATE.json':v['passed']=False
   return v
  with patch.object(m.Evidence,'load',altered),self.assertRaisesRegex(ValueError,'gate failed'):m.verify(self.item)
 def test_different_tracker_runtime_rejected(self):
  load=m.Evidence.load
  def altered(e,p,digest=None):
   v=copy.deepcopy(load(e,p,digest))
   if Path(p)==m.RECOVERY/'tracks/forced/REPORT.json':v['cuda_version']='unexpected'
   return v
  with patch.object(m.Evidence,'load',altered),self.assertRaisesRegex(ValueError,'tracker mismatch'):m.verify(self.item)
if __name__=='__main__':unittest.main()
