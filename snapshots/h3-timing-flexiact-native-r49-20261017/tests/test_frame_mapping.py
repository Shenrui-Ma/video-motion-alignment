import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from release49 import INDICES,validate_probe
class FrameMappingTests(unittest.TestCase):
 def probe(self,n,fps):return {'streams':[{'width':1152,'height':768,'avg_frame_rate':str(fps)+'/1'}],'frames':[{'best_effort_timestamp_time':str(i/fps)} for i in range(n)]}
 def test_same_original_physical_times(self):
  self.assertEqual(list(INDICES),[3*i for i in range(49)])
  self.assertEqual([i/24 for i in INDICES],[i/8 for i in range(49)])
  self.assertEqual([min(i//3,48) for i in INDICES],list(range(49)))
 def test_valid_input_output_grids(self):
  validate_probe(self.probe(158,24),158,24);validate_probe(self.probe(49,8),49,8)
 def test_off_grid_fps_or_size_rejected(self):
  for key,val in [('width',720),('avg_frame_rate','8/1')]:
   x=self.probe(158,24);x['streams'][0][key]=val
   with self.assertRaises(ValueError):validate_probe(x,158,24)
 def test_shift_nonfinite_missing_frame_rejected(self):
  for val in ('nan','inf','0.3'):
   x=self.probe(158,24);x['frames'][0]['best_effort_timestamp_time']=val
   with self.assertRaises(ValueError):validate_probe(x,158,24)
  with self.assertRaises(ValueError):validate_probe(self.probe(157,24),158,24)
