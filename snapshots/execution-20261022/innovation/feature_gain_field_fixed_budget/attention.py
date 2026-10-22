"""Single-forward, reference-mass preserving temporal-feature guidance."""
import math
import time
from dataclasses import dataclass, asdict
import torch
from .components import temporal_components
from .controller import update_gain_field, summarize_probe_components
from .budget import fixed_budget_alpha
from .frozen import load_frozen


@dataclass(frozen=True)
class FeatureConfig:
    mode: str = 'gain_field_fixed_budget'
    alpha_prior: float = .25
    alpha_max: float = .5
    prior_weight: float = 1.
    smoothness: float = .625
    probes: int = 8
    basis: str = 'centered'
    relative_floor: float = 1e-8

    def __post_init__(self):
        if self.mode not in ('fixed','gain_field_fixed_budget'):
            raise ValueError('unknown feature-guidance mode')
        if not 0 <= self.alpha_prior <= self.alpha_max <= 1:
            raise ValueError('invalid alpha prior/cap')
        if self.mode == 'gain_field_fixed_budget' and (self.alpha_prior != .25 or self.alpha_max != .5):
            raise ValueError('gain_field requires frozen alpha_prior=.25 and alpha_max=.5')
        if not all(math.isfinite(x) and x >= 0 for x in (self.prior_weight,self.smoothness)):
            raise ValueError('invalid objective weights')
        if type(self.probes) is not int or not 1 <= self.probes <= 32:
            raise ValueError('probes must be an integer in [1,32]')
        if self.basis != 'centered':
            raise ValueError('gain field requires rank-one centered tangent')
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
                      controller_state=None,controller_state_out=None,step_index=0,layer_index=0):
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
    # Energy is measured at full resolution, before W_o, for each video bin.
    correction_view=correction.reshape(1,heads,t,s,d)
    bin_energy=torch.linalg.vector_norm(correction_view,dim=(0,1,3,4)).square()
    alpha=torch.full((t,),config.alpha_prior,device=q.device,dtype=dtype)
    control={}
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
        # Endpoints keep the fixed prior; no smoothing edge crosses them.
        mp[:,0,:]=0
        mp[:,-1,:]=0
        started=time.perf_counter()
        components=temporal_components(sp,rp,previous,following,mp,
            basis='centered',relative_signal_floor=config.relative_floor)
        aa,bb,nn=summarize_probe_components(components)
        transfer_started=time.perf_counter()
        # One explicit small device-to-host transfer of 3 x T sufficient stats.
        # This may synchronize the current stream; report it separately.
        cpu_stats=torch.stack((aa,bb,nn.to(aa.dtype))).to(device='cpu',dtype=torch.float64)
        record['statistics_transfer_seconds']=time.perf_counter()-transfer_started
        solver_started=time.perf_counter()
        value,next_state,control=update_gain_field(cpu_stats[0],cpu_stats[1],cpu_stats[2],
            state=controller_state,step_index=step_index,layer_index=layer_index,
            prior_weight=config.prior_weight,smoothness=config.smoothness,
            relative_floor=config.relative_floor,
            bin_coordinates=torch.arange(lo,hi,dtype=torch.float64))
        record['controller_cpu_seconds']=time.perf_counter()-solver_started
        record['statistics_transfer_bytes']=cpu_stats.numel()*cpu_stats.element_size()
        # Per-bin gain is shared by every head and spatial token in that bin.
        alpha=value.to(device=q.device,dtype=dtype)
        if controller_state_out is not None:
            controller_state_out['next_state']=next_state
        record['controller_host_dispatch_seconds']=time.perf_counter()-started
        record['probe_indices']=ids.detach()
        record['boundary_probes_excluded']=True
    candidate_alpha=alpha.clone()
    budget_control={}
    if config.mode!='fixed':
        started=time.perf_counter()
        alpha,budget_control=fixed_budget_alpha(candidate_alpha,bin_energy,
            control['solver_succeeded'],prior=config.alpha_prior,cap=config.alpha_max)
        record['budget_host_dispatch_seconds']=time.perf_counter()-started
    correction_energy=bin_energy.to(torch.float64).sum()
    applied_energy=(alpha.to(torch.float64).square()*bin_energy.to(torch.float64)).sum()
    correction_view.mul_(alpha[None,None,:,None,None])
    correction.add_(full[:,:,qa:qb].to(dtype))
    changed=correction.to(full.dtype)
    finite=torch.isfinite(changed).all()
    full[:,:,qa:qb].copy_(changed)
    record.update(applied=True,alpha=alpha.detach(),candidate_alpha=candidate_alpha.detach(),
        fixed_budget=budget_control,control=control,
        head_energy=head_energy.detach(),bin_energy=bin_energy.detach(),
        latent_bin_indices=list(range(lo,hi)),reference_mass_mean=mass.mean().detach(),
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
            self.audit.update(schema='h3-temporal-gain-field-fixed-budget-v1',feature_config=asdict(feature_config),
                feature_forward_summaries=[],full_dit_forward_calls_added=0,intermediate_vae_decode_calls=0,
                frozen_periodic_temporal_readout=False,
                controller_signal='same-query reference Value temporal tangent; not pixel or pose features',
                alpha_scope='capped common radial scaling of candidate time gains per layer/step; all other bins fixed .25',
                metric_scope='same-forward full-resolution pre-W_o correction energy matched to fixed alpha .25')
            self.audit['effective_collateral'] = ((1-feature_config.alpha_prior)/feature_config.alpha_prior
                if feature_config.alpha_prior > 0 else None)
            self.audit['anchor_rule'] = 'per-run/per-layer/per-bin first valid step; that bin uses alpha_prior; no future-step statistics'
            self.audit['ambient_dimension_calibration'] = False
            self.audit['gain_field_geometry'] = 'uniform latent-bin coordinates; no RGB frame duration reweighting'
            self.audit['box_qp'] = {'lower':0.,'upper':.5,'collateral':3.,'smoothness':feature_config.smoothness,
                'solver':'bounded primal-feasible active set / tridiagonal Thomas'}
            self.audit['temporal_boundary_rule'] = 'selected-valid-window endpoints and no-evidence bins fixed to alpha_prior; smoothing edges cut'
            self.audit['fixed_budget_rule'] = 'sum E_t*clip(c*a_candidate_t,0,.5)^2 = .25^2*sum E_t on solver_succeeded bins; candidate QP unchanged'
            self.audit['qp_applies_to'] = 'candidate_alpha only; applied alpha is the fixed-energy capped radial ablation'
            self.audit['independent_field_trajectory_energy_matched'] = False
            self.write()
        def finish_forward(self):
            records=[]
            for block,pending in self.feature_pending:
                row=serial(pending);row.update(block=block,forward=self.forward_index)
                if not row.get('finite_output',True):raise FloatingPointError('nonfinite feature-guidance output')
                if row.get('applied'):
                    aa=row['alpha'];row.update(alpha_mean=sum(aa)/len(aa),alpha_min=min(aa),alpha_max=max(aa))
                records.append(row)
            self.feature_pending.clear()
            self.audit['feature_forward_summaries'].append({'forward':self.forward_index,'layers':records})
            super().finish_forward()
    class Override:
        def __init__(self,state,plan,block):self.state,self.plan,self.block,self.calls=state,plan,block,0
        def __call__(self,native,q,k,v,heads,**kwargs):
            if getattr(native,'__name__',None)!='attention_pytorch' or kwargs.get('mask') is not None or not kwargs.get('skip_reshape') or kwargs.get('skip_output_reshape',False):
                raise ValueError('requires unmasked preshaped attention_pytorch')
            self.calls+=1
            if self.calls!=1:raise ValueError('expected one attention call per block')
            state=self.state
            expected=state.audit.get('expected_sampling_steps',20)
            if state.forward_index >= expected:
                raise ValueError('gain-field MODEL state already consumed; create a new per-run node state')
            record={};active=state.selected(self.block);state_update={}
            out=feature_attention(q,k,v,heads,self.plan,attention=core.flash_attention_lse,
                aligned_attention=core._aligned_attention,config=state.config,enabled=active,diagnostics=record,
                controller_state=state.anchors.get(self.block),controller_state_out=state_update,
                step_index=state.forward_index,layer_index=self.block)
            if 'next_state' in state_update:
                state.anchors[self.block]=state_update['next_state']
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
