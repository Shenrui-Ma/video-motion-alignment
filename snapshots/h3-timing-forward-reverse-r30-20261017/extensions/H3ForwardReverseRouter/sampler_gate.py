"""Passive single-forward/callback gate and parent native005 stop-before-route bridge."""
import hashlib
import json
import time
import uuid

import torch

from .guider_identity import official_basic_guider_class

KEY='H3ForwardReverseRouter/sampler-gate-v1'


def signature(tensor):
    cpu=tensor.detach().to('cpu').contiguous()
    return dict(shape=list(cpu.shape),dtype=str(cpu.dtype),bytes=cpu.numel()*cpu.element_size(),
                sha256=hashlib.sha256(cpu.view(torch.uint8).numpy().tobytes()).hexdigest())


def signature_tree(value):
    if isinstance(value,torch.Tensor):return signature(value)
    if value is None or isinstance(value,(str,bool,int,float)):return value
    if isinstance(value,(list,tuple)):return [signature_tree(v) for v in value]
    if isinstance(value,dict):return {str(k):signature_tree(v) for k,v in sorted(value.items(),key=lambda p:str(p[0]))}
    if isinstance(value,(uuid.UUID,torch.device,torch.dtype)):return str(value)
    if hasattr(value,'cond'):return {'type':type(value).__qualname__,'cond':signature_tree(value.cond)}
    if type(value).__name__=='PackedLayout':return {'type':'PackedLayout','fields':signature_tree(vars(value))}
    raise ValueError('unsupported actual conditioning value '+type(value).__qualname__)


