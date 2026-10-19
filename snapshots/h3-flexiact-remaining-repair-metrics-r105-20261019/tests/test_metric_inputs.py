import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import metric_inputs as m
class Metrics(unittest.TestCase):
 def fixture(self,root):
  (root/'inputs').mkdir();(root/'inputs/ref.mp4').write_bytes(b'reference fixture');(root/'inputs/portrait.jpg').write_bytes(b'portrait fixture');(root/'native.mp4').write_bytes(b'native fixture');(root/'forced.mp4').write_bytes(b'forced fixture')
  p={'source_id':'human2animal_2__movie_man_11','source':{'file':'inputs/ref.mp4','sha256':m.sha(root/'inputs/ref.mp4')},'portrait':{'file':'inputs/portrait.jpg','sha256':m.sha(root/'inputs/portrait.jpg')},'geometry':{'frames':158},'valid_frames':147,'evaluation_indices':list(range(0,147,3)),'crop_xywh':[0,0,1152,768],'original_task':{'edit_prompt':'official task'}};g={'runs':{k:{'video':{'file':'/producer/'+k+'.mp4','sha256':m.sha(root/(k+'.mp4'))}} for k in ('native','forced')}};return p,g
 def test_native_ready_excludes_forced_and_scores(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);p,g=self.fixture(r)
   with patch.object(m,'ROOT',r):v=m.bind_media(p,g,r,False)
   self.assertEqual(set(v['raw_videos']),{'source','native'});self.assertIsNone(v['score']);self.assertEqual(v['status'],'inputs_ready_score_pending');self.assertEqual(v['evaluate_indices'],list(range(0,147,3)))
 def test_paired_ready_uses_actual_three_videos(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);p,g=self.fixture(r)
   with patch.object(m,'ROOT',r):v=m.bind_media(p,g,r,True)
   self.assertEqual(set(v['raw_videos']),{'source','native','forced'});self.assertEqual(v['valid_frames'],147);self.assertEqual(v['crop_xywh'],[0,0,1152,768]);self.assertFalse(v['GPU_started'])
 def test_changed_generated_or_source_file_rejected(self):
  for changed in ['native.mp4','forced.mp4','inputs/ref.mp4','inputs/portrait.jpg']:
   with tempfile.TemporaryDirectory() as d:
    r=Path(d);p,g=self.fixture(r);(r/changed).write_bytes(b'changed')
    with patch.object(m,'ROOT',r),self.assertRaisesRegex(ValueError,'SHA differs'):m.bind_media(p,g,r,True)
if __name__=='__main__':unittest.main()
