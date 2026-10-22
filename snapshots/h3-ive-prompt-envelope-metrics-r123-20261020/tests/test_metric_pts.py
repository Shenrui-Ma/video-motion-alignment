import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import metric_inputs
from unittest.mock import patch
class PTSBinding(unittest.TestCase):
 def test_actual_sources_have_seconds_and_full_mapping(self):
  for source in ('short_0358',):
   p=metric_inputs.info(source);v=json.loads((ROOT/p['provenance']['file']).read_text())
   self.assertTrue(v['original_pts'])
   self.assertTrue(all(b>a for a,b in zip(v['original_pts'],v['original_pts'][1:])))
   self.assertTrue(all(0<=i<len(v['original_pts']) for i in v['input_to_original_frame'][:p['valid_frames']]))
 def test_native_actual_metric_binding(self):
  p=metric_inputs.info('short_0358');v=json.loads((ROOT/p['provenance']['file']).read_text())
  gate={'runs':{'native':{'video':{'sha256':'fixture'}}}}
  with patch.object(metric_inputs,'validate_static'),patch.object(metric_inputs,'verify_intake',return_value=gate),patch.object(metric_inputs,'save') as save,patch.object(metric_inputs,'bound',return_value={'file':'fixture','sha256':'fixture'}):
   metric_inputs.prepare('short_0358',False)
  data=save.call_args.args[1]
  self.assertEqual(data['original_pts_seconds'],v['original_pts'])
  self.assertNotIn('original_pts_rational',data)
  self.assertEqual(len(data['input_to_original_frame']),105)
if __name__=='__main__':unittest.main()
