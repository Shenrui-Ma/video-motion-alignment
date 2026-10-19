import sys,unittest,torch,tempfile,json,copy,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extensions'))
from H3ForwardReverseRouter.core import joint_attention
from H3ForwardReverseRouter.base_router import route_attention
from H3ForwardReverseRouter.reverse_frozen import reverse_attention
from H3ForwardReverseRouter.sampler_gate import canonical_condition,actual_prefix,signature
from test_reverse_parent import plan,dense,attention_pytorch

def flash_contract(q,k,v):
 out,lse=dense(q,k,v);return out,lse.float()
def mathematical(q,k,v,p,f,b):
 logits=q@k.transpose(-1,-2)/q.shape[-1]**.5;prob=logits.softmax(-1);w=prob.clone();ra,rb=p['reference_video_segment'];ta,tb=p['query_interval_half_open'];rqa,rqb=p['key_interval_half_open'];tk0,tk1=p['target_video_segment']
 if f:
  for i in range(ta,tb):
   group=(i-p['target_video_segment'][0])//p['frame_rows'];lo=ra+group*p['frame_rows'];hi=lo+p['frame_rows'];mass=prob[:,:,i,ra:rb].sum(-1,keepdim=True);w[:,:,i,ra:rb]=0;w[:,:,i,lo:hi]=mass*logits[:,:,i,lo:hi].softmax(-1)
 if b:
  logits[:,:,rqa:rqb,tk0:tk1]=-torch.inf;w[:,:,rqa:rqb]=logits[:,:,rqa:rqb].softmax(-1)
 return (w@v).transpose(1,2).reshape(1,q.shape[-2],-1),w
class JointTests(unittest.TestCase):
 def setUp(self):
  torch.set_num_threads(1);g=torch.Generator().manual_seed(430);self.q,self.k,self.v=[torch.randn(1,3,31,8,generator=g,dtype=torch.float64) for _ in range(3)]
 def runmode(self,mode,**kwargs):return joint_attention(attention_pytorch,self.q,self.k,self.v,3,plan(),mode=mode,attention=flash_contract,**kwargs)
 def test_four_modes_oracle_and_component_paths(self):
  for dtype in (torch.float64,torch.float32):
   self.q,self.k,self.v=[x.to(dtype) for x in (self.q,self.k,self.v)]
   for mode in ('native','forward','reverse_block','joint'):
    got=self.runmode(mode);truth,w=mathematical(self.q,self.k,self.v,plan(),mode in ('forward','joint'),mode in ('reverse_block','joint'))
    tol={'atol':2e-12,'rtol':2e-12} if dtype==torch.float64 and mode in ('native','reverse_block') else {'atol':3e-6,'rtol':3e-5}
    torch.testing.assert_close(got,truth,**tol);torch.testing.assert_close(w.sum(-1),torch.ones_like(w.sum(-1)));self.assertTrue(bool((w>=0).all()))
   f=route_attention(self.q,self.k,self.v,3,plan(),mode='mass_preserve',attention=flash_contract);b=reverse_attention(attention_pytorch,self.q,self.k,self.v,3,plan(),mode='reverse_block',attention=flash_contract);joint=self.runmode('joint')
   self.assertTrue(torch.equal(joint[:,22:28],f[:,22:28]));self.assertTrue(torch.equal(joint[:,6:12],b[:,6:12]))
 def test_disjoint_assembly_order_and_native_rows(self):
  n=self.runmode('native');f=self.runmode('forward');b=self.runmode('reverse_block');j=self.runmode('joint');a=n.clone();a[:,22:28]=f[:,22:28];a[:,6:12]=b[:,6:12];z=n.clone();z[:,6:12]=b[:,6:12];z[:,22:28]=f[:,22:28]
  self.assertTrue(torch.equal(a,z) and torch.equal(j,a))
  mask=torch.ones(31,dtype=torch.bool);mask[6:12]=False;mask[22:28]=False;self.assertTrue(torch.equal(j[:,mask],n[:,mask]))
 def test_audit_and_inference_rng(self):
  with torch.inference_mode():
   self.q,self.k,self.v=[x.clone() for x in (self.q,self.k,self.v)];old=[x.clone() for x in (self.q,self.k,self.v)];rng=torch.get_rng_state().clone();audit={};j=self.runmode('joint',first_audit=audit)
   self.assertTrue(all(audit[k] for k in ('input_values_bitwise','nonselected_rows_bitwise','target_audio_bitwise','forward_component_rows_bitwise','reverse_component_rows_bitwise','native_vs_prewrite_full_Flash_bitwise','finite')));self.assertEqual(audit['input_versions_before'],[None]*3);self.assertEqual(audit['aux_attention_calls'],5);self.assertEqual(audit['extra_full_Flash_calls'],1);self.assertTrue(all(torch.equal(a,b) for a,b in zip(old,(self.q,self.k,self.v))) and torch.equal(rng,torch.get_rng_state()))
 def test_disabled_exact_and_zero_correction_valid(self):
  n=self.runmode('native');self.assertTrue(torch.equal(n,self.runmode('joint',forward_alpha=0,reverse_alpha=0)))
  self.assertTrue(torch.equal(self.runmode('forward'),self.runmode('joint',reverse_alpha=0)));self.assertTrue(torch.equal(self.runmode('reverse_block'),self.runmode('joint',forward_alpha=0)))
  self.v.zero_();audit={};self.runmode('joint',first_audit=audit);self.assertTrue(audit['selected_reference_rows_equal_native'] and audit['selected_target_rows_equal_native'])
 def test_audio_portrait_complement_retained(self):
  self.v.zero_();self.v[:,:,2:3]=1;self.v[:,:,15:19]=2;self.assertGreater(float(self.runmode('reverse_block')[:,6:12].sum()),0)
 def test_bad_layout_backend_and_mutation_rejected(self):
  for p in (dict(plan(),query_interval_half_open=[6,12]),dict(plan(),seq_len=32)):
   with self.assertRaises(ValueError):joint_attention(attention_pytorch,self.q,self.k,self.v,3,p,mode='joint',attention=flash_contract)
  def bad(q,k,v,h,**kw):return attention_pytorch(q,k,v,h)+1
  with self.assertRaisesRegex(ValueError,'prewrite Flash'):joint_attention(bad,self.q,self.k,self.v,3,plan(),mode='joint',attention=flash_contract,first_audit={})
  def mutate(q,k,v,h,**kw):q.add_(1);return attention_pytorch(q,k,v,h)
  with self.assertRaisesRegex(ValueError,'versions'):joint_attention(mutate,self.q,self.k,self.v,3,plan(),mode='joint',attention=flash_contract)
 def test_UUID_only_exact_exceptions(self):
  def tree(u):return {'original':{'positive':[{'uuid':u,'value':3}]},'processed':{'positive':[{'uuid':u,'value':3}]}}
  a,b=tree(str(uuid.uuid4())),tree(str(uuid.uuid4()));self.assertEqual(canonical_condition(a),canonical_condition(b));b['processed']['positive'][0]['value']=4;self.assertNotEqual(canonical_condition(a),canonical_condition(b));a['processed']['positive'][0]['uuid']=str(uuid.uuid4())
  with self.assertRaises(ValueError):canonical_condition(a)
if __name__=='__main__':unittest.main()
