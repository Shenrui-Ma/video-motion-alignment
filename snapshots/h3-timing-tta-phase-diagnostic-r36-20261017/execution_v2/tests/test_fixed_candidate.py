import sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from fixed_candidate import common_costs,decisions,candidate_family
from test_math import motion


def proposal(d,h=None):return {'candidate':d,'secondary_identity_lag':d if h is None else h,'dual_identity_consistent':True}
def fixture():
 lags=[-2,-1,0,1,2,4];c=np.full((3,3,6),.2);c[:,:,-1]=.15
 return {'status':'measured','candidate_lag':4,'lags':lags,'costs':c.tolist()}

class TestFixedCandidate(unittest.TestCase):
 def test_known0plusminus2_4_8_both_thresholds(self):
  for d in (0,-2,2,-4,4,-8,8):
   for conf in (.3,.5):
    s,t,sc,tc=motion(d);v=common_costs(s,t,sc,tc,(50,65),conf,d);out=decisions(v,proposal(d))
    self.assertEqual(out['candidate_lag'],d);self.assertEqual(out['arms']['E']['status'],'ON' if d>=4 else 'ALIGNED' if abs(d)<=2 else 'ADVANCED')
 def test_one_fixed_candidate_cannot_be_optimized_by_a_view(self):
  f=fixture();a=np.asarray(f['costs']);a[0,0,2]=.1;f['costs']=a.tolist();d=decisions(f,proposal(4));self.assertEqual(d['candidate_lag'],4);self.assertEqual(d['arms']['E']['status'],'UNKNOWN')
 def test_threshold_relaxation_separate_from_averaging(self):
  d=decisions(fixture(),proposal(4));self.assertEqual(d['arms']['A']['status'],'NO_ON');self.assertEqual(d['arms']['B']['status'],'NO_ON')
  for a in 'CDE':self.assertEqual(d['arms'][a]['status'],'ON')
 def test_stable_wrong_pose_can_pass_no_accuracy_claim(self):
  # Finite-view consistency can be uniformly positive without independent truth.
  f=fixture();c=np.asarray(f['costs']);c[:,:,:5]=.2;c[:,:,-1]=.199;f['costs']=c.tolist();self.assertEqual(decisions(f,proposal(4))['arms']['E']['status'],'ON')
 def test_one_negative_view_blocks_envelope_but_not_mean(self):
  f=fixture();c=np.asarray(f['costs']);c[2,2,:5]=.14;f['costs']=c.tolist();d=decisions(f,proposal(4));self.assertEqual(d['arms']['D']['status'],'ON');self.assertEqual(d['arms']['E']['status'],'UNKNOWN')
 def test_confidence_families_not_silently_mixed(self):
  self.assertTrue(candidate_family(proposal(4,2)).startswith('UNKNOWN'));self.assertTrue(candidate_family(proposal(3)).startswith('UNKNOWN'))
 def test_no_candidate_reliability_rescue(self):
  p=proposal(4);p['dual_identity_consistent']=False;d=decisions(fixture(),p);self.assertTrue(all(x['status']=='UNKNOWN' for x in d['arms'].values()))
 def test_one_shared_mask_and_weights_every_lag_view(self):
  s,t,sc,tc=motion(4);tc[2,54,0]=.4;v=common_costs(s,t,sc,tc,(50,65),.5,4)
  self.assertFalse(v['common_mask'][0][0]);self.assertEqual(v['common_weights'][0][0],0)
 def test_boundary_and_nonfinite_rejected(self):
  s,t,sc,tc=motion(4)
  with self.assertRaises(ValueError):common_costs(s,t,sc,tc,(50,65),.3,24)
  tc[2,60,0]=np.inf
  with self.assertRaises(ValueError):common_costs(s,t,sc,tc,(50,65),.3,4)
 def test_null_cost_tie_unknown_envelope(self):
  f=fixture();c=np.asarray(f['costs']);c[:,:,2]=.15;f['costs']=c.tolist();self.assertEqual(decisions(f,proposal(4))['arms']['E']['status'],'UNKNOWN')

if __name__=='__main__':unittest.main()
