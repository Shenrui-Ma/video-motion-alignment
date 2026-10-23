import unittest,json,copy
from check_science import check,D
class Science(unittest.TestCase):
 def setUp(self):self.g=json.loads((D/'graph.json').read_text());self.j=json.loads((D/'jobs.json').read_text())
 def test_frozen(self):self.assertTrue(check(self.g,self.j))
 def test_prompt_drift(self):self.g['5']['inputs']['manifest_path']='wrong';self.assertRaises(AssertionError,check,self.g,self.j)
 def test_old_prefix(self):self.j['jobs'][0]['expected_output_prefix']='live_phase_old/';self.assertRaises(AssertionError,check,self.g,self.j)
 def test_old_owner(self):self.j['jobs'][0]['metadata']['actual_producer']='host81_live_phase_pair';self.assertRaises(AssertionError,check,self.g,self.j)
 def test_strength_drift(self):self.g['50']['inputs']['alpha_max']=.6;self.assertRaises(AssertionError,check,self.g,self.j)
 def test_old_writer(self):self.g['52']['inputs']['output_dir']='/old/audit';self.assertRaises(AssertionError,check,self.g,self.j)
 def test_retries(self):self.j['jobs'][0]['max_attempts']=2;self.assertRaises(AssertionError,check,self.g,self.j)
if __name__=='__main__':unittest.main()
