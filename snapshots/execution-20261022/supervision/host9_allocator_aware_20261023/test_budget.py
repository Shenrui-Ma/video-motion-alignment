import unittest,types
from allocator_memory_budget import bounded_free,patch
class Tests(unittest.TestCase):
 def test_limit_after_other_exit(self):self.assertEqual(bounded_free(50,2,10,18),(8,2))
 def test_physical_pressure(self):self.assertEqual(bounded_free(3,1,10,18),(3,1))
 def test_exhaustion(self):self.assertEqual(bounded_free(50,2,19,18),(0,0))
 def test_cache_is_not_extra_cap(self):self.assertEqual(bounded_free(50,8,14,18),(4,4))
 def test_wrapper(self):
  dev=types.SimpleNamespace(type='cuda',index=0)
  m=types.SimpleNamespace(get_free_memory=lambda d,t:(50,2) if t else 50,get_torch_device=lambda:dev)
  torch=types.SimpleNamespace(cuda=types.SimpleNamespace(memory_stats=lambda d:{'active_bytes.all.current':10},current_device=lambda:0))
  patch(m,torch,18);self.assertEqual(m.get_free_memory(),8);self.assertEqual(m.get_free_memory(dev,True),(8,2));self.assertEqual(m.get_free_memory(types.SimpleNamespace(type='cpu',index=None)),50);self.assertEqual(m.get_free_memory(types.SimpleNamespace(type='cuda',index=1)),50)
  patch(m,torch,18)
  with self.assertRaises(RuntimeError):patch(m,torch,17)
if __name__=='__main__':unittest.main()
