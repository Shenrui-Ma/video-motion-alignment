import copy,unittest
from unittest.mock import patch
import import_scores as m
DATA=m.read(m.ROOT/'inventory/ivebench.json')['items']
class BindingTests(unittest.TestCase):
 def test_actual_0252(self):
  item=next(x for x in DATA if x['id']=='r73_short_0252');n,g,_,_=m.normal(item,73);self.assertAlmostEqual(n,.8026777861879288);self.assertAlmostEqual(g,.8024124040915745)
 def test_changed_display_output_rejected(self):
  item=copy.deepcopy(next(x for x in DATA if x['id']=='r73_short_0252'));item['media_sha256']['guided_video_path']='0'*64
  with self.assertRaises(ValueError):m.normal(item,73)
 def test_wrong_source_rejected(self):
  item=copy.deepcopy(next(x for x in DATA if x['id']=='r73_short_0252'));item['media_sha256']['reference_video_path']='1'*64
  with self.assertRaises(ValueError):m.normal(item,73)
 def test_wrong_valid_support_rejected(self):
  item=copy.deepcopy(next(x for x in DATA if x['id']=='r73_short_0252'));item['valid_frames']=97
  with self.assertRaises(ValueError):m.normal(item,73)
 def test_official_cropped_display(self):
  item=next(x for x in DATA if x['id']=='r63_short_0210');n,g,_,_=m.normal(item,63);self.assertTrue(n>0 and g>0)
 def test_exact_reuse(self):
  item=next(x for x in DATA if x['id']=='r55_short_0210');n,g,_,_=m.reused(item);self.assertEqual(n,g);self.assertEqual(n,.8043357672003687)
 def test_pending_is_null(self):
  item=next(x for x in DATA if x['id']=='r89_short_0358');v,e=m.process(item);self.assertEqual(v['status'],'pending');self.assertIsNone(v['native']);self.assertIsNone(v['guided']);self.assertIsNone(v['delta'])
 def test_mismatched_report_rejected(self):
  item=next(x for x in DATA if x['id']=='r73_short_0252');orig=m.Evidence.bound
  def altered(self,row):
   v=orig(self,row)
   if '/tracks/native/' in row['file']:v=copy.deepcopy(v);v['tracks_sha256']='1'*64
   return v
  with patch.object(m.Evidence,'bound',altered),self.assertRaises(ValueError):m.normal(item,73)
if __name__=='__main__':unittest.main()
