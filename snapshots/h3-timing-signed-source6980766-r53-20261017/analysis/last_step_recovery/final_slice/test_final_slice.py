import ast,copy,json,os,unittest
from pathlib import Path
from unittest.mock import patch
import final_worker as w
import supervision as s
ROOT=Path(__file__).resolve().parent

class SliceTests(unittest.TestCase):
 def test_extracted_functions_exact(self):
  source=ROOT/'inputs/frozen_decode_live_child.py';tree=ast.parse(source.read_text());actual=ast.parse((ROOT/'frozen_decode.py').read_text())
  for node in actual.body:
   if isinstance(node,ast.FunctionDef):self.assertEqual(ast.dump(node,include_attributes=False),ast.dump(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==node.name),include_attributes=False))
 def test_actual_cpu_reference_update(self):
  import torch
  ctx=s.read_json(ROOT/'inputs/CONTEXT.json');proof=s.read_json(ROOT/'inputs/CPU_X14_REPLAY.json');x=torch.load(ROOT/'inputs/step014_input_raw.pt',weights_only=True,map_location='cpu')['packed'];p=torch.load(ROOT/'inputs/step014_full.pt',weights_only=True,map_location='cpu');grid=torch.tensor(ctx['original_request']['full_grid'],dtype=torch.float32)
  self.assertEqual(w.signature(w.update(x,w.pack(p),grid,14)),proof['rows'][0]['expected']);self.assertFalse(torch.cuda.is_initialized())
 def test_final_decision_is_actual_off(self):
  d=s.read_json(ROOT/'inputs/DECISION19.json');self.assertFalse(d['decision19']['chosen_full']);self.assertEqual(d['context_sha256'],s.sha(ROOT/'inputs/CONTEXT.json'));self.assertFalse(d['original_run_completed'])
 def test_actual_x19_load_and_final_cpu_update(self):
  import torch
  x=w.load_x19(ROOT/'inputs/x19_reconstructed_cpu.pt');ctx=s.read_json(ROOT/'inputs/CONTEXT.json');self.assertEqual(w.signature(x),ctx['Native019_branch']['same_input']);p=torch.load(ROOT/'inputs/step019_native.pt',map_location='cpu',weights_only=True);grid=torch.tensor(ctx['original_request']['full_grid'],dtype=torch.float32);result=w.update(x,w.pack(p),grid,19);self.assertEqual(tuple(result.shape),(1,1,3817216));self.assertTrue(bool(torch.isfinite(result).all()));self.assertFalse(torch.cuda.is_initialized())
 def test_missing_root_approval_rejected(self):
  with patch.object(w.s,'alive',return_value=True),self.assertRaisesRegex(ValueError,'root GPU'):w.admitted({'root_approved':False,'gpu_uuid':w.GPU}, {})
 def test_busy_gpu_rejected(self):
  with patch.object(w.s,'alive',return_value=True),patch.object(w.d,'assert_idle_gpu',side_effect=RuntimeError('busy')),self.assertRaisesRegex(RuntimeError,'busy'):w.admitted({'root_approved':True,'gpu_uuid':w.GPU}, {})
 def test_unregistered_owned_peer_rejected(self):
  with patch.object(w.s,'alive',return_value=True),patch.object(w.d,'assert_idle_gpu',return_value={}),patch.object(w.subprocess,'check_output',return_value='GPU-other, 5\n'),patch.object(w.s,'identity',return_value={'pid':5,'uid':os.getuid()}),self.assertRaisesRegex(ValueError,'unregistered'):w.admitted({'root_approved':True,'gpu_uuid':w.GPU,'permitted_peers':[]}, {})
 def test_own_child_release_allows_foreign_compute(self):
  from gpu_release_gate import wait_own_child_released
  child={'returncode':0,'process':{'pid':10,'uid':os.getuid(),'start_ticks':20,'cmdline_sha256':'a'}}
  result=wait_own_child_released('GPU-target',child,lambda pid:None,compute_pids=lambda:[22])
  self.assertTrue(result['original_generation_absent']);self.assertEqual(result['other_compute_pids'],[22])
  with self.assertRaisesRegex(RuntimeError,'generation remains'):
   wait_own_child_released('GPU-target',child,lambda pid:child['process'],compute_pids=lambda:[10])
if __name__=='__main__':unittest.main()
