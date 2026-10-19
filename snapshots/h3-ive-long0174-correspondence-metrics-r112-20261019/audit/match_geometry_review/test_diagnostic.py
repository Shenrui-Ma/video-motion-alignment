import unittest
import numpy as np
from diagnostic import *
G={'content_wh':[96,80],'input_wh':[128,96],'pad_xy':[16,8],'grid_hw':[3,4],'patch_size':32}
class DiagnosticTests(unittest.TestCase):
 def bank(self):return np.tile(np.arange(12),(1,1))
 def evaluate(self,a,b,forward=None,backward=None,visibility=None):
  t=np.array([[a],[b]],dtype=float);v=np.ones((2,1),dtype=bool) if visibility is None else visibility
  f=self.bank() if forward is None else forward;bk=self.bank() if backward is None else backward
  return evaluate_bank(t,v,f,bk,[0,1],0,geometry=G)
 def test_identity_mapping_preserves_point_offset(self):
  rows=self.evaluate([17.3,20.2],[17.3,20.2]);self.assertTrue(np.allclose(rows['error_px'],0));self.assertEqual(summarize(rows)['PCK_threshold_pixels']['16']['PCK_matched'],1.)
 def test_known_translation_forward_and_backward(self):
  f=self.bank();b=self.bank();f[0,1]=2;b[0,2]=1
  rows=self.evaluate([20,20],[52,20],f,b);self.assertTrue(np.allclose(rows['error_px'],0));self.assertTrue(np.allclose(rows['identity_error_px'],32))
  s=summarize(rows)['PCK_threshold_pixels']['16'];self.assertEqual(s['PCK_matched'],1.);self.assertEqual(s['PCK_identity_same_matched_points'],0.)
 def test_crop_offset_selects_correct_patch(self):
  self.assertEqual(point_cell([17,20],G),1);self.assertTrue(np.allclose(transport([17,20],1,2,G),[49,20]))
  self.assertEqual(point_cell([0,0],G),0);self.assertEqual(point_cell([95.9,79.9],G),11)
 def test_unmatched_retained_in_coverage_denominator(self):
  f=np.full((1,12),-1);rows=self.evaluate([20,20],[20,20],f,f);s=summarize(rows)
  self.assertEqual(s['candidate_count'],2);self.assertEqual(s['matched_count'],0);self.assertEqual(s['eligible_visible_in_content'],2)
  self.assertEqual(s['matched_coverage'],0);self.assertIsNone(s['PCK_threshold_pixels']['16']['PCK_matched']);self.assertEqual(s['PCK_threshold_pixels']['16']['matched_correct_over_all_eligible'],0)
 def test_visibility_missing_is_unknown(self):
  rows=self.evaluate([20,20],[20,20],visibility=np.array([[True],[False]]));s=summarize(rows)
  self.assertEqual(s['status_counts']['UNKNOWN_VISIBILITY'],2);self.assertEqual(s['eligible_visible_in_content'],0);self.assertIsNone(s['PCK_threshold_pixels']['16']['PCK_matched'])
 def test_outside_content_is_unknown(self):
  rows=self.evaluate([-1,20],[20,20]);self.assertEqual(summarize(rows)['status_counts']['UNKNOWN_OUTSIDE_CONTENT'],2)
 def test_wrong_match_retained_in_pck(self):
  f=self.bank();f[0,1]=11;rows=self.evaluate([20,20],[20,20],f,self.bank());s=summarize(rows)
  self.assertEqual(s['matched_count'],2);self.assertEqual(s['PCK_threshold_pixels']['16']['PCK_matched'],.5)
  self.assertGreater(rows['error_px'][0],64)
 def test_predicted_outside_content_is_still_wrong_match(self):
  f=self.bank();f[0,1]=3;rows=self.evaluate([20,20],[20,20],f,self.bank())
  self.assertEqual(rows['status'][0],STATUS['MATCHED']);self.assertGreater(rows['predicted_x'][0],80);self.assertGreater(rows['error_px'][0],32)
 def test_unknown_nonfinite_kept(self):
  rows=self.evaluate([float('nan'),20],[20,20]);self.assertEqual(summarize(rows)['status_counts']['UNKNOWN_NONFINITE'],2)
 def test_bad_index_rejected(self):
  f=self.bank();f[0,1]=12
  with self.assertRaises(ValueError):self.evaluate([20,20],[20,20],f,self.bank())
 def test_physical_frame_positions(self):
  self.assertEqual([i for a,b in spans() for i in range(a,b+1)],list(range(145)))
  self.assertEqual(representative_frames()[:6],[0,2,6,10,14,17]);self.assertEqual(representative_frames()[-1],142)
 def test_regions_missing_do_not_invent_foreground(self):
  rows=self.evaluate([20,20],[20,20]);self.assertEqual(grouped(rows)['foreground']['status'],'UNDEFINED_NO_SOURCE_ONLY_REGIONS')
 def test_source_region_selection_uses_source_time(self):
  reg={'frames':{'0':[[10,10,30,30]]}};self.assertEqual(region_membership([20,20],0,reg),1);self.assertEqual(region_membership([40,20],0,reg),0);self.assertEqual(region_membership([20,20],1,reg),-1)
 def test_fixed_source_ids_keep_membership_across_motion(self):
  reg={'schema':'source-only-manual-track-ids-v1','track_ids':[2,3]}
  self.assertEqual(region_membership([20,20],0,reg,2),1);self.assertEqual(region_membership([90,70],144,reg,2),1)
  self.assertEqual(region_membership([20,20],0,reg,4),0)
 def test_fixed_ids_reject_changed_track_binding(self):
  binding={'source_full':{'sha256':'s'},'source_tracks':{'sha256':'t'}}
  reg={'schema':'source-only-manual-track-ids-v1','track_ids':[2,3],'source_full_sha256':'s','source_tracks_sha256':'t',
       'source_frame':0,'defined_from_source_only':True,'annotator':'source-only-test','annotation_note':'initial subject interior'}
  validate_regions(reg,binding);reg['source_tracks_sha256']='different'
  with self.assertRaises(ValueError):validate_regions(reg,binding)
if __name__=='__main__':unittest.main()
