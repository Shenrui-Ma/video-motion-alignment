import copy,unittest
from bind_parent import *
class AdapterTests(unittest.TestCase):
 def records(self):
  return dict(EXPECTED,passed=True,completion_status='complete_with_original_RGB_gate_failed',recovery_protocol_sha256='p'),dict(EXPECTED),{'parent_recovery_protocol_sha256':'p'}
 def test_explicit_limited_scope(self):self.assertEqual(check_scope(*self.records()),EXPECTED)
 def test_rgb_false_not_hidden(self):
  for key,v in [('all_OFF_141RGB_equal',True),('original_outcome_gate_passed',True),('final_AV_latent_exact',False),('pixel_difference_origin','encoding')]:
   d,s,p=self.records();d[key]=v
   with self.subTest(key=key),self.assertRaises(ValueError):check_scope(d,s,p)
 def test_summary_must_agree(self):
  d,s,p=self.records();s['all_OFF_141RGB_equal']=True
  with self.assertRaises(ValueError):check_scope(d,s,p)
 def test_bool_strict(self):
  d,s,p=self.records();s['all_OFF_141RGB_equal']=0
  with self.assertRaises(ValueError):check_scope(d,s,p)
 def test_recovery_protocol_bound(self):
  d,s,p=self.records();d['recovery_protocol_sha256']='other'
  with self.assertRaises(ValueError):check_scope(d,s,p)
if __name__=='__main__':unittest.main()
