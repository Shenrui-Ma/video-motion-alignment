import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import cgroup_memory as c,capacity_trial as t
class Host9Tests(unittest.TestCase):
 def value(self):return {'uid':1016,'host_available_bytes':100*c.GIB,'ancestors':[{'path':'/user.slice','max_bytes':None,'current_bytes':200*c.GIB,'events':{'failcnt':0,'under_oom':0}}]}
 def test_unlimited_parent_and_host_headroom(self):
  v=self.value();self.assertTrue(c.assess(v,stage='entry')['passed']);v['host_available_bytes']=63*c.GIB;self.assertFalse(c.assess(v,stage='entry')['passed']);v['host_available_bytes']=40*c.GIB;self.assertFalse(c.assess(v,stage='running')['passed'])
 def test_finite_bounds_and_events(self):
  v=self.value();v['ancestors'][0]['max_bytes']=240*c.GIB;self.assertFalse(c.assess(v,stage='entry')['passed']);v=self.value();b=copy.deepcopy(v);v['ancestors'][0]['events']['failcnt']=1;self.assertFalse(c.assess(v,stage='running',baseline=b)['passed'])
 def test_uid_and_limit_change_rejected(self):
  v=self.value();v['uid']=1004
  with self.assertRaises(ValueError):c.assess(v,stage='entry')
  v=self.value();b=copy.deepcopy(v);v['ancestors'][0]['max_bytes']=300*c.GIB
  with self.assertRaises(ValueError):c.assess(v,stage='running',baseline=b)
 def test_reused_pid_and_other_uid_never_signalled(self):
  expected={'pid':123,'uid':1016,'start_ticks':1,'cmdline_sha256':'a'}
  for changed in [dict(expected,start_ticks=2),dict(expected,uid=1025),dict(expected,cmdline_sha256='b')]:
   self.assertFalse(t.signal_exact(expected,lookup=lambda pid:changed,uid=1016,pidfd_open=lambda *a:self.fail('opened replaced PID')))
  self.assertFalse(t.signal_exact(dict(expected,uid=1025),lookup=lambda pid:expected,uid=1016,pidfd_open=lambda *a:self.fail('opened other UID')))
if __name__=='__main__':unittest.main()
