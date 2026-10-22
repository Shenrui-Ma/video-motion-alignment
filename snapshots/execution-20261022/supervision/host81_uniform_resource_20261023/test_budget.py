import unittest
from budget_admission import admit_before_context,admit_after_context
class Budget(unittest.TestCase):
 def test_threshold(self):self.assertTrue(admit_before_context(22500));self.assertFalse(admit_before_context(22499))
 def test_measured(self):self.assertTrue(admit_after_context(22008*2**20,22*2**20,int(19.5*2**30)))
 def test_context_growth_refused(self):self.assertFalse(admit_after_context(21400*2**20,22*2**20,int(19.5*2**30)))
 def test_no_double_count_reserved(self):self.assertFalse(admit_after_context(21000*2**20,300*2**20,int(19.5*2**30)))
 def test_exact_boundary(self):self.assertTrue(admit_after_context((19968+1536)*2**20,0,int(19.5*2**30)))
if __name__=='__main__':unittest.main()
