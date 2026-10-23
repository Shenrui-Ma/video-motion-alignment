import copy,unittest
import guard_logic as guard
class GuardTests(unittest.TestCase):
 def audit(self):return {'status':'complete','completed_forwards':20,'completed_blocks':1000,'compensated_calls':1000,'delta_resolved':True,'delta_mode':'reference_origin','delta_derivation':{'runtime':True},'rotation':{'frequency_mask':[0]*8+[1]*8,'selected_pair_indices':list(range(8,16)),'delta_physical_frames':-107},'forward_summaries':[{'layers':[{'finite':True,'correction_rms':1.}]*50}]*20}
 def test_wait_and_success(self):
  self.assertFalse(guard.preceding_status({'a':{'status':'submitted'}},['a']))
  self.assertTrue(guard.preceding_status({'a':{'status':'completed'}},['a']))
 def test_failed_stops(self):
  with self.assertRaises(RuntimeError):guard.preceding_status({'a':{'status':'failed'}},['a'])
 def test_valid_audit(self):self.assertEqual(guard.verify_partial_audit(self.audit())['status'],'passed')
 def test_no_compensation_rejected(self):
  a=self.audit();a['compensated_calls']=0
  with self.assertRaises(AssertionError):guard.verify_partial_audit(a)
 def test_wrong_band_rejected(self):
  a=self.audit();a['rotation']['frequency_mask']=[1]*16
  with self.assertRaises(AssertionError):guard.verify_partial_audit(a)
 def test_nonfinite_rejected(self):
  a=self.audit();a['forward_summaries'][0]['layers'][0]['correction_rms']=float('nan')
  with self.assertRaises(AssertionError):guard.verify_partial_audit(a)
if __name__=='__main__':unittest.main()
