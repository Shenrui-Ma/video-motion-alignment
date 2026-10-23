"""Independent synthetic CPU checks; no real input tensors or model weights."""
import copy, json, pathlib, sys, tempfile, unittest
from types import SimpleNamespace as NS
from unittest import mock
import torch
S=pathlib.Path(sys.argv[1]);sys.argv=sys.argv[:1];sys.path.insert(0,str(S))
import adapter, condition, identity, nodes
torch.set_num_threads(1)
C=json.loads((S/'native_contract.json').read_text())

def counters(value=0):
 return {'operations':{b+'.'+o:{n+'_calls':value for n in ('attempted','successful','failed')} for b in ('cuda','triton','eager') for o in ('int8_linear','w4a8_int8_linear')}}
class Independent(unittest.TestCase):
 def test_actual_counter_schema_and_missing_backend(self):
  a=counters();b=counters();b['operations']['triton.int8_linear'].update(attempted_calls=200,successful_calls=200)
  self.assertEqual(adapter.dispatch_delta(a,b)['triton.int8_linear']['successful'],200)
  for which in ('before','after'):
   aa,bb=copy.deepcopy(a),copy.deepcopy(b);(aa if which=='before' else bb)['operations'].pop('cuda.int8_linear')
   with self.assertRaises(ValueError):adapter.dispatch_delta(aa,bb)
  for key in ('attempted_calls','successful_calls','failed_calls'):
   bb=copy.deepcopy(b);bb['operations']['eager.int8_linear'].pop(key)
   with self.assertRaises(ValueError):adapter.dispatch_delta(a,bb)
 def test_backend_negative_or_noninteger_is_rejected(self):
  a=counters();b=counters();b['operations']['triton.int8_linear'].update(attempted_calls=200,successful_calls=200)
  for bad in (-1, .5, True):
   aa=copy.deepcopy(a);aa['operations']['cuda.int8_linear']['failed_calls']=bad
   with self.assertRaises(ValueError):adapter.dispatch_delta(aa,b)
 def test_reference_original_and_prepared_context_restored(self):
  z=torch.arange(32,dtype=torch.float32).reshape(1,1,32,1,1);refs=[dict(kind='video',latent=z)]
  payload=dict(refs=refs,cond_video_latents=[z],seed=2026101701,audio_scale=4)
  ctxt=torch.ones(2,3);g=NS(conds={'positive':[{'model_conds':{'minimax_payload':NS(cond=payload),'c_crossattn':NS(cond=ctxt)}}]})
  original=g.conds;sig=adapter.context_signature(g)
  with self.assertRaisesRegex(RuntimeError,'sentinel'):
   with condition.replaced_reference(g,True) as p:
    self.assertIs(p['refs'][0]['latent'],p['cond_video_latents'][0]);self.assertIsNot(p['refs'],refs)
    self.assertEqual(adapter.context_signature(g),sig)
    self.assertTrue(torch.equal(p['cond_video_latents'][0][:,:,5:10],z[:,:,10:15]))
    raise RuntimeError('sentinel')
  self.assertIs(g.conds,original);self.assertIs(payload['refs'],refs);self.assertIs(refs[0]['latent'],z)
  self.assertEqual(adapter.context_signature(g),sig)
 def test_all_captured_tensor_branches_are_required(self):
  a={k:torch.zeros(2,dtype=torch.float32) for k in adapter.QK_NAMES+adapter.TENSOR_METADATA}
  a.update({k:0 for k in adapter.VALUE_METADATA})
  for key in adapter.QK_NAMES+adapter.TENSOR_METADATA:
   b=copy.deepcopy(a);b[key][1]=torch.finfo(torch.float32).eps
   with self.assertRaises(ValueError):adapter.exact_capture(a,b)
  b=copy.deepcopy(a);b['actual_K_R'][1]=1
  self.assertTrue(adapter.exact_capture(a,b,include_qk=False))
 def test_schema_uses_actual_live_state_identity_key(self):
  z=torch.zeros(1,1,2908288,dtype=torch.float32);info=identity.tensor_info(z);qzero=torch.zeros(32,8,56,128,dtype=torch.bfloat16)
  with tempfile.TemporaryDirectory() as tmp:
   entries={};items={}
   for step in (9,19):
    sf=pathlib.Path(tmp)/('s'+str(step));qf=pathlib.Path(tmp)/('q'+str(step));sf.write_bytes(b's'+str(step).encode());qf.write_bytes(b'q'+str(step).encode())
    entries[str(step)]={'state':{'path':str(sf),'sha256':identity.file_sha(sf)},'qk':{'path':str(qf),'sha256':identity.file_sha(qf)}}
    st=dict(schema='h3-live-phase-state-v1',step_zero_based=step,target_shapes=C['target_shapes'],sample_sigmas_video=C['sigmas_video'],packed_x=z,raw_packed_x0=z)
    fi=dict(case=C['case'],method=C['method'],trajectory_id=C['trajectory_id'],step_zero_based=step,layer_zero_based=25,state_file_sha256=identity.file_sha(sf),science_contract_sha256=identity.file_sha(S/'native_contract.json'),sample_sigmas_video=C['sigmas_video'],noise_sha256=C['noise_tensor_sha256'],packed_x=info,raw_packed_x0=info)
    q=dict(schema='h3-passive-qk-capture-v1',step_zero_based=step,layer_zero_based=25,case=C['case'],method=C['method'],trajectory_id=C['trajectory_id'],forward_identity=fi,sample_sigmas_video=C['sigmas_video'])
    q.update({name:qzero for name in adapter.QK_NAMES});q.update(heads=56,head_dim=128,spatial_ids=[0,135,269,404,538,673,807,942],valid_bins=[True]*31+[False])
    items[str(sf)]=st;items[str(qf)]=q
   with mock.patch.object(identity.torch,'load',side_effect=lambda path,**kw:items[str(path)]):
    self.assertEqual(set(identity.load_live_inputs(entries,C)),{9,19})
    q=items[entries['9']['qk']['path']];q['forward_identity']['state_sha256']=q['forward_identity'].pop('state_file_sha256')
    with self.assertRaises((ValueError,KeyError)):identity.load_live_inputs(entries,C)
 def test_all_source_hashes_precede_decoding(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/'fake';p.write_bytes(b'notatensor')
   ent={str(t):{k:{'path':str(p),'sha256':identity.file_sha(p)} for k in ('state','qk')} for t in (9,19)}
   ent['19']['qk']['sha256']='0'*64
   with mock.patch.object(identity.torch,'load',side_effect=AssertionError('decoded')) as load:
    with self.assertRaises(ValueError):identity.load_live_inputs(ent,C)
    self.assertFalse(load.called)
 def test_production_rejects_combined_scope_before_ready_or_tensors(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/'release.json';identity.write_json(p,dict(schema='h3-content-coordinate-root-release-v1',scope='two_zero_then_two_swap',maximum_attempts=1,cohort='content_coordinate_calibration'))
   with mock.patch.object(nodes,'load_live_inputs',side_effect=AssertionError('decoded')) as loader:
    with self.assertRaisesRegex(ValueError,'bounded release'):nodes.preflight(str(p),identity.file_sha(p))
    self.assertFalse(loader.called)
 def test_outer_audio_error_leaves_failed_receipt(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/'GATE.json';identity.write_json(p,dict(status='forwards_complete',passed=False,outer_normalization_pending=True))
   raw=torch.ones(1,1,6);shapes=[[1,1,3],[1,1,3]]
   wrong=NS(is_nested=True,unbind=lambda:(torch.ones(1,1,3),torch.ones(1,1,3)))
   with self.assertRaises(ValueError):nodes.finalize_outer(tmp,wrong,raw,shapes)
   self.assertFalse(json.loads(p.read_text())['passed'])
if __name__=='__main__':unittest.main(verbosity=2)
