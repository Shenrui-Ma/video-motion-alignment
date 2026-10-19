import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from gpu_release_gate import wait_after_child
class Tests(unittest.TestCase):
 def call(self,assertion,pids=lambda:[],lookup=lambda pid:None):
  now=[0.0]
  return wait_after_child('GPU-fixture',{'returncode':0,'process':{'pid':123}},assertion,lookup,clock=lambda:now[0],sleep=lambda n:now.__setitem__(0,now[0]+n),compute_pids=pids)
 def test_utilization_tail_then_original_strict_pass(self):
  count=[0]
  def check(uuid):
   count[0]+=1
   if count[0]<4:raise RuntimeError('GPU is not idle; refusing offline decode')
   return {'uuid':uuid,'memory_used_mib':4,'utilization_percent':0}
  result=self.call(check);self.assertEqual(len(result['attempts']),3);self.assertEqual(result['wait_seconds'],.75);self.assertTrue(result['strict_original_idle_assertion_passed'])
 def test_foreign_immediate_refusal(self):
  with self.assertRaisesRegex(RuntimeError,'foreign'):self.call(lambda u:self.fail('idle must not be queried'),lambda:[999])
 def test_live_or_reused_child_refusal(self):
  with self.assertRaisesRegex(RuntimeError,'still live or reused'):self.call(lambda u:self.fail('idle must not be queried'),lookup=lambda pid:{'pid':pid})
 def test_strict_timeout_and_unrelated_error(self):
  def fail(u):raise RuntimeError('GPU is not idle; refusing offline decode')
  with self.assertRaises(TimeoutError):self.call(fail)
  def schema(u):raise RuntimeError('GPU UUID did not resolve exactly')
  with self.assertRaisesRegex(RuntimeError,'UUID'):self.call(schema)
if __name__=='__main__':unittest.main()
