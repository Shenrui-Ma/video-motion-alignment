"""Execute the candidate's real probe and sampler audit with small synthetic predictions.

No Comfy/model/CUDA operation is represented as tested by this fixture.
The independent numerical oracle makes one chosen-endpoint Euler update per step.
"""
import sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace, MethodType
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'extensions'),str(ROOT/'tests')]
import torch
from test_visible_feedback import G,measurement
from H3AutomaticWindowRouter.selector import Controller
import H3AutomaticWindowRouter.core as c

class Call:
 def __init__(self,owner,fn):self.class_obj=owner;self.fn=fn
 def __call__(self,*a,**kw):return self.fn(*a,**kw)
class FreshTransactionFixture:
 def __init__(self,state):self.start=0
 def hydrate(self):pass
 def sampler_function(self,original):return original
 def check_native(self,row):pass
 def finish(self):pass
class PairFixture:
 def begin(self,*a):pass
 def branch(self,*a):pass
 def decision(self,*a):pass
 def finish(self,*a):pass

def exercise(arm,kind):
 with tempfile.TemporaryDirectory(prefix='r59-transaction-') as folder:
  s=SimpleNamespace(entered=False,finished=False,transaction=None,callback_count=0,phase=None,forward_index=-1,next_block=0,full_indices=[],reference=torch.zeros(1),snapshots=Path(folder),active_bins=[],query_gain=None,alpha=1.0)
  s.config=SimpleNamespace(geometry=G,shapes=((1,1,2),(1,1,2)),policy=arm)
  s.controller=Controller(G,arm=arm);s.pair_gate=PairFixture();s.write=lambda:None
  s.audit={'completed_forward_calls':0,'completed_calls':0,'routed_calls':0,'calls_by_forward':[],'routed_by_forward':[],'counterfactual':{'branches':[],'measurements':[],'inputs':[],'steps':[]}}
  s.raw=lambda v:[x.detach().to('cpu',copy=True).contiguous() for x in v.split(2,dim=-1)]
  s.reference_signature=c.readout.tensor_signature(s.reference)
  s.authorize=MethodType(c.State.authorize,s)
  s.save_input=lambda *a:None
  def save(value,n,branch):
   return {'physical_index':n,'branch':branch,'nfe_index':s.forward_index,'file':f'synthetic_step{n}_{branch}','raw_stream_signatures':[c.readout.tensor_signature(x) for x in s.raw(value)]}
  s.save_endpoint=save
  calls=[];observed=[];same_inputs=[]
  def observe(state,row):
   observed.append(row['physical_index']);return measurement(row['physical_index'],kind)
  s.live_observer=observe
  model=SimpleNamespace(latent_shapes=[(1,1,2),(1,1,2)],audio_scale=lambda:4.,latent_format=SimpleNamespace(scale_factor=1.))
  guider=SimpleNamespace(original_conds={'positive':[]},conds={},inner_model=model)
  options={'transformer_options':{}}
  sigmas=torch.linspace(1,0,21);options['transformer_options']['sample_sigmas']=sigmas
  noise=torch.arange(4,dtype=torch.float32).reshape(1,1,4)/7
  noise_before=noise.clone();seed=2026101701
  probe=c.PredictionProbe(s)
  def predict(x,timestep,model_options,seed):
   branch=s.phase['branch'];same_inputs.append((s.callback_count,branch,x.clone()))
   calls.append((s.callback_count,branch,s.alpha))
   s.forward_index+=1;s.audit['completed_forward_calls']+=1;s.audit['completed_calls']+=50
   s.audit['calls_by_forward'].append(50);s.audit['routed_by_forward'].append(50 if branch=='full' else 0)
   s.audit['routed_calls']+=50 if branch=='full' else 0
   return x*.25+.001+(s.alpha*.002 if branch=='full' else 0)
  predict_exec=Call(guider,predict)
  update_count=[]
  def sample_euler(model_wrap,sigma,args,callback,initial,latent,mask,disable):
   x=initial.clone()
   for i in range(20):
    original=x.clone();pred=probe(predict_exec,x,sigma[i:i+1],args['model_options'],args['seed'])
    if not torch.equal(x,original):raise AssertionError('PredictionProbe changed Euler input')
    callback(i,pred,x,20)
    derivative=(x-pred)/sigma[i]
    x=x+derivative*(sigma[i+1]-sigma[i]);update_count.append(i)
   return x
  sampler=SimpleNamespace(sampler_function=sample_euler,extra_options={},inpaint_options={})
  executor=Call(sampler,sample_euler)
  audit=c.SamplerAudit(s,unpack=lambda x:x,nested=lambda x:x)
  callback_indices=[]
  with patch('H3AutomaticWindowRouter.resume_state.ResumeState',FreshTransactionFixture),patch.object(c,'validate_guider',lambda *a:None),patch.object(c,'parent_guard',lambda *a:'unchanged'):
   actual=audit(executor,guider,sigmas,{'seed':seed,'model_options':options},lambda i,*a:callback_indices.append(i),noise,disable_pbar=True)
  controller=Controller(G,arm=arm);expected=noise.clone();expected_active=[]
  for i in range(20):
   d=controller.select(i,measurement(i,kind) if controller.needs_observation else None)
   endpoint=expected*.25+.001+(d['route_alpha']*.002 if d['chosen_full'] else 0)
   expected=expected+(expected-endpoint)/sigmas[i]*(sigmas[i+1]-sigmas[i])
   if d['chosen_full']:expected_active.append(i)
  assert torch.equal(actual,expected),'single-update independent oracle differs'
  assert torch.equal(noise,noise_before)
  assert callback_indices==update_count==list(range(20))
  assert s.full_indices==expected_active
  assert len(calls)==20+len(expected_active)
  assert observed==(list(range(20)) if controller.needs_observation else [])
  for i in expected_active:
   entries=[x for n,branch,x in same_inputs if n==i]
   assert len(entries)==2 and torch.equal(entries[0],entries[1]),'Native/Full did not share x'
  return len(calls),expected_active,s.audit

class Transactions(unittest.TestCase):
 def test_native_one_forward_one_euler_no_observer(self):
  count,indices,a=exercise('native','unknown');self.assertEqual(count,20);self.assertEqual(indices,[])
 def test_weak_only29_forwards20_euler_no_observer(self):
  count,indices,a=exercise('weak_only','unknown');self.assertEqual(count,29);self.assertEqual(indices,list(range(6,15)))
 def test_visible_unknown20_forwards20_euler(self):
  count,indices,a=exercise('visible_only','unknown');self.assertEqual(count,20)
 def test_visible_persistent39_forwards20_euler(self):
  count,indices,a=exercise('visible_only','candidate');self.assertEqual(count,39);self.assertEqual(indices,list(range(1,20)))
 def test_fallback29_forwards20_euler(self):
  count,indices,a=exercise('visible_fallback','unknown');self.assertEqual(count,29);self.assertEqual(indices,list(range(6,15)))
 def test_fallback_visible_priority39_forwards20_euler(self):
  count,indices,a=exercise('visible_fallback','candidate');self.assertEqual(count,39)
  self.assertTrue(all(r['decision']['route_alpha']==1 for r in a['counterfactual']['steps'][1:]))

if __name__=='__main__':unittest.main()
