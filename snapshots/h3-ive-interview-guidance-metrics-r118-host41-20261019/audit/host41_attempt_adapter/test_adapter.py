import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('adapter',Path(__file__).with_name('consume_host41.py'));mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class AttemptTests(unittest.TestCase):
 def test_actual_host41(self):self.assertTrue(mod.valid_attempt('host41_interview_attempt1'))
 def test_existing_root(self):self.assertTrue(mod.valid_attempt('root_interview_attempt1'))
 def test_unknown_host41(self):self.assertFalse(mod.valid_attempt('host41_other_attempt'))
 def test_traversal(self):self.assertFalse(mod.valid_attempt('root_../../tmp'))
 def test_injection(self):self.assertFalse(mod.valid_attempt('root_x;touch /tmp/x'))
 def test_empty(self):self.assertFalse(mod.valid_attempt(''))
 def test_nonstring(self):self.assertFalse(mod.valid_attempt(None))
 def test_original_freeze(self):self.assertTrue(mod.verify_static())
if __name__=='__main__':unittest.main()
