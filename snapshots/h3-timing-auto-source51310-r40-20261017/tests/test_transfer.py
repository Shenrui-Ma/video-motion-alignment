import copy,json,hashlib,sys,tempfile,unittest
from pathlib import Path
import torch
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'scripts'),str(R/'extensions')]
from H3AutomaticWindowRouter.pair_gate import compare_embedding_tensors,HistoricalPairGate
from H3AutomaticWindowRouter.dependencies import readout
from prelaunch_gates import check_layout_case,check

class TransferTests(unittest.TestCase):
 def test_embedding_exact_and_corrupt(self):
  x=torch.arange(80,dtype=torch.float32).reshape(1,10,8);s=readout.tensor_signature(x);s.pop('bytes')
  compare_embedding_tensors(x,x.clone(),s)
  for changed in (x+1,x.double(),x.reshape(1,8,10)):
   with self.assertRaises(ValueError):compare_embedding_tensors(changed,x,s)
  with self.assertRaises(ValueError):compare_embedding_tensors(x,x+1,s)
 def test_dense_prefix_and_first_on_keeps_current(self):
  cap=json.loads((R/'configs/parent_captures.json').read_text())
  self.assertEqual([v['step_zero_based'] for v in cap['captures']],list(range(20)))
  self.assertEqual(cap['seed'],2026101701)
  gate=HistoricalPairGate();s=type('State',(),{'audit':{'counterfactual':{}}})()
  gate.decision(s,1,{'chosen_full':True});self.assertTrue(gate.native_comparable(1));self.assertFalse(gate.native_comparable(2))
  gate.decision(s,3,{'chosen_full':False});self.assertFalse(gate.native_comparable(4))
 def test_actual_layout_boundary_gate(self):
  c=json.loads((R/'configs/parent_conditioning.json').read_text())
  a={'actual_shape':True,'shape':[1,56,87361,128],'plan':{'seq_len':87361,'frame_rows':943,'latent_interval_half_open':[0,42],'query_interval_half_open':[47755,87361],'reference_video_segment':[7679,47285]},'passed':True,'checks':{'fixture':True}}
  check_layout_case({'cases':[a]},c)
  for field,value in [('seq_len',87592),('reference_video_segment',[7910,47516]),('query_interval_half_open',[47986,87592])]:
   bad=copy.deepcopy(a);bad['plan'][field]=value
   with self.assertRaises(ValueError):check_layout_case({'cases':[bad]},c)
 def test_inherited_numerical_hashes(self):
  spec=json.loads((R/'configs/r27_inheritance.json').read_text())
  self.assertGreaterEqual(len(spec['exact_numerical_files']),15)
  for name,digest in spec['exact_numerical_files'].items():self.assertEqual(hashlib.sha256((R/name).read_bytes()).hexdigest(),digest,name)
  self.assertFalse(spec['offline_final_candidates_used_online'])
 def test_service_only_continuation_generation(self):
  from start_controller import admit
  owner={'pid':12,'identity':{'start_ticks':'abc'}}
  admit(12,'abc',owner)
  for args in ((13,'abc',owner),(12,'old',owner),(12,'abc',owner,{'pid':1})):
   with self.assertRaises(ValueError):admit(*args)
 def test_actual_parent_metadata_and_source_mapping(self):
  from parent_binding import check
  result=check(R,remote=False);self.assertEqual(result['available_native_indices'],list(range(20)))
 def test_two_controller_starts_compete_for_one_lock(self):
  from start_controller import controller_start_lock
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'processes').mkdir()
   with controller_start_lock(root):
    with self.assertRaises(BlockingIOError):
     with controller_start_lock(root):self.fail('second controller start acquired lock')
   with controller_start_lock(root):pass
 def test_real_gpu_evidence_still_required(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'configs').mkdir();(root/'configs/protocol.json').write_text('{}')
   with self.assertRaises(FileNotFoundError):check(root)

if __name__=='__main__':unittest.main()
