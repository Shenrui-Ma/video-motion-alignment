import importlib.util,pathlib,unittest
from pose_test_support import measurement
R=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('r19_selector',R/'extensions/H3PoseObserverRouter/selector.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class SelectorTest(unittest.TestCase):
 def test_prefix(self):
  for n in range(10):self.assertEqual(m.select(n,None)['chosen_full'],6<=n<=9)
 def test_table_and_reentry(self):
  for values,reason in [([3]*4,'ON_LATE'),([2,-2,0,1],'OFF_ALIGNED'),([-3]*4,'OFF_ADVANCED'),([4,4,2,4],'UNKNOWN'),([None]*4,'UNKNOWN')]:
   for n in (10,19):self.assertEqual(m.select(n,measurement(values))['reason'],reason)
 def test_rejected_late_unknown(self):self.assertEqual(m.select(10,measurement([5]*4,['confounded']))['reason'],'UNKNOWN')
 def test_bad_response_aborts(self):
  for result in (None,{}, {'status':'failed'}, {'status':'complete'}):
   with self.assertRaises((ValueError,KeyError,TypeError)):m.select(10,result)
 def test_invalid_index(self):
  for n in (-1,20,10.,True):
   with self.assertRaises(ValueError):m.select(n,measurement([4]*4))
if __name__=='__main__':unittest.main()
