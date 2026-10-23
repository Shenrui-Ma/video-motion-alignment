import copy,importlib.util,json,pathlib,sys,tempfile,unittest
from unittest import mock
import numpy as np
S=pathlib.Path(sys.argv[1]);sys.argv=sys.argv[:1];sys.path.insert(0,str(S))
import core,provenance
POLICY=json.loads((S/'POLICY.json').read_text())
class Independent(unittest.TestCase):
 def tiny_z(self):return np.arange(1*2*32*4*6,dtype=np.float32).reshape(1,2,32,4,6)/17
 def test_patchify_explicit_spatial_channel_oracle(self):
  z=self.tiny_z();rows=[]
  for n in range(1):
   for t in range(32):
    for y in range(2):
     for x in range(3):rows.append([z[n,c,t,2*y+dy,2*x+dx] for c in range(2) for dy in range(2) for dx in range(2)])
  np.testing.assert_array_equal(core.patchify_video(z),np.asarray(rows,dtype=np.float32))
 def test_fixed_coordinate_noise_and_inverse(self):
  z=self.tiny_z();p=core.PERMUTATION;n=np.arange(32*6*8,dtype=np.float32).reshape(32*6,8)/11
  rows=core.patchify_video(z).reshape(32,6,8);expect=(np.float32(.999)*rows[p]+np.float32(1-.999)*n.reshape(32,6,8)).reshape(-1,8)
  actual=core.coordinate_augmented_rows(core.swap_reference(z),n)
  np.testing.assert_array_equal(actual,expect);np.testing.assert_array_equal(core.swap_reference(core.swap_reference(z)),z)
  moved_noise=core.coordinate_augmented_rows(z,n).reshape(32,6,8)[p].reshape(-1,8)
  self.assertGreater(float(np.max(abs(actual-moved_noise))),.001)
 def test_construct_keeps_all_other_inputs_and_has_no_alias(self):
  p=copy.deepcopy(POLICY);p.update(reference_shape=[1,2,32,4,6],condition_noise_shape=[192,8],position_shape=[20,3],target_packed_shape=[1,1,16],conditioning_embedding_shape=[1,5,4],conditioning_tags_shape=[5])
  arrays={'reference':self.tiny_z(),'coordinate_noise':np.ones((192,8),np.float32),'position_ids':np.zeros((20,3),np.float64),'target_packed_x':np.ones((1,1,16),np.float32),'conditioning_embedding':np.ones((1,5,4),np.float32),'conditioning_tags':np.arange(5,dtype=np.int64),'sample_sigmas_video':np.array(p['original_native_metadata'][0]['forward_identity']['sample_sigmas_video'],np.float32)}
  before={k:v.copy() for k,v in arrays.items()};out=core.construct_frozen_inputs(arrays,p['sigma_by_step']['9'],p)
  for k in arrays:
   np.testing.assert_array_equal(arrays[k],before[k]);self.assertFalse(np.shares_memory(arrays[k],out[k]))
   if k!='reference':np.testing.assert_array_equal(out[k],arrays[k])
  out['reference'][:]=0;out['conditioning_embedding'][:]=2
  for k in arrays:np.testing.assert_array_equal(arrays[k],before[k])
 def fixture(self):
  rng=np.random.default_rng(2026);q=rng.normal(size=(32,3,2,4)).astype(np.float32);k=rng.normal(size=q.shape).astype(np.float32);w=np.ones(4,np.float32);v=np.ones(32,bool);v[31]=False;s=np.array(POLICY['physical_frame_spans_inclusive'])
  return q,k,w,v,s
 def test_fixed_dictionary_readout_content_vs_coordinate(self):
  q,k,w,v,s=self.fixture();pi=core.PERMUTATION
  content=core.fixed_dictionary_readout(q,k,q[pi],w,w,v,pi,s)
  coord=core.fixed_dictionary_readout(q,k,q,w,w,v,pi,s)
  np.testing.assert_array_equal(content['nearest_mask'].argmax(-1),pi[:31]);np.testing.assert_array_equal(coord['nearest_mask'].argmax(-1),np.arange(31))
  self.assertTrue((content['coordinate_minus_source_margin'][5:15]>0).all());self.assertTrue((coord['coordinate_minus_source_margin'][5:15]<0).all())
  # Independent explicit dot -> key-probe exponential sum -> time normalization.
  nq=core.normalized_content(q,w);nk=core.normalized_content(k,w);valid=np.flatnonzero(v)
  expected=[]
  for querytime,probe,head in [(0,1,0),(6,2,1),(30,0,0)]:
   logits=np.array([[sum(float(nq[querytime,probe,head,d])*float(nk[j,r,head,d]) for d in range(4))/2 for r in range(3)] for j in valid]);exp=np.exp(logits-logits.max());prob=exp.sum(-1)/exp.sum()
   np.testing.assert_allclose(content['original_probability'][head,querytime,probe,valid],prob,rtol=5e-15,atol=1e-16)
 def test_unknown_partial_and_mislabeled_pair_rejected(self):
  q,k,w,v,s=self.fixture();res=core.fixed_dictionary_readout(q,k,q,w,w,v,core.PERMUTATION,s);a=core.summarize(res,9);b=core.summarize(res,19)
  self.assertEqual(core.summarize_pair({9:a})['status'],'pending')
  with self.assertRaises(ValueError):core.summarize_pair({9:a,19:a})
  bad=copy.deepcopy(b);bad['per_bin'][1]['query_bin']=bad['per_bin'][0]['query_bin']
  with self.assertRaises(ValueError):core.summarize_pair({9:a,19:bad})
  with self.assertRaises(ValueError):core.summarize_pair({9:a,19:b,20:b})
  good=core.summarize_pair({9:a,19:b});self.assertEqual(good['tested_correlated_bins'],62)
 def test_hash_checks_all_before_any_decode(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'a.npz';np.savez(p,a=np.arange(3));paths={'a':p,'z':p};hashes={'a':provenance.sha256(p),'z':'0'*64}
   with mock.patch.object(provenance.np,'load',side_effect=AssertionError('decoded')) as loader:
    with self.assertRaises(ValueError):provenance.verified_npz(paths,hashes,{'a':['a'],'z':['a']})
    self.assertFalse(loader.called)
 def test_model_forward_hard_refusal_even_with_claimed_gate(self):
  called=[]
  with self.assertRaises(provenance.PendingRuntime):provenance.request_model_forward(zero_gate=True,root_release=True,call=lambda:called.append(1))
  self.assertFalse(called)
if __name__=='__main__':unittest.main(verbosity=2)
