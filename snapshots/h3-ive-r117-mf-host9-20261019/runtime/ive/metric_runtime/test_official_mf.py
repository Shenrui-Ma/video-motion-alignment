import unittest,math,copy
import numpy as np
import torch
from ive_mf_adapter import official_class,validate_time_view,validate_full_view,validate_source_provenance,SELECTION_SHA

class OfficialMFTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.metric=official_class().__new__(official_class())
 def test_identical_dynamic_tracks_score_one(self):
  tr=torch.tensor([[[[0.,0.]],[[1.,2.]],[[3.,1.]],[[1.,4.]],[[5.,2.]],[[7.,8.]]]])
  vis=torch.ones(1,6,1)
  self.assertAlmostEqual(self.metric._compute_similarity_from_tracks(tr,vis,tr.clone(),vis.clone()),1)
 def test_static_identical_can_get_one(self):
  tr=torch.zeros(1,6,1,2);vis=torch.ones(1,6,1)
  self.assertEqual(self.metric._compute_similarity_from_tracks(tr,vis,tr,vis),1)
 def test_no_visible_tracks_is_zero(self):
  tr=torch.zeros(1,6,1,2);vis=torch.zeros(1,6,1)
  self.assertEqual(self.metric._compute_similarity_from_tracks(tr,vis,tr,vis),0)
 def test_visibility_interpolation_compresses_original_gap(self):
  tr=np.array([[0.,0.],[1.,0.],[2.,0.],[3.,0.],[4.,0.]])
  out,vis=self.metric.interpolate_track(tr,np.array([1.,1.,0.,0.,1.]),5)
  np.testing.assert_allclose(out[:,0],[0.,.5,1.,2.5,4.])
  np.testing.assert_allclose(vis,1.)
  self.assertNotEqual(out[2,0],tr[2,0])
 def test_same_time_shape_deviation_lowers_score(self):
  a=np.array([[0.,0.],[1.,0.],[2.,1.],[3.,0.],[4.,2.]])
  b=a.copy();b[2]+=[2.,3.]
  score=self.metric.compute_frame_by_frame_similarity(a,b,np.ones(5),np.ones(5))
  self.assertGreater(score,0);self.assertLess(score,1)
 def test_timebase_rejects_shift_padding_nonfinite(self):
  ok={'width':1280,'height':720,'count':5,'pts_s':[i/24 for i in range(5)]}
  validate_time_view(ok,5)
  for pts in [[.01+i/24 for i in range(5)],[0,1/24,float('nan'),3/24,4/24],[0,1/24,2/24,3/24,float('inf')]]:
   with self.assertRaises(ValueError):validate_time_view(dict(ok,pts_s=pts),5)
  with self.assertRaises(ValueError):validate_time_view(dict(ok,count=90),5)
 def test_actual_input_provenance_rejects_changed_map_or_pixels(self):
  mapping=list(range(5))+[4]*85
  expected={'pair_id':'fixture','edit_prompt':'Change clothes','source':{'sha256':'original','frame_count':5},'input_protocol':{'effective_frame_count':5,'input_to_original_frame':mapping}}
  record={'schema':'r54-ivebench-input-v1','pair_id':'fixture','selection_sha256':SELECTION_SHA,'source_sha256':'original','video_sha256':'prepared','geometry':[1312,736],'content_rectangle_xywh':[16,8,1280,720],'frames':90,'fps':24,'effective_frame_count':5,'evaluate_indices':list(range(5)),'input_to_original_frame':mapping,'padding_indices':list(range(5,90)),'decoded_pixel_mapping_exact':True,'prompt':'Change clothes','reference_images':[],'original_transformed_frame_md5':[str(i) for i in range(5)],'input_frame_md5':[str(i) for i in mapping]}
  actual=record['input_frame_md5']
  validate_source_provenance(record,expected,'prepared',actual)
  for key,value in [('video_sha256','other'),('input_to_original_frame',[0]*90),('prompt','Other task')]:
   changed=copy.deepcopy(record);changed[key]=value
   with self.assertRaises(ValueError):validate_source_provenance(changed,expected,'prepared',actual)
  with self.assertRaises(ValueError):validate_source_provenance(record,expected,'prepared',['changed']+actual[1:])
  validate_full_view({'width':1312,'height':736,'count':90,'pts_s':[i/24 for i in range(90)]})
  with self.assertRaises(ValueError):validate_full_view({'width':1312,'height':736,'count':90,'pts_s':[float('nan')]*90})

if __name__=='__main__':
 torch.set_num_threads(1)
 unittest.main()
