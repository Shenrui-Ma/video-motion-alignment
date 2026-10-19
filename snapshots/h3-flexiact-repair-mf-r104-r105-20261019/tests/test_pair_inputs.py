import copy,sys,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from prepare_pair import verify_manifest,INDICES
class TestInputs(unittest.TestCase):
 def values(self):
  return ({'evaluate_indices':INDICES,'evaluation_fps':8,'valid_frames':147,'raw_videos':{'source':{},'native':{'sha256':'n'},'forced':{'sha256':'f'}}},
          {'source_original_sha256':'s','official_source':{'sha256':'s'}},
          {'passed':True,'checks':{'actual_conditions':True},'runs':{'native':{'video':{'sha256':'n'}},'forced':{'video':{'sha256':'f'}}}})
 def test_actual_binding(self):self.assertTrue(verify_manifest(*self.values()))
 def test_padding_frame_rejected(self):
  m,p,g=self.values();m['evaluate_indices']=list(range(0,156,3))
  with self.assertRaises(ValueError):verify_manifest(m,p,g)
 def test_changed_source_rejected(self):
  m,p,g=self.values();p['source_original_sha256']='processed24fps'
  with self.assertRaises(ValueError):verify_manifest(m,p,g)
 def test_missing_guided_rejected(self):
  m,p,g=self.values();del m['raw_videos']['forced']
  with self.assertRaises(ValueError):verify_manifest(m,p,g)
 def test_failed_actual_gate_rejected(self):
  m,p,g=self.values();g['checks']['actual_conditions']=False
  with self.assertRaises(ValueError):verify_manifest(m,p,g)
 def test_wrong_generated_binding_rejected(self):
  m,p,g=self.values();m['raw_videos']['forced']['sha256']='different'
  with self.assertRaises(ValueError):verify_manifest(m,p,g)
if __name__=='__main__':unittest.main()
