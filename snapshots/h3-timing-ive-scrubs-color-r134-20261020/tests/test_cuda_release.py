import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import service

class Release(unittest.TestCase):
 def run_case(self,query,lookup=lambda p:None):
  tick=[0.0]
  def sleep(t):tick[0]+=t
  return service.wait_cuda_release({'pid':77,'identity':{'start_ticks':'1'}},seconds=1,clock=lambda:tick[0],sleep=sleep,query=query,lookup=lookup)
 def test_nvml_linger_then_release(self):
  rows=iter([[{'pid':77,'gpu_uuid':'our'}],[{'pid':88,'gpu_uuid':'foreign'}]])
  r=self.run_case(lambda:next(rows));self.assertEqual(r['polls'],2);self.assertTrue(r['own_compute_absent']);self.assertEqual(r['rows'][0]['pid'],88)
 def test_persistent_allocation_times_out(self):
  with self.assertRaisesRegex(TimeoutError,'bounded wait'):self.run_case(lambda:[{'pid':77}])
 def test_recycled_pid_refused(self):
  with self.assertRaisesRegex(RuntimeError,'generation changed'):self.run_case(lambda:[],lookup=lambda p:{'start_ticks':'2'})

if __name__=='__main__':unittest.main()
