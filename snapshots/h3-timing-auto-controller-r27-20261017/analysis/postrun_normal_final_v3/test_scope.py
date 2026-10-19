import copy,json,tempfile,unittest
from pathlib import Path
from common import *
class ScopeTests(unittest.TestCase):
 def test_honest_scope(self):self.assertTrue(check_scope(scope_fields()))
 def test_rgb_not_relabelled(self):
  for key,value in [('all_OFF_141RGB_equal',True),('original_outcome_gate_passed',True),('pixel_difference_origin','encoder'),('new_model_invocations',1),('final_AV_latent_exact',False)]:
   d=scope_fields();d[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):check_scope(d)
 def test_bool_not_integer(self):
  d=scope_fields();d['all_OFF_141RGB_equal']=0
  with self.assertRaises(ValueError):check_scope(d)
 def test_missing_scope(self):
  d=scope_fields();del d['original_outcome_gate_passed']
  with self.assertRaises(ValueError):check_scope(d)
 def test_partial_exact(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'a').write_bytes(b'preserved');e={'a':{'bytes':9,'sha256':sha(p/'a')}};checked_partial(p,e)
   (p/'extra').write_bytes(b'x')
   with self.assertRaises(ValueError):checked_partial(p,e)
   (p/'extra').unlink();(p/'a').write_bytes(b'changed!!')
   with self.assertRaises(ValueError):checked_partial(p,e)
 def test_no_overwrite(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'result';save_new(p,{'failed':True})
   with self.assertRaises(FileExistsError):save_new(p,{'failed':False})
   self.assertTrue(read(p)['failed'])
 def test_real_frozen_evidence(self):
  p=read(HERE/'PROTOCOL.json');e=read(HERE/'INPUT_EVIDENCE.json');r=read(HERE/'RESULTS.json')
  self.assertEqual(len(p['partial_files']),23);self.assertEqual(p['partial_files'],e['partial_inventory']);self.assertFalse(r['RGB_equality']);self.assertTrue(e['runtime_gate']['cases'][0]['all_OFF_final_exact']);self.assertEqual(e['runtime_gate']['cases'][0]['mask'],[])
 def test_no_numerical_entrypoints(self):
  import ast
  s=ast.parse((HERE/'remote_finalize.py').read_text());calls={n.func.attr for n in ast.walk(s) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
  self.assertFalse(calls&{'evaluate','observe','runtime_imports','VideoCapture','run'})
if __name__=='__main__':unittest.main()
