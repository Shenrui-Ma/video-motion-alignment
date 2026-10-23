import unittest,copy
from extension_guard import check_schedule,may_append
class GuardTests(unittest.TestCase):
 def doc(self,weak=True):
  return dict(schema='h3-temporal-router-v1',completed_forward_calls=20,started_calls=1000,completed_calls=1000,native_override_calls=1000,calls_by_block=[20]*50,calls_by_forward=[50]*20,block_interval_half_open=[0,50],radius=0,time_offset=0,schedule='global_weak' if weak else 'native',mode='mass_preserve' if weak else 'native',routed_calls=1000 if weak else 0,alpha=.25,step_set_zero_based=list(range(20)) if weak else [],forward_summaries=[{'layer_stats':[{'finite':True}]*50}]*20 if weak else [])
 def test_native(self):check_schedule(self.doc(False),'native')
 def test_weak(self):check_schedule(self.doc(),'global_weak')
 def test_missing(self):
  d=self.doc();d['completed_calls']=999
  with self.assertRaises(AssertionError):check_schedule(d,'global_weak')
 def test_nan(self):
  d=self.doc();d['forward_summaries'][0]['layer_stats'][0]['finite']=False
  with self.assertRaises(AssertionError):check_schedule(d,'global_weak')
 def test_budget(self):
  d=self.doc();d['alpha']=.5
  with self.assertRaises(AssertionError):check_schedule(d,'global_weak')
 def test_boundary(self):
  s={'worker':{'state':'owned_alive'},'service':{'state':'exited'},'locks':{},'port_listening':False};self.assertFalse(may_append({'a':{'status':'completed'}},'a',s));s['worker']['state']='exited';self.assertTrue(may_append({'a':{'status':'completed'}},'a',s))
if __name__=='__main__':unittest.main()
