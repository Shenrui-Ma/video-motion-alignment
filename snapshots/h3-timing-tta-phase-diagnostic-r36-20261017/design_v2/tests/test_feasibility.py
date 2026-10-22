import sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'design_v2'));sys.path.insert(0,str(ROOT/'scripts'))
from feasibility import support_bound,candidate_gate
from support_bound import identity_bound

class TestBound(unittest.TestCase):
 def test_candidate_not_replaced_by_secondary(self):
  a=candidate_gate({'reliable_lag_frames':8},{'reliable_lag_frames':6});self.assertEqual(a['candidate'],8);self.assertTrue(a['dual_identity_consistent'])
  b=candidate_gate({'reliable_lag_frames':None},{'reliable_lag_frames':4});self.assertIsNone(b['candidate']);self.assertFalse(b['dual_identity_consistent'])
 def test_disagreement_retained(self):
  a=candidate_gate({'reliable_lag_frames':8},{'reliable_lag_frames':4});self.assertEqual(a['candidate'],8);self.assertFalse(a['dual_identity_consistent'])
 def test_fixed_stencil_and_null_deduplication(self):
  s=np.ones((141,2,2));c=np.ones((141,2))
  for lag in (0,-2,2,-4,4,-8,8):
   a=support_bound(s,s,c,c,(50,65),lag,.3);self.assertEqual(a['lags'],sorted(set([lag,-2,-1,0,1,2])));self.assertEqual(a['coverage_upper_bound'],1)
 def test_all49_mask_subset_of_restricted(self):
  s=np.ones((141,2,2));c=np.ones((141,2));t=c.copy();t[30,0]=0
  a=support_bound(s,s,c,t,(50,65),8,.5);b=identity_bound(s,s,c,t,(50,65),.5)
  self.assertTrue((np.array(b['mask'])<=np.array(a['mask'])).all())
 def test_candidate_null_intersection_not_separate_support(self):
  s=np.ones((141,2,2));c=np.ones((141,2));t=c.copy();t[70,0]=0
  a=support_bound(s,s,c,t,(50,65),8,.5);self.assertFalse(a['mask'][12][0])
 def test_no_boundary_clamp(self):
  s=np.ones((141,2,2));c=np.ones((141,2));a=support_bound(s,s,c,c,(125,140),8,.3)
  self.assertEqual(a['valid_frames_upper_bound'],8);self.assertFalse(a['possibly_eligible'])
 def test_identity_scale_values_do_not_affect_support(self):
  s=np.ones((141,2,2));c=np.ones((141,2));self.assertEqual(support_bound(s,s,c,c,(50,65),4,.3),support_bound(s*100,s*-10,c,c,(50,65),4,.3))

if __name__=='__main__':unittest.main()
