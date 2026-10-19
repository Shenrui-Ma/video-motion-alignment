import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import execution_gate as g
class CapacityTrial(unittest.TestCase):
 def run_approval(self,mib):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);(r/'configs').mkdir();(r/'audit').mkdir();runtime={'gpu_uuid':'GPU-test'};(r/'configs/runtime.json').write_text(json.dumps(runtime))
   value={'schema':'r116-native-screen-approval-v1','root_approved':True,'runtime_profile_sha256':g.sha(r/'configs/runtime.json'),'main_gpu_uuid':'GPU-test','registered_runs':['p0','p1'],'required_free_bytes':mib*1024**2,'reserve_vram_gib':8,'capacity_status':'ACTUAL_FULL_TRAJECTORY_PENDING'}
   (r/'audit/ROOT_SCREEN_APPROVAL.json').write_text(json.dumps(value))
   with patch.object(g,'registry',return_value=({},['p0','p1'])):return g.approval(r)
 def test_40gib_is_explicit_pending_trial(self):
  self.assertEqual(self.run_approval(40960)['capacity_status'],'ACTUAL_FULL_TRAJECTORY_PENDING')
 def test_less_than_40gib_rejected(self):
  with self.assertRaisesRegex(ValueError,'scope or headroom'):self.run_approval(40959)
if __name__=='__main__':unittest.main()
