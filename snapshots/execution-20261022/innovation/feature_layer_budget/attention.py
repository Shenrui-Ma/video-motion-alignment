"""Single-forward, reference-mass preserving temporal-feature guidance."""
import math
import time
from dataclasses import dataclass, asdict
import torch
from .components import temporal_components
from .anchor_controller import anchor_strength_from_energies
from .frozen import load_frozen
from .budget import allocate_layers, budget_measure


@dataclass(frozen=True)
class FeatureConfig:
    mode: str = 'layer_budget'
    alpha_prior: float = .25
    alpha_max: float = .5
    probes: int = 8
    basis: str = 'centered'
    relative_floor: float = 1e-8

    def __post_init__(self):
        if self.mode not in ('fixed','layer_budget'):
            raise ValueError('unknown feature-guidance mode')
        if not 0 <= self.alpha_prior <= self.alpha_max <= 1:
            raise ValueError('invalid alpha prior/cap')
        if self.mode == 'layer_budget' and (self.alpha_prior != .25 or self.alpha_max != .5):
            raise ValueError('layer_budget requires frozen prior=.25 and cap=.5')
        if type(self.probes) is not int or not 1 <= self.probes <= 32:
            raise ValueError('probes must be an integer in [1,32]')
        if self.basis != 'centered':
            raise ValueError('layer budget requires rank-one centered tangent')
        if not math.isfinite(self.relative_floor) or not 0 <= self.relative_floor < 1:
            raise ValueError('invalid relative signal floor')


def packed(x):
    return x.transpose(1,2).reshape(x.shape[0],x.shape[2],-1)


def validate(q,k,v,heads,plan):
    if q.ndim!=4 or q.shape!=k.shape or q.shape!=v.shape or q.shape[0]!=1 or q.shape[1]!=heads:
        raise ValueError('matching single batch [1,H,N,D] QKV required')
    if any(x.device!=q.device or x.dtype!=q.dtype for x in (k,v)):
        raise ValueError('QKV dtype/device mismatch')
    qa,qb=plan['query_interval_half_open'];ra,rb=plan['reference_video_segment'];ta,tb=plan['target_video_segment']
    lo,hi=plan['latent_interval_half_open'];s=plan['frame_rows']
    if type(s)!=int or s<1 or not 0<=ra<rb<=ta<=qa<qb<=tb<=q.shape[2]:
        raise ValueError('invalid disjoint frame layout')
    if (rb-ra)%s or (tb-ta)!=(rb-ra) or not 0<=lo<hi<=(rb-ra)//s or (qa,qb)!=(ta+lo*s,ta+hi*s):
        raise ValueError('incomplete reference/target frames')
    if plan.get('seq_len',q.shape[2])!=q.shape[2]:raise ValueError('packed sequence mismatch')


