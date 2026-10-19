import copy,json,sys,unittest,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from common import *
class NativeScope(unittest.TestCase):
 def setUp(self):
  self.c=R/'cases/r96_long_0173';self.s=read(self.c/'SPEC.json');self.g=read(self.c/self.s['gate']['file'])
 def test_real_native_gate(self):validate_gate(self.s,self.g);self.assertEqual(set(self.g['runs']),{'native','forced'})
 def test_reject_pair(self):
  self.g['schema']='r96-native-runtime-gate-v1'
  with self.assertRaises(ValueError):validate_gate(self.s,self.g)
 def test_reject_failed_gate(self):
  self.g['checks']['native_sampled_finite']=False
  with self.assertRaises(ValueError):validate_gate(self.s,self.g)
 def test_reject_wrong_run(self):
  self.g['runs']['native']['run_id']='old_native'
  with self.assertRaises(ValueError):validate_gate(self.s,self.g)
 def test_reject_wrong_media(self):
  self.g['runs']['native']['video']['sha256']='0'*64
  with self.assertRaises(ValueError):validate_gate(self.s,self.g)
 def test_reject_wrong_time(self):
  self.g['runs']['native']['valid_frames']=158
  with self.assertRaises(ValueError):validate_gate(self.s,self.g)
 def test_prepared_domain(self):
  m=read(self.c/'INPUTS.json');self.assertEqual(m['valid_frames'],145);self.assertEqual(set(m['roles']),{'source','native','forced'});self.assertEqual(m['gate_sha256'],sha(self.c/'inputs/PAIR_RUNTIME_GATE.json'))
  for x in m['roles'].values():self.assertEqual(len(x['score_frame_md5']),145);self.assertEqual(x['score_sha256'],sha(self.c/x['score_file']))
 def test_pair_actual_counts_and_prefix(self):
  self.assertEqual(self.g['runs']['native']['routed_blocks'],0);self.assertEqual(self.g['runs']['forced']['routed_blocks'],450)
  prefix=self.g['prefix_tensor_comparison'];self.assertEqual([x['step_zero_based'] for x in prefix],list(range(6)));self.assertTrue(all(x[k] is True for x in prefix for k in ('video','audio')))
 def test_numerics_unchanged(self):verify_runtime()
 def test_wrapper_bounded_two_roles(self):
  import ast
  s=(R/'audit/run_authorized.py').read_text();ast.parse(s);self.assertIn("['source','native','forced']",s);self.assertIn('timeout=600',s);self.assertIn("if owner_check() is not None:peer_change",s)
class OwnerGuard(unittest.TestCase):
 def call(self,current,cuda):
  import ast,types
  tree=ast.parse((R/'audit/run_authorized.py').read_text());f=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='owner_check');m=ast.Module(body=[f],type_ignores=[])
  owner={'pid':951112,'identity':{'start_ticks':'10923395','uid':1004,'cmdline':'real'}}
  env={'PEER':Path('/unused'),'read':lambda x:owner,'require':require,'process_identity':types.SimpleNamespace(snapshot=lambda p:current,service_record=lambda x:x),'cuda_pids':lambda:cuda}
  exec(compile(m,'owner_guard','exec'),env);return env['owner_check']()
 def test_absent_parent(self):self.assertIsNone(self.call(None,set()))
 def test_absent_with_nvml_tail(self):
  with self.assertRaises(ValueError):self.call(None,{951112})
 def test_parent_reused(self):
  with self.assertRaises(ValueError):self.call({'start_ticks':'wrong','uid':1004,'cmdline':'real'},{951112})
 def test_live_exact_parent(self):self.assertEqual(self.call({'start_ticks':'10923395','uid':1004,'cmdline':'real'},{951112})['pid'],951112)
if __name__=='__main__':unittest.main()
