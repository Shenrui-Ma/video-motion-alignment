"""Full packed geometry with small deterministic CPU model calculations."""
import hashlib
import json
from pathlib import Path
import sys
import uuid
from types import SimpleNamespace

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'extensions'))
from H3OneStepForkAudit.core import (State, Config, BlockPatch, ForkSampler, POINTS,
    condition_signature, readout)
from counterfactual_support import FakeModel, unpack, cpu_attention, run_blocks, Observations


def to_d(x, sigma, denoised):
    return (x-denoised)/sigma.reshape(sigma.shape+(1,)*(x.ndim-sigma.ndim))


class FakeGuider:
    cfg = 1.0
    def __call__(self, x, sigma, model_options=None, seed=None):
        run_blocks(self.state, self.patches, sigmas=model_options['transformer_options']['sample_sigmas'])
        if self.fail == 'double_forward':
            run_blocks(self.state, self.patches)
        if self.fail == 'rng': torch.rand(1)
        if self.fail == 'input': x.add_(1)
        if self.fail == 'sigma': sigma.add_(0.001)
        if self.fail == 'condition': self.original_conds['positive'][0]['tag'] += 1
        if self.fail == 'grid': model_options['transformer_options']['sample_sigmas'][0] = 0.9
        y = x*0.25 + 0.015625
        if self.fail == 'endpoint': y += 0.0001
        return y


class MemorySource:
    def __init__(self, path, condition, noise, reference, *, same=False, euler=None):
        self.manifest_path = path/'source_stub.json'
        self.manifest_path.write_text('{"fixture":true}')
        self.shapes = ((1,24,42,46,82),(1,32,2,235))
        self.condition = condition
        self.grid = torch.linspace(1,0,21)
        self.c = {'seed':2026101311,'full_grid':self.grid.tolist(),'initial_noise':readout.tensor_signature(noise)}
        self.data, self.rows, self.input_data = {}, {}, {}
        refsig = readout.tensor_signature(reference)['sha256']
        def capture(n,x):
            native=x*0.25+0.015625
            full=native if same else native+0.01
            if n in POINTS:
                self.input_data[n] = (x.clone(), {'reference_sha256':refsig})
            if n in POINTS or n-1 in POINTS:
                for branch,y in [('native',native),('full',full)]:
                    streams=unpack(y,self.shapes)
                    row={'raw_stream_signatures':[readout.tensor_signature(v) for v in streams],
                         'normalized_stream_signatures':[readout.tensor_signature(streams[0]),readout.tensor_signature(streams[1]*0.25)],
                         'same_input':readout.tensor_signature(x),'reference_sha256':refsig}
                    self.data[n,branch]=y.clone();self.rows[n,branch]=row
            return full if 6<=n<15 else native
        if euler is None:
            x=noise.clone()
            for n in range(20):
                y=capture(n,x)
                d=to_d(x,self.grid[n],y)
                dt=self.grid[n+1]-self.grid[n]
                x=x+d*dt
        else:
            def model(x,sigma,**kwargs):
                n=int((self.grid-sigma.reshape(())).abs().argmin())
                return capture(n,x)
            euler(model,noise.clone(),self.grid,disable=True)

    def input(self,n): return self.input_data[n]
    def endpoint(self,n,branch): return self.data[n,branch],self.rows[n,branch]


def make_case(path, *, fail=None, same=False):
    cfg=Config('cpu_case',str(path/'audit'))
    reference=torch.zeros(cfg.shapes[0])
    total=sum(torch.Size(s).numel() for s in cfg.shapes)
    noise=torch.arange(total,dtype=torch.float32).reshape(1,1,-1)/total
    guider=FakeGuider();guider.fail=fail
    guider.original_conds={'positive':[{'uuid':uuid.uuid4(),'tag':1,'minimax_refs':[{'kind':'video','latent':reference}]}]}
    guider.conds={'positive':[dict(guider.original_conds['positive'][0])]}
    source=MemorySource(path,condition_signature(guider),noise,reference,same=same)
    state=State({'refs':[]},reference,cfg,source,observer=Observations([0]))
    state.plan_for=lambda _: {'seq_len':84,'frame_rows':1,'latent_interval_half_open':[14,20],
                             'query_interval_half_open':[56,62],'reference_video_segment':[0,42]}
    state.extra_conds_calls=1
    guider.state=state;guider.inner_model=FakeModel(cfg.shapes)
    guider.patches={('double_block',i):BlockPatch(state,i) for i in range(50)}
    wrapper=ForkSampler(state,unpack=unpack,to_d=to_d,expected_class=FakeGuider,require_cuda=False)
    guider.model_options={'transformer_options':{'sample_sigmas':source.grid,
        'patches_replace':{'dit':guider.patches},'wrappers':{'sampler_sample':{'fork':[wrapper]}}}}
    return state,guider,noise,wrapper


def execute(case, *, callback=None):
    state,guider,noise,wrapper=case
    def forbidden(*args,**kwargs):raise AssertionError('KSAMPLER executor was called')
    with cpu_attention():
        return wrapper(forbidden,guider,state.source.grid,{'model_options':guider.model_options,'seed':2026101311},
                       callback,noise,torch.zeros_like(noise),None,True)
