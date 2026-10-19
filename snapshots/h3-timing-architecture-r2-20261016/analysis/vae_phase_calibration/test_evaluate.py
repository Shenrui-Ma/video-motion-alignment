import unittest
import numpy as np
from evaluate import signal,phase_mean,scan,geometry
LIMITS={'min_per_frame_rms':1e-6,'required_valid_coverage':1.,'separated_competitor_frames':4,'max_ambiguous_margin':1e-6}
class TestCalibration(unittest.TestCase):
 def test_geometry(self):
  c=geometry();self.assertEqual(len(c),42);self.assertEqual(c[-1],138.5);np.testing.assert_array_equal(c[5:]-c[:-5],17)
 def test_time_center_invariance(self):
  z=np.random.default_rng(1).normal(size=(42,7));before=z.copy()
  np.testing.assert_allclose(signal(z,'raw_adjacent')[1],signal(z,'whole_time_centering')[1],atol=1e-14)
  np.testing.assert_array_equal(z,before)
 def test_periodic_constant_removed(self):
  template=np.random.default_rng(2).normal(size=(5,7));z=template[np.arange(42)%5]
  self.assertGreater(np.linalg.norm(signal(z,'raw_adjacent')[1]),0)
  for m in ['phase_mean_centering','constant0_template','same_phase_gap5']:
   a=signal(z,m,phase_mean(z));self.assertLess(np.abs(a[1]).max(),1e-14);self.assertFalse(scan(a,a,[50,65],LIMITS)['accepted'])
 def test_template_additive_recovery(self):
  rng=np.random.default_rng(3);motion=rng.normal(size=(42,7));bias=rng.normal(size=(5,7));z=motion+bias[np.arange(42)%5]
  np.testing.assert_allclose(signal(z,'constant0_template',bias)[1],signal(motion,'raw_adjacent')[1],atol=1e-14)
 def test_signed_shift(self):
  times=np.arange(160,dtype=float);rng=np.random.default_rng(4);v=rng.normal(size=(160,7));shifted=v[np.maximum(0,np.arange(160)-8)]
  r=scan((times,v),(times,shifted),[50,65],LIMITS);self.assertTrue(r['accepted']);self.assertEqual(r['best']['lag_frames'],8)
 def test_periodic_ambiguity(self):
  times=np.arange(160,dtype=float);v=np.random.default_rng(5).normal(size=(17,7))[np.arange(160)%17];r=scan((times,v),(times,v),[50,65],LIMITS)
  self.assertFalse(r['accepted']);self.assertIn('ambiguous_separated_lag',r['rejection_reasons'])
 def test_endpoint_clamp(self):
  times=np.arange(10,dtype=float);v=np.random.default_rng(6).normal(size=(10,7));r=scan((times,v),(times,v),[6,12],LIMITS)
  self.assertFalse(r['accepted']);self.assertIn('winner_endpoint_clamp',r['rejection_reasons'])
if __name__=='__main__':unittest.main()
