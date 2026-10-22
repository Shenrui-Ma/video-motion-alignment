import unittest,copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from capacity import assess,GIB,helper

def fixture():
 return dict(uid=1004,host_available_bytes=64*GIB,ancestors=[dict(path='/user.slice',current_bytes=96*GIB,high_bytes=100*GIB,max_bytes=112*GIB,stat=dict(file=40*GIB,shmem=4*GIB,active_file=20*GIB,inactive_file=16*GIB,file_mapped=8*GIB,file_dirty=2*GIB,file_writeback=1*GIB,anon=56*GIB),events=dict(oom=0,oom_kill=0),pressure=dict(some=dict(avg10=0),full=dict(avg10=0)))])
class Test(unittest.TestCase):
 def test_credit_formula(self):
  x=fixture();r=assess(x)['rows'][0];self.assertEqual(r['credit'],19*GIB);self.assertTrue(assess(x)['passed'])
 def test_input_unmodified(self):
  x=fixture();y=copy.deepcopy(x);assess(x);self.assertEqual(x,y)
 def test_unknown_stats_rejected(self):
  x=fixture();del x['ancestors'][0]['stat']['file_mapped']
  with self.assertRaises(ValueError):assess(x)
 def test_mapped_not_reclaimable(self):
  x=fixture();x['ancestors'][0]['stat']['file_mapped']=40*GIB;self.assertFalse(assess(x)['passed'])
 def test_shmem_not_reclaimable(self):
  x=fixture();x['ancestors'][0]['stat']['shmem']=40*GIB;self.assertFalse(assess(x)['passed'])
 def test_no_double_credit(self):
  x=fixture();x['ancestors'][0]['stat']['active_file']=0;x['ancestors'][0]['stat']['inactive_file']=8*GIB;self.assertFalse(assess(x)['passed'])
 def test_psi_entry(self):
  x=fixture();x['ancestors'][0]['pressure']['some']['avg10']=1.01;self.assertFalse(assess(x)['passed']);self.assertTrue(assess(x,'running')['passed'])
 def test_raw_hard_limit(self):
  x=fixture();x['ancestors'][0]['current_bytes']=105*GIB;self.assertFalse(assess(x)['passed']);self.assertFalse(assess(x,'running')['passed'])
 def test_exact_raw_boundary(self):
  x=fixture();x['ancestors'][0]['current_bytes']=104*GIB;self.assertTrue(assess(x)['passed']);self.assertTrue(assess(x,'running')['passed'])
 def test_host_floor(self):
  x=fixture();x['host_available_bytes']=31*GIB
  with self.assertRaises(AssertionError):assess(x)
 def test_limit_change(self):
  x=fixture();x['ancestors'][0]['max_bytes']=111*GIB
  with self.assertRaises(AssertionError):assess(x)
 def test_negative_counter(self):
  x=fixture();x['ancestors'][0]['events']['oom']=-1
  with self.assertRaises(AssertionError):assess(x)
if __name__=='__main__':unittest.main()
