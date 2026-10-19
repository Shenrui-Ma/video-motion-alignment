import math,unittest
from measure import stats
class Metrics(unittest.TestCase):
 def test_exact(self):
  r=stats(0,0,6,2,0,0,0);self.assertEqual(r['MAE_0_255'],0);self.assertTrue(r['PSNR_is_infinite']);self.assertIsNone(r['PSNR_dB'])
 def test_one_level(self):
  r=stats(6,6,6,2,6,2,1);self.assertEqual(r['MAE_0_255'],1);self.assertEqual(r['RMSE_0_255'],1);self.assertAlmostEqual(r['PSNR_dB'],20*math.log10(255));self.assertEqual(r['different_pixel_fraction_any_RGB'],1)
 def test_sparse_channels(self):
  r=stats(7,25,6,2,2,2,4);self.assertEqual(r['MAE_0_255'],7/6);self.assertEqual(r['different_channel_fraction'],1/3);self.assertEqual(r['different_pixel_fraction_any_RGB'],1);self.assertEqual(r['max_abs_0_255'],4)
if __name__=='__main__':unittest.main()