@torch.no_grad()
def feature_attention(q,k,v,heads,plan,*,attention,aligned_attention,config=FeatureConfig(),enabled=True,diagnostics=None,
                      requested_alpha=None,step_index=0,layer_index=0):
    validate(q,k,v,heads,plan)
    full,full_lse=attention(q,k,v)
    record={'attention_calls':1,'applied':False,'mode':config.mode}
    if not enabled or config.alpha_max==0 or config.alpha_prior==0:
        if diagnostics is not None:diagnostics.update(record)
        return packed(full)
    qa,qb=plan['query_interval_half_open'];ra,rb=plan['reference_video_segment']
    lo,hi=plan['latent_interval_half_open'];s=plan['frame_rows'];t=hi-lo;d=q.shape[-1]
    qe=q[:,:,qa:qb];kr=k[:,:,ra:rb];vr=v[:,:,ra:rb]
    ref,ref_lse=attention(qe,kr,vr);record['attention_calls']+=1
    def counted(a,b,c):
        record['attention_calls']+=1
        out,lse=attention(a,b,c)
        return out,lse.float()
    same,same_lse=aligned_attention(qe,kr,vr,latent_lo=lo,frame_rows=s,radius=0,time_offset=0,attention=counted)
    dtype=torch.float64 if q.dtype==torch.float64 else torch.float32
    # Match the frozen same-time mass-preserving FP32 LSE contract exactly.
    log_mass=ref_lse.float()-full_lse[:,:,qa:qb].float()
    mass=log_mass.clamp(max=0).exp().to(dtype)
    correction=mass.unsqueeze(-1)*(same.to(dtype)-ref.to(dtype))
    # Reduction without a full-size squared temporary keeps the controller's
    # peak memory close to the existing same-time path.
    head_energy=torch.linalg.vector_norm(correction,dim=(0,2,3)).square()
    alpha=torch.full((heads,),config.alpha_prior,device=q.device,dtype=dtype)
    native_energy=torch.linalg.vector_norm(full[:,:,qa:qb].to(dtype)).square()
    correction_energy=head_energy.sum()
    energy_scale=torch.maximum(native_energy,correction_energy)
    tiny=torch.finfo(dtype).tiny
    energy_valid=(torch.isfinite(native_energy)&torch.isfinite(correction_energy)
        &(native_energy>tiny)&(correction_energy>tiny)
        &(native_energy>config.relative_floor*energy_scale))
    relative_energy=torch.where(energy_valid,correction_energy/(native_energy+tiny),torch.zeros_like(native_energy))
    stats=torch.stack((torch.zeros_like(native_energy),torch.zeros_like(native_energy),
        torch.zeros_like(native_energy),correction_energy,native_energy,
        torch.zeros_like(native_energy),relative_energy,energy_valid.to(dtype)))
    if requested_alpha is None:requested_alpha=config.alpha_prior
    if not isinstance(requested_alpha,(int,float)) or not math.isfinite(requested_alpha) or not 0<=requested_alpha<=config.alpha_max:
        raise ValueError('finite frozen layer alpha in [0,alpha_max] required')
    alpha.fill_(requested_alpha)
    if config.mode!='fixed':
        # Fixed stratified probes cover each spatial frame; all attention heads
        # participate. No QK probability grid or intermediate RGB is needed.
        ids=torch.linspace(0,s-1,min(s,config.probes),device=q.device).round().long()
        indices=(torch.arange(t,device=q.device)[:,None]*s+ids[None,:]).flatten()
        nprobe=len(ids)
        probeq=qe.index_select(2,indices).reshape(heads,t,nprobe,d).permute(1,0,2,3).contiguous()
        bins=torch.arange(lo,hi,device=q.device);nt=(rb-ra)//s
        grouped_k=kr[0].reshape(heads,nt,s,d).permute(1,0,2,3)
        grouped_v=vr[0].reshape(heads,nt,s,d).permute(1,0,2,3)
        def neighbor(idx):
            a,_=counted(probeq,grouped_k[idx].contiguous(),grouped_v[idx].contiguous())
            return a.permute(1,0,2,3)
        # The configured valid window can end before padded reference bins.
        # Keep the tangent inside that window rather than observing padding.
        previous=neighbor((bins-1).clamp_min(lo));following=neighbor((bins+1).clamp_max(hi-1))
        sp=same.index_select(2,indices).reshape(heads,t,nprobe,d)
        rp=ref.index_select(2,indices).reshape(heads,t,nprobe,d)
        mp=mass.index_select(2,indices).reshape(heads,t,nprobe).clone()
        # A one-sided endpoint tangent contains S_same itself, biasing its
        # projection energy upward. Estimate alpha only from interior bins;
        # the estimated alpha still acts on the complete selected window.
        mp[:,0,:]=0
        mp[:,-1,:]=0
        started=time.perf_counter()
        components=temporal_components(sp,rp,previous,following,mp,
            basis='centered',relative_signal_floor=config.relative_floor)
        A=components['temporal_energy'].sum();B=components['complement_energy'].sum()
        count=components['valid'].sum().to(dtype)
        signal_valid=(torch.isfinite(A)&torch.isfinite(B)&(A>=0)&(B>=0)&(count>0)
            &(torch.maximum(A,B)>tiny))
        current_valid=signal_valid&energy_valid
        # This local safety fallback does not redistribute unfinished layers.
        alpha=torch.where(current_valid,alpha,torch.full_like(alpha,config.alpha_prior))
        stats=torch.stack((torch.where(signal_valid,A,0.),torch.where(signal_valid,B,0.),count,
            correction_energy,native_energy,current_valid.to(dtype),relative_energy,energy_valid.to(dtype)))
        record['raw_probe_evidence_valid']=signal_valid.detach()
        record['current_evidence_valid']=current_valid.detach()
        record['local_fallback_to_prior']=(~current_valid).detach()
        record['controller_gpu_dispatch_seconds']=time.perf_counter()-started
        record['probe_indices']=ids.detach()
        record['boundary_probes_excluded']=True
    applied_energy=(alpha.square()*head_energy).sum()
    correction.mul_(alpha[None,:,None,None])
    correction.add_(full[:,:,qa:qb].to(dtype))
    changed=correction.to(full.dtype)
    finite=torch.isfinite(changed).all()
    full[:,:,qa:qb].copy_(changed)
    record.update(applied=True,alpha=alpha.detach(),requested_alpha=float(requested_alpha),
        statistics_gpu=stats.detach(),
        head_energy=head_energy.detach(),reference_mass_mean=mass.mean().detach(),
        native_energy=native_energy.detach(),relative_correction_energy=relative_energy.detach(),
        relative_energy_valid=energy_valid.detach(),
        correction_energy=correction_energy.detach(),
        applied_energy=applied_energy.detach(),finite_output=finite.detach())
    if diagnostics is not None:diagnostics.update(record)
    return packed(full)