def condition_signature(guider):
    tree=signature_tree({'original':guider.original_conds,'processed':getattr(guider,'conds',{})})
    data=json.dumps(tree,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return {'sha256':hashlib.sha256(data).hexdigest(),'tree':tree}


def normalized_streams(x0,model,shapes):
    from comfy.utils import unpack_latents
    from comfy.nested_tensor import NestedTensor
    if getattr(x0,'is_nested',False):leaves=list(x0.unbind())
    else:
        size=sum(torch.Size(s).numel() for s in shapes)
        if tuple(x0.shape)!=(1,1,size):raise ValueError('invalid packed x0 shape')
        leaves=list(unpack_latents(x0,shapes))
    if len(leaves)!=2 or any(tuple(t.shape)!=tuple(s) or t.dtype!=torch.float32 for t,s in zip(leaves,shapes)):
        raise ValueError('invalid raw x0 streams')
    raw=[t.detach().to('cpu',copy=True).contiguous() for t in leaves]
    ready=list(model.process_latent_out(NestedTensor(raw)).unbind())
    if len(ready)!=2 or not torch.equal(ready[0],raw[0]) or not torch.equal(ready[1],raw[1]/4):
        raise ValueError('normalization must remain video identity/audio4')
    if any(not bool(torch.isfinite(t).all()) for t in ready):raise ValueError('nonfinite parent prefix')
    return ready

def normalized_signature(x0,model,shapes):
    return {k:signature(v) for k,v in zip(('video','audio'),normalized_streams(x0,model,shapes))}


def canonical_condition(tree):
    import copy
    value=copy.deepcopy(tree)
    a=value['original']['positive'][0]['uuid'];b=value['processed']['positive'][0]['uuid']
    if a!=b or str(uuid.UUID(a))!=a:raise ValueError('condition UUID correspondence differs')
    value['original']['positive'][0]['uuid']='<allowed-run-UUID>'
    value['processed']['positive'][0]['uuid']='<allowed-run-UUID>'
    return value

def actual_prefix(ready,index,bindings,native005):
    from pathlib import Path
    rows=bindings['native_0to5']
    if len(rows)!=6 or [x['physical_index'] for x in rows]!=list(range(6)):raise ValueError('six fixed prefix rows required')
    r=rows[index];p=Path(r['file'])
    if hashlib.sha256(p.read_bytes()).hexdigest()!=r['file_sha256']:raise ValueError('historical prefix file SHA differs')
    old=torch.load(p,map_location='cpu',weights_only=True)
    if set(old)!={'video','audio','metadata'}:raise ValueError('historical R10 prefix schema')
    m=old['metadata']
    if any(m[k]!=r[k] for k in ('physical_index','branch','seed','sigma','sigma_next')):raise ValueError('historical prefix metadata')
    expected=r['normalized_stream_signatures'];actual=[signature(old[k]) for k in ('video','audio')]
    if actual!=expected or not all(torch.equal(v,old[k]) for k,v in zip(('video','audio'),ready)):raise ValueError('eligible Native prefix mismatch')
    result={'index':index,'file':str(p),'file_sha256':r['file_sha256'],'old_signatures':actual,'current_signatures':[signature(v) for v in ready],'actual_tensor_equal':True,'source':'R10 actual Native prefix; available R3 common endpoints and final141RGB replayed'}
    if index==5:
        q=Path(native005['file'])
        if hashlib.sha256(q.read_bytes()).hexdigest()!=native005['sha256']:raise ValueError('actual R3 Native005 file SHA differs')
        other=torch.load(q,map_location='cpu',weights_only=True);m=other['metadata']
        if m['schema']!='h3-x0-readout-v1' or m['seed']!=2026101311 or m['step_zero_based']!=5 or m['normalization_stage']!='after_process_latent_out' or m['audio_scale']!=4 or m['video_latent_scale_factor']!=1:raise ValueError('actual R3 Native005 metadata')
        if [signature(other[k]) for k in ('video','audio')]!=expected or not all(torch.equal(other[k],v) for k,v in zip(('video','audio'),ready)):raise ValueError('actual R3 Native005 tensor mismatch')
        result['actual_R3_Native005']={'file':str(q),'file_sha256':native005['sha256'],'tensor_equal':True}
    return result


class SamplerGate:
    def __init__(self,state,parent,grid,seed,shapes):
        self.state,self.parent,self.grid,self.seed,self.shapes=state,parent,grid,seed,tuple(tuple(x) for x in shapes)

    def __call__(self,executor,model_wrap,sigmas,extra_args,callback,noise,
                 latent_image=None,denoise_mask=None,disable_pbar=False):
        from comfy_extras.nodes_custom_sampler import Guider_Basic
        s=self.state
        if s.sampling_started:raise ValueError('one exclusive sample per fresh router state')
        if not official_basic_guider_class(type(model_wrap),Guider_Basic) or model_wrap.cfg!=1.:
            raise ValueError('official single-positive BasicGuider CFG1 required')
        if set(model_wrap.original_conds)!={'positive'} or len(model_wrap.original_conds['positive'])!=1:
            raise ValueError('one positive and no negative conditioning required')
        sampler=executor.class_obj
        if getattr(sampler.sampler_function,'__name__',None)!='sample_euler' or sampler.extra_options.get('s_churn',0)!=0:
            raise ValueError('unchanged Euler without churn required')
        grid=sigmas.detach().cpu().tolist()
        if grid!=self.grid or len(grid)!=21 or extra_args.get('seed')!=self.seed:
            raise ValueError('actual sampler sigma/seed differs from frozen parent')
        model=model_wrap.inner_model
        if tuple(tuple(x) for x in model.latent_shapes)!=self.shapes or model.audio_scale()!=4 or model.latent_format.scale_factor!=1:
            raise ValueError('actual AV geometry/scaling mismatch')
        s.sampling_started=True;s.audit['sample_sigmas']=grid;s.audit['expected_sampling_steps']=20
        before_condition=condition_signature(model_wrap);before_noise=signature(noise)
        if canonical_condition(before_condition['tree'])!=canonical_condition(self.parent_condition):raise ValueError('actual B processed condition differs beyond two UUID leaves')
        before_rng=torch.get_rng_state().clone();cuda_rng=torch.cuda.get_rng_state(noise.device).clone() if noise.device.type=='cuda' else None
        s.audit['sampler_gate']=dict(status='running',seed=self.seed,sigmas=grid,noise=before_noise,
            actual_current_condition=before_condition,historical_processed_tree_compared='R25 B tree except two exact consistent UUID leaves',
            B_processed_condition_equal=True,prefix_0to5=[],
            historical_evidence_scope='clean conditions+noise+code/seed and actual005AV bridge',callback_records=[])
        started=time.perf_counter();s.write()

        def record(i,x0,x,total):
            if (i!=s.callback_count or total!=20 or i>=20 or s.forward_index!=i or s.next_block!=0 or
                    s.audit['completed_forward_calls']!=i+1):raise ValueError('callback must follow exactly one complete50-block model forward')
            if sigmas.detach().cpu().tolist()!=self.grid:raise ValueError('actual full sampler grid changed')
            row=dict(index=i,completed_NFE=i+1,completed_blocks=s.audit['completed_calls'])
            if i<=5:
                ready=normalized_streams(x0,model,self.shapes)
                proof=actual_prefix(ready,i,self.prefix_bindings,self.native005)
                s.audit['sampler_gate']['prefix_0to5'].append(proof)
                row['actual_Native_prefix']=proof
            if i==5:
                actual={k:signature(v) for k,v in zip(('video','audio'),ready)}
                expected={k:self.parent[k] for k in ('video','audio')}
                row['parent_prefix005']={'actual':actual,'expected':expected,'passed':actual==expected}
                s.audit['sampler_gate']['prefix005']=row['parent_prefix005']
                s.write()
                if actual!=expected:raise ValueError('parent native005 AV prefix mismatch; abort before any joint intervention')
                s.prefix_passed=True
            s.callback_count+=1;s.audit['callback_count']=s.callback_count
            s.audit['sampler_gate']['callback_records'].append(row)
            if callback is not None:callback(i,x0,x,total)

        try:
            result=executor(model_wrap,sigmas,extra_args,record,noise,latent_image,denoise_mask,disable_pbar)
            if s.callback_count!=20 or s.audit['completed_forward_calls']!=20:raise ValueError('incomplete Euler/forward count')
            if condition_signature(model_wrap)!=before_condition or signature(noise)!=before_noise:
                raise ValueError('original actual conditions/noise mutated')
            if not torch.equal(before_rng,torch.get_rng_state()) or (cuda_rng is not None and not torch.equal(cuda_rng,torch.cuda.get_rng_state(noise.device))):
                raise ValueError('sampler/diagnostic consumed global RNG')
            s.audit['sampler_gate'].update(status='complete',condition_noise_rng_unchanged=True)
            s.audit['status']='complete'
            return result
        except BaseException as exc:
            s.audit.update(status='failed',error=repr(exc));s.audit['sampler_gate']['status']='failed';raise
        finally:
            s.audit['sampler_gate']['sampler_wall_seconds']=time.perf_counter()-started
            if noise.device.type=='cuda':
                s.audit['sampler_gate']['memory_peak_allocated_bytes']=torch.cuda.max_memory_allocated(noise.device)
                s.audit['sampler_gate']['memory_peak_reserved_bytes']=torch.cuda.max_memory_reserved(noise.device)
            s.write()
