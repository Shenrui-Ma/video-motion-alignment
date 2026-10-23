"""Control-flow integration with actual KSAMPLER and synthetic cheap model.

No checkpoint, real capture, runtime service or CUDA input is used. Capture is a
small fixture: the original passive hook implementation remains separately bound
to its reviewed live source, not scientifically validated by this fake model.
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS, MethodType
from unittest.mock import patch
import torch
from adapter import ContentCoordinateSampler, QK_NAMES, TENSOR_METADATA, VALUE_METADATA
from condition import prepared_payload
from identity import tensor_info
from test_cpu import SOURCE, actual_condition_class, guider


def qk(step):
    d={name:torch.ones(2) for name in QK_NAMES+TENSOR_METADATA}
    d.update({name:0 for name in VALUE_METADATA});d['step_zero_based']=step
    return d


class FakeCapture:
    def __init__(self, attention, probes, *, step, **kw):self.data=qk(step)
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def save(self,path):torch.save(self.data,path)


class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.out=Path(self.tmp.name)/'result'
        self.shapes=[[1,24,32,46,82],[1,32,2,178]]
        self.noise=torch.ones(1,1,2908288);self.sigmas=torch.linspace(1,0,21)
        self.contract=dict(sigmas_video=self.sigmas.double().tolist(),noise_tensor_sha256=tensor_info(self.noise)['sha256'],target_shapes=self.shapes,router={'mode':'native'})
        self.inputs={i:(dict(packed_x=torch.full_like(self.noise,float(i)/20),raw_packed_x0=torch.full_like(self.noise,float(i)/20)*.2),qk(i)) for i in (9,19)}
        self.state=NS(mode='native',forward_index=-1,next_block=0,audit=dict(started_calls=0,completed_calls=0,completed_forward_calls=0))
        self.options={'transformer_options':{'sample_sigmas':self.sigmas,'patches_replace':{'dit':{('double_block',i):NS(state=self.state) for i in range(50)}}}}
        self.backend={'operations':{b+'.'+op:dict(attempted_calls=0,successful_calls=0,failed_calls=0) for b in ('cuda','triton','eager') for op in ('int8_linear','w4a8_int8_linear')}}
        self.observed=[];self.router_refs=[];self.fail_on=None
        owner=self
        class Model(torch.nn.Module):
            def forward(m,x,sigma,**args):
                router=args['model_options']['transformer_options']['patches_replace']['dit'][('double_block',0)].state
                step=router.forward_index+1
                owner.router_refs.append(router)
                z=prepared_payload(owner.g)['cond_video_latents'][0]
                owner.observed.append(dict(step=step,x=tensor_info(x),z=float(z[0,0,5,0,0]),state=id(router)))
                if owner.fail_on==len(owner.observed):raise RuntimeError('synthetic model failure')
                m._cond_video_rows(prepared_payload(owner.g),'cpu')
                router.forward_index=step;router.audit.update(started_calls=50,completed_calls=50,completed_forward_calls=1)
                for key in ('attempted_calls','successful_calls'):owner.backend['operations']['triton.int8_linear'][key]+=200
                return x*.2
        m=Model();m.patch_size=(1,2,2)
        m._cond_video_rows=MethodType(actual_condition_class()._cond_video_rows,m)
        m.blocks=[NS(attn=NS(heads=56,head_dim=128)) for _ in range(50)]
        z=torch.arange(32,dtype=torch.float32).reshape(1,1,32,1,1).expand(1,24,32,46,82).clone()
        self.g=guider(z);self.g.cfg=1
        class Sampler:
            def max_denoise(self,*args):return True
        scope=dict(torch=torch,Sampler=Sampler,detail=lambda *a,**kw:None)
        for name in ('reshape_sigma','CONST','KSamplerX0Inpaint','KSAMPLER'):exec(SOURCE[name],scope)
        ms=scope['CONST']();ms.noise_scale=1;ms.shift=12;ms.audio_shift=3;ms.multiplier=1000
        self.g.inner_model=NS(model_sampling=ms,audio_scale=lambda:4.,latent_shapes=self.shapes,diffusion_model=m)
        class ModelWrap:
            inner_model=self.g.inner_model
            def __call__(w,x,sigma,**kwargs):return m(x,sigma,**kwargs)
        # KSAMPLER builds KSamplerX0Inpaint around an object whose inner_model is
        # the BaseModel. Its inner_model must also expose prepared guider fields.
        self.wrap=ModelWrap();self.wrap.conds=self.g.conds;self.wrap.cfg=1
        self.g=self.wrap
        self.model=m;self.KSAMPLER=scope['KSAMPLER'];self.saved_conds=self.g.conds
        self.saved_method=m._cond_video_rows
        self.mm_patch=patch.dict(sys.modules,{'comfy.model_management':NS(in_training=False)})
        self.mm_patch.start()
    def tearDown(self):self.mm_patch.stop();self.tmp.cleanup()
    def run_sampler(self):
        fn=ContentCoordinateSampler(self.inputs,self.contract,self.out,allow_swap=True,backend_snapshot=lambda:copy.deepcopy(self.backend))
        probes=NS(valid_bins=[True]*31+[False])
        with patch('adapter.PassiveQKCapture',FakeCapture),patch('adapter.ProbeLayout.from_actual',return_value=probes):
            value=self.KSAMPLER(fn).sample(self.wrap,self.sigmas,{'model_options':self.options,'seed':2026101701},None,
                self.noise,torch.zeros_like(self.noise),None,True)
        return fn,value
    def test_four_independent_forwards_fresh_router_and_saved_states(self):
        fn,value=self.run_sampler()
        self.assertEqual([(r['step'],r['z']) for r in self.observed],[(9,5),(19,5),(9,10),(19,10)])
        self.assertEqual(len(set(r['state'] for r in self.observed)),4)
        for record in self.observed:self.assertEqual(record['x'],tensor_info(self.inputs[record['step']][0]['packed_x']))
        self.assertIs(self.g.conds,self.saved_conds);self.assertEqual(self.state.forward_index,-1)
        gate=json.loads((self.out/'GATE.json').read_text())
        self.assertEqual(gate['status'],'forwards_complete');self.assertFalse(gate['passed'])
        self.assertEqual(gate['physical_forward_calls'],4)
    def test_zero19_one_element_failure_stops_before_swap(self):
        self.inputs[19][0]['raw_packed_x0'][0,0,-1]+=1e-5
        with self.assertRaises(ValueError):self.run_sampler()
        self.assertEqual(len(self.observed),2)
        gate=json.loads((self.out/'GATE.json').read_text())
        self.assertFalse(gate['passed']);self.assertTrue(gate['calls'][0]['zero_exact'])
        self.assertFalse((self.out/'swap9').exists())
    def test_model_failure_restores_payload_oracle_counter_hooks(self):
        self.fail_on=2
        with self.assertRaises(RuntimeError):self.run_sampler()
        self.assertIs(self.g.conds,self.saved_conds)
        self.assertEqual(self.model._cond_video_rows,self.saved_method)
        self.assertEqual(len(self.model._forward_hooks),0)
        self.assertFalse(json.loads((self.out/'GATE.json').read_text())['passed'])
        self.assertFalse((self.out/'swap9').exists())


if __name__=='__main__':unittest.main()
