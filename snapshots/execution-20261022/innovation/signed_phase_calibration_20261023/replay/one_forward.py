"""Finite replay SAMPLER preserving CFGGuider/AV wrappers and historical indexing.

This module never loads weights, submits a graph, or loops over the denoising grid.
It is used only by the isolated output node after explicit resource deployment.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import torch
try:
    from .capture import ProbeLayout,PassiveQKCapture
    from .reconstruct import file_sha,tensor_info,unpack,raw_x0,sigma_grid
except ImportError:
    from capture import ProbeLayout,PassiveQKCapture
    from reconstruct import file_sha,tensor_info,unpack,raw_x0,sigma_grid


def arm_router_options(options,step,outdir):
    """Clone ONLY fresh historical patch state; retain frozen patch algorithms.

    Zero entries before `step` are explicitly skipped accounting placeholders,
    not earlier executed forwards. Each off/on call gets independent counters.
    """
    result=dict(options);to=dict(result.get('transformer_options',{}));result['transformer_options']=to
    pr=dict(to.get('patches_replace',{}));to['patches_replace']=pr;dit=dict(pr.get('dit',{}));pr['dit']=dit
    patches=[dit.get(('double_block',i)) for i in range(50)]
    if any(p is None for p in patches): raise ValueError('original 50-block H3 router patches required')
    states={id(p.state) for p in patches}
    if len(states)!=1: raise ValueError('historical patches must share one state')
    old=patches[0].state
    if old.forward_index!=-1 or old.next_block!=0 or old.audit['started_calls']!=0: raise ValueError('only fresh original router state is supported')
    if old.mode not in ('native','mass_preserve'): raise ValueError('unsupported historical method')
    if old.mode=='mass_preserve' and (old.alpha!=.25 or tuple(old.active_steps)!=tuple(range(20))): raise ValueError('only original full weak .25 schedule')
    state=copy.deepcopy(old)
    state.forward_index=step-1
    state.path=Path(outdir)/'router_replay.json'
    state.audit['run_id']='passive_replay_step'+str(step)
    state.audit['calls_by_forward']=[0]*step;state.audit['routed_by_forward']=[0]*step
    state.audit['replay']={'historical_step_zero_based':step,'physical_model_calls_expected':1,'leading_zero_counters_are_skipped_not_executed':True}
    state.audit['status']='replay_armed'
    for i,p in enumerate(patches):
        new=copy.copy(p);new.state=state;dit[('double_block',i)]=new
    return result,state


def prepared_layout(guider):
    pos=guider.conds.get('positive',[])
    if len(pos)!=1 or guider.conds.get('negative'):raise ValueError('one BasicGuider positive condition required')
    condition=pos[0]['model_conds']['minimax_payload']
    payload=condition.cond
    return payload['layout'],payload

class HistoricalOneForward:
    def __init__(self,state_file,state_sha,old_x0_file,old_x0_sha,output_dir,*,capture_on,valid_frames,expected_method,case="cpu_fixture"):
        if file_sha(state_file)!=state_sha or file_sha(old_x0_file)!=old_x0_sha:raise ValueError('replay input file identity mismatch')
        self.state=torch.load(state_file,map_location='cpu',weights_only=True)
        self.old=torch.load(old_x0_file,map_location='cpu',weights_only=True)
        self.expected_method=expected_method;self.case=case
        self.step=self.state['step_zero_based'];self.capture_on=capture_on;self.valid_frames=valid_frames
        if self.step not in (9,19) or self.old['metadata']['step_zero_based']!=self.step:raise ValueError('actual historical step mismatch')
        if self.state['historical_x0_file_sha256']!=old_x0_sha:raise ValueError('state/denoised identity mismatch')
        self.out=Path(output_dir);self.out.mkdir(parents=True,exist_ok=False)
        self.calls=0;self.record={};self.raw_result=None
        self.input_identity={'state_file_sha256':state_sha,'old_x0_file_sha256':old_x0_sha,'historical_capture_manifest_sha256':self.state['manifest_sha256'],'packed_x':tensor_info(self.state['packed_x'])}

    def __call__(self,model_k,initial_x,sigmas,extra_args=None,callback=None,disable=None,**kw):
        if self.calls:raise RuntimeError('finite replay sampler cannot be reused')
        self.calls+=1
        extra_args={} if extra_args is None else dict(extra_args)
        if extra_args.get('denoise_mask') is not None:raise ValueError('no denoise mask in frozen replay')
        # Actual KSAMPLER always supplies its internal k_callback, even when
        # the outer callback is None. A finite forward never invokes it.
        if kw:raise ValueError('unverified sampler extra options')
        exact=sigma_grid(self.state['sigmas_video'])
        if not torch.equal(sigmas.cpu(),exact):raise ValueError('complete historical21sigma grid must be preserved')
        if tensor_info(initial_x)['sha256']!=self.state['noise_sha256']:raise ValueError('original initial noise not preserved through KSAMPLER')
        guider=model_k.inner_model;base=guider.inner_model
        if guider.cfg!=1.0 or float(base.audio_scale())!=4 or float(base.model_sampling.noise_scale)!=1:raise ValueError('historical CFG/AV/noise settings mismatch')
        if [list(s) for s in base.latent_shapes]!=self.state['shapes']:raise ValueError('full AV geometry mismatch')
        to=extra_args['model_options']['transformer_options']
        if not torch.equal(to['sample_sigmas'].cpu(),exact):raise ValueError('model full sigma schedule differs')
        options,router=arm_router_options(extra_args['model_options'],self.step,self.out)
        expected_mode={'native':'native','global_weak':'mass_preserve'}[self.expected_method]
        if router.mode!=expected_mode:raise ValueError('actual router method differs from frozen control')
        extra_args['model_options']=options
        layout,payload=prepared_layout(guider)
        shapes=self.state['shapes'];probes=ProbeLayout.from_actual(layout,shapes[0],self.valid_frames)
        if float(payload['audio_scale'])!=4 or int(payload['seed'])!=self.old['metadata']['seed']:raise ValueError('conditioning scale/seed mismatch')
        model=base.diffusion_model
        if len(model.blocks)!=50:raise ValueError('H3 block count differs')
        if (model.blocks[25].attn.heads,model.blocks[25].attn.head_dim)!=(56,128):raise ValueError('H3 actual attention geometry differs')
        x=self.state['packed_x'].to(initial_x.device,dtype=torch.float32,copy=True)
        before=tensor_info(x)
        sigma=sigmas[self.step]*x.new_ones([x.shape[0]])
        cap=None
        if self.capture_on:
            cap=PassiveQKCapture(model.blocks[25].attn,probes,step=self.step,layer=25,
                                 in_training=__import__("comfy.model_management",fromlist=["in_training"]).in_training)
            with cap: result=model_k(x,sigma,**extra_args)
        else:result=model_k(x,sigma,**extra_args)
        if tensor_info(x)!=before:raise ValueError('model changed sampler input in place')
        if result.shape!=x.shape or result.dtype!=torch.float32 or not bool(torch.isfinite(result).all()):raise ValueError('invalid full raw denoised result')
        if router.forward_index!=self.step or router.audit['completed_forward_calls']!=1 or router.audit['completed_calls']!=50:raise ValueError('historical indexing or single-forward audit failed')
        self.raw_result=result.detach().to('cpu',copy=True).contiguous()
        rv,ra=unpack(self.raw_result,shapes)
        self.normalized={'video':rv.clone(),'audio':ra*.25}
        self.record={'schema':'h3-finite-historical-forward-v1','input_identity':self.input_identity,'step_zero_based':self.step,'sigma_video':float(sigmas[self.step]),'full_sigmas_preserved':True,'capture_on':self.capture_on,'physical_model_calls':1,'raw_denoised':tensor_info(self.raw_result),'normalized_denoised':{k:tensor_info(v) for k,v in self.normalized.items()},'router_completed_blocks':50,'raw_audio_uses_video_schedule':True,'normalization_applied_only_to_saved_comparison_copy':'audio /4'}
        torch.save({'raw_packed_x0':self.raw_result,**self.normalized,'metadata':self.record},self.out/'denoised.pt')
        if cap:
            cap.data['case']=self.case;cap.data['method']=self.expected_method
            cap.data['forward_identity']=self.record['input_identity']
            cap.data['sample_sigmas_video']=exact.double().tolist()
            cap.data['sigma_video']=float(sigmas[self.step])
            self.record['capture_tensor_signatures']=cap.save(self.out/'qk.pt')
        (self.out/'FORWARD.json').write_text(json.dumps(self.record,indent=2,allow_nan=False)+'\n')
        return result


def verify_pair(off,on,old):
    result={'schema':'h3-finite-replay-gates-v1','passed':True,'streams':{}}
    for name in ('video','audio'):
        a,b,c=off[name],on[name],old[name]
        if a.shape!=c.shape or b.shape!=c.shape or any(t.dtype!=torch.float32 for t in (a,b,c)) or not all(bool(torch.isfinite(t).all()) for t in (a,b,c)):
            raise ValueError('stream shape/dtype/finite mismatch')
        exact=torch.equal(a,b)
        # Strict passive gate: raw equality checked by caller and every normalized element here.
        delta=(a.double()-c.double()).reshape(-1);rms=max(float(c.double().square().mean().sqrt()),1e-8)
        scores={'hook_exact_equal':exact,'old_rms':rms,'nrmse':float(delta.square().mean().sqrt())/rms,'p99_abs_over_old_rms':float(torch.quantile(delta.abs(),.99))/rms,'max_abs_over_old_rms':float(delta.abs().max())/rms}
        scores['historical_pass']=scores['nrmse']<=1e-4 and scores['p99_abs_over_old_rms']<=1e-3 and scores['max_abs_over_old_rms']<=1e-2
        result['streams'][name]=scores;result['passed'] &= exact and scores['historical_pass']
    return result
