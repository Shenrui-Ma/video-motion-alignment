import copy,importlib.util,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'audit/prepare.py';spec=importlib.util.spec_from_file_location('pair_prepare',p);prep=importlib.util.module_from_spec(spec);spec.loader.exec_module(prep)
class PairDomain(unittest.TestCase):
 def sample(self):return {'source_id':'long_0081','valid_frames':120,'total_frames':124,'fps':24,'crop_xywh':[16,8,1280,720],'evaluation_indices':list(range(120)),'raw_videos':{'source':{},'native':{},'forced':{}},'reference_image_used':False,'evaluation_scope':'official_source_full_extent','input_to_original_frame':list(range(120))}
 def test_actual_domain(self):prep.validate_manifest(self.sample())
 def test_padding_rejected(self):
  v=self.sample();v['evaluation_indices']=list(range(124))
  with self.assertRaises(AssertionError):prep.validate_manifest(v)
 def test_native_only_rejected(self):
  v=self.sample();del v['raw_videos']['forced']
  with self.assertRaises(AssertionError):prep.validate_manifest(v)
 def test_crop_changed_rejected(self):
  v=self.sample();v['crop_xywh']=[0,0,1312,736]
  with self.assertRaises(AssertionError):prep.validate_manifest(v)
 def test_wrong_source_rejected(self):
  v=self.sample();v['source_id']='long_0059'
  with self.assertRaises(AssertionError):prep.validate_manifest(v)
