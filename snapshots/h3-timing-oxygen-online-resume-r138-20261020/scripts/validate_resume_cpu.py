"""Actual archived state0..9 replay using the deployed resume sampler; no model load."""
import os,sys,json
from pathlib import Path
from types import SimpleNamespace
from r86_contract import ROOT,read,require
from execution_gate import atomic
require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','hide CUDA for actual recovery verification')
sys.path.insert(0,str(ROOT/'extensions'))
import torch
torch.set_num_threads(1)
from H3AutomaticWindowRouter.resume_state import ResumeState
from H3X0Readout.core import tensor_signature
case=read(ROOT/'configs/protocol.json')['cases'][0]
shapes=((1,24,32,46,82),(1,32,2,178));counts=[int(torch.tensor(s).prod()) for s in shapes]
def raw(v):return [x.reshape(shape) for x,shape in zip(v.split(counts,dim=-1),shapes)]
state=SimpleNamespace(raw=raw,audit={'counterfactual':{'resume':{}}})
r=ResumeState(state)
cache=read(ROOT/'prepared_parent/noise.json')['cache_file'];noise=torch.load(cache,map_location='cpu',weights_only=True)
x=torch.cat([v.reshape(1,1,-1) for v in noise['tensors']],-1)
grid=torch.tensor(r.old['counterfactual']['full_grid'],dtype=torch.float32)
callback_rows=[]
def callback(v):
 r.replay_callback(v['i'],v['denoised'],v['x'],20)
 callback_rows.append({'index':v['i'],'noisy_state_sha256':tensor_signature(v['x'])['sha256']})
continuations=[]
def original(model,x,sigmas,**kwargs):
 require(torch.equal(x,r.state9) and torch.equal(sigmas,grid[9:]),'actual continuation state/grid differs')
 continuations.append({'input':tensor_signature(x),'grid':sigmas.tolist()})
 return x
value=r.sampler_function(original)(None,x,grid,callback=callback)
require(not torch.cuda.is_initialized(),'CPU replay initialized CUDA')
result={'passed':True,'actual_callbacks':callback_rows,'actual_continuation':continuations,
        'model_predictions':0,'observer_calls':0,'archival_callbacks':9,'state9_signature':tensor_signature(value),
        'full_prefix_exact':state.audit['counterfactual']['resume']['prefix_reconstruction_exact'],
        'cuda_initialized':False}
atomic(ROOT/'audit/ACTUAL_RESUME_CPU.json',result);print(json.dumps(result,indent=2))