def serial(value):
    if isinstance(value,torch.Tensor):return value.detach().cpu().tolist()
    if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [serial(v) for v in value]
    return value


def make_classes(core):
    class State(core.RouterState):
        def __init__(self,*args,feature_config,**kwargs):
            self.config=feature_config;self.feature_pending=[];self.anchors={}
            super().__init__(*args,**kwargs)
            self.layer_plan=torch.full((self.num_blocks,),feature_config.alpha_prior,dtype=torch.float64)
            self.plan_source_forward=-1;self.plan_for_forward=0;self.previous_energy=torch.zeros(self.num_blocks,dtype=torch.float64)
            self.audit.update(schema='h3-causal-layer-budget-v1',feature_config=asdict(feature_config),
                feature_forward_summaries=[],layer_budget_summaries=[],
                full_dit_forward_calls_added=0,intermediate_vae_decode_calls=0,
                frozen_periodic_temporal_readout=False,
                controller_signal='same-query reference Value centred temporal tangent',
                alpha_scope='per-layer scalar; fixed from previous completed forward, shared over all selected video bins',
                metric_scope='previous-step pre-Wo local relative correction energy on selected output queries',
                native_energy_scope='selected output queries only, before output projection',
                budget_target='alpha_prior squared times previous-step eligible-layer relative energy',
                current_step_exact_budget_conservation=False,
                anchor_rule='per-run/per-layer first valid step; newly created quality=.5',
                initial_steps='first step fixed prior; first completed anchor qualities=.5 so second step fixed prior',
                temporal_boundary_rule='selected-window endpoints excluded from probe statistics; all bins receive each layer scalar',
                local_fallback_rule='current raw probe or local energy invalid returns prior; old-anchor suitability only changes the next-step plan',
                anchor_suitability_decision_time='after all layers complete; no retroactive change to executed alpha')
            self.write()
        def finish_forward(self):
            if len(self.feature_pending)!=self.num_blocks or [b for b,_ in self.feature_pending]!=list(range(self.num_blocks)):
                raise ValueError('layer allocation requires all ordered blocks of a completed forward')
            started=time.perf_counter()
            present=[(b,r['statistics_gpu']) for b,r in self.feature_pending if 'statistics_gpu' in r]
            # No anchor or next-step allocation is computed until all blocks finish.
            statistics=torch.zeros((self.num_blocks,8),dtype=torch.float64)
            transfer_started=time.perf_counter()
            if present:
                values=torch.stack([v for _,v in present]).to(device='cpu',dtype=torch.float64)
                for (block,_),value in zip(present,values):statistics[block]=value
            transfer_seconds=time.perf_counter()-transfer_started
            quality=torch.full((self.num_blocks,),.5,dtype=torch.float64)
            evidence=torch.zeros(self.num_blocks,dtype=torch.bool)
            actual_alpha=torch.zeros(self.num_blocks,dtype=torch.float64)
            current_energy=torch.zeros(self.num_blocks,dtype=torch.float64)
            records=[]
            for block,pending in self.feature_pending:
                pending.pop('statistics_gpu',None)
                row=serial(pending);row.update(block=block,forward=self.forward_index,
                    plan_source_forward=self.plan_source_forward,plan_for_forward=self.plan_for_forward)
                if not row.get('finite_output',True):raise FloatingPointError('nonfinite layer-budget output')
                if row.get('applied'):
                    aa=row['alpha'];row.update(alpha_mean=sum(aa)/len(aa),alpha_min=min(aa),alpha_max=max(aa))
                    actual_alpha[block]=aa[0]
                    A,B,count,D2,O2,current_valid,e,energy_valid=statistics[block]
                    if bool(energy_valid) and torch.isfinite(e):current_energy[block]=e
                    if self.config.mode=='layer_budget':
                        masked_count=count if bool(current_valid) else torch.zeros_like(count)
                        _,new_anchor,calibration=anchor_strength_from_energies(A,B,masked_count,
                            state=self.anchors.get(block),step_index=self.forward_index,layer_index=block,
                            alpha_prior=self.config.alpha_prior,alpha_max=self.config.alpha_max,
                            prior_weight=1.,relative_floor=self.config.relative_floor)
                        self.anchors[block]=new_anchor
                        anchor_eligible=bool(calibration['anchor_created']|calibration['used_anchor'])
                        eligible=anchor_eligible and bool(current_valid) and float(e)>0
                        evidence[block]=eligible
                        if eligible:
                            quality[block]=.5 if bool(calibration['anchor_created']) else calibration['normalized_temporal']
                        # The anchor utility is reused; its instantaneous alpha is not applied.
                        calibration.pop('alpha');calibration.pop('alpha_unclipped')
                        row['quality_calibration']=serial(calibration)
                        row['current_anchor_evidence_valid']=anchor_eligible
                        row['anchor_low_current_energy']=bool(calibration['low_current_energy'])
                        row['next_plan_eligible']=eligible
                        row['allocation_quality']=float(quality[block]);row['allocation_eligible']=eligible
                records.append(row)
            plan_snapshot=self.layer_plan.clone()
            predicted_plan=budget_measure(self.previous_energy,plan_snapshot,alpha_prior=self.config.alpha_prior)
            predicted_executed=budget_measure(self.previous_energy,actual_alpha,alpha_prior=self.config.alpha_prior)
            observed=budget_measure(current_energy,actual_alpha,alpha_prior=self.config.alpha_prior)
            solver_started=time.perf_counter()
            if self.config.mode=='layer_budget':
                next_plan,allocation=allocate_layers(quality,current_energy,evidence,
                    alpha_prior=self.config.alpha_prior,alpha_max=self.config.alpha_max)
            else:
                next_plan=torch.full_like(self.layer_plan,self.config.alpha_prior)
                allocation={'reason':'fixed_mode','alpha':next_plan,'eligible':evidence}
            solver_seconds=time.perf_counter()-solver_started
            self.audit['layer_budget_summaries'].append(serial({
                'forward':self.forward_index,'plan_source_forward':self.plan_source_forward,
                'plan_for_forward':self.plan_for_forward,'planned_alpha':plan_snapshot,
                'actual_alpha':actual_alpha,'previous_relative_energy':self.previous_energy,
                'current_relative_energy':current_energy,'current_quality':quality,
                'current_eligible':evidence,'predicted_plan_budget':predicted_plan,
                'predicted_executed_budget':predicted_executed,'current_actual_drift':observed,
                'next_plan_for_forward':self.forward_index+1,'next_alpha':next_plan,
                'allocation':allocation,'statistics_transfer_seconds':transfer_seconds,
                'statistics_transfer_bytes':len(present)*8*8,'waterfill_cpu_seconds':solver_seconds,
                'finish_controller_host_seconds':time.perf_counter()-started}))
            self.feature_pending.clear()
            self.audit['feature_forward_summaries'].append({'forward':self.forward_index,'layers':records})
            self.layer_plan=next_plan;self.previous_energy=current_energy
            self.plan_source_forward=self.forward_index;self.plan_for_forward=self.forward_index+1
            super().finish_forward()
    class Override:
        def __init__(self,state,plan,block):self.state,self.plan,self.block,self.calls=state,plan,block,0
        def __call__(self,native,q,k,v,heads,**kwargs):
            if getattr(native,'__name__',None)!='attention_pytorch' or kwargs.get('mask') is not None or not kwargs.get('skip_reshape') or kwargs.get('skip_output_reshape',False):
                raise ValueError('requires unmasked preshaped attention_pytorch')
            self.calls+=1
            if self.calls!=1:raise ValueError('expected one attention call per block')
            state=self.state
            if state.audit.get('status')=='failed':
                raise ValueError('failed layer-budget MODEL state cannot be reused')
            expected=state.audit.get('expected_sampling_steps',20)
            if state.forward_index >= expected:
                raise ValueError('layer-budget MODEL state already consumed; create a new per-run node state')
            if state.plan_for_forward!=state.forward_index or state.plan_source_forward!=state.forward_index-1:
                raise ValueError('layer plan must come from a completed earlier forward')
            record={};active=state.selected(self.block)
            out=feature_attention(q,k,v,heads,self.plan,attention=core.flash_attention_lse,
                aligned_attention=core._aligned_attention,config=state.config,enabled=active,diagnostics=record,
                requested_alpha=float(state.layer_plan[self.block]),
                step_index=state.forward_index,layer_index=self.block)
            state.audit['native_override_calls']+=1
            if 'first_attention' not in state.audit:
                state.audit['first_attention'] = {'qkv_shape':list(q.shape), 'dtype':str(q.dtype),
                    'device':str(q.device), 'heads':heads, 'returned_shape':list(out.shape), 'flash_lse':True}
            if record['applied']:
                state.audit['routed_calls']+=1;state.audit['routed_by_block'][self.block]+=1
                state.audit['routed_by_forward'][state.forward_index]+=1
            state.feature_pending.append((self.block,record))
            return out
    class Block(core.EventBlockPatch):override_class=Override
    return State,Block


def attach(model,positive,*,config,start_frame,end_frame,step_start,step_end,block_start,block_end,run_id,audit_dir):
    import comfy.ldm.minimax.model as h3
    core=load_frozen().core;diffusion=model.get_model_object('diffusion_model')
    if not isinstance(diffusion,h3.MiniMaxH3Model) or len(diffusion.blocks)!=50 or tuple(h3.FRAME_PER_TOKEN)!=(1,4,4,4,4):
        raise ValueError('expected frozen H3 geometry and 50 blocks')
    if getattr(h3.optimized_attention,'__name__',None)!='attention_pytorch':raise ValueError('requires native attention_pytorch')
    options=model.model_options.get('transformer_options',{})
    if options.get('patches_replace',{}).get('dit') or options.get('optimized_attention_override'):raise ValueError('existing patch not composable')
    state_class,block_class=make_classes(core)
    state=state_class(core.conditioning_metadata(positive),'mass_preserve',config.alpha_prior,0,0,
        start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir,feature_config=config)
    clone=model.clone()
    for i in range(50):clone.set_model_patch_replace(block_class(state,i),'dit','double_block',i)
    return clone
