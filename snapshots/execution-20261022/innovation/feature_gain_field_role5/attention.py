"""Single-forward, reference-mass preserving temporal-feature guidance."""
import math
import time
from dataclasses import dataclass, asdict
import torch
from .components import temporal_components
from .controller import update_gain_field, summarize_probe_components
from .frozen import load_frozen
from .shadow import STEPS as SHADOW_STEPS, LAYERS as SHADOW_LAYERS, summarize_shadow


@dataclass(frozen=True)
class FeatureConfig:
    mode: str = 'gain_field'
    alpha_prior: float = .25
    alpha_max: float = .5
    prior_weight: float = 1.
    smoothness: float = .625
    probes: int = 8
    basis: str = 'centered'
    relative_floor: float = 1e-8

    def __post_init__(self):
        if self.mode not in ('fixed','gain_field'):
            raise ValueError('unknown feature-guidance mode')
        if not 0 <= self.alpha_prior <= self.alpha_max <= 1:
            raise ValueError('invalid alpha prior/cap')
        if self.mode == 'gain_field' and (self.alpha_prior != .25 or self.alpha_max != .5):
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


def neighbor_indices(lo,hi,device=None):
    """Use +/-5 only with a complete neighborhood inside the existing window."""
    bins=torch.arange(lo,hi,device=device)
    role5=(bins>=lo+5)&(bins<hi-5)
    radius=torch.where(role5,5,1)
    return (bins-radius).clamp_min(lo),(bins+radius).clamp_max(hi-1),role5


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
                      controller_state=None,controller_state_out=None,step_index=0,layer_index=0,
                      shadow_state=None,shadow_state_out=None,shadow_enabled=True):
    validate(q,k,v,heads,plan)
    full,full_lse=attention(q,k,v)
    record={'attention_calls':1,'shadow_attention_calls':0,'applied':False,'mode':config.mode}
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
        previous_ids,following_ids,role5=neighbor_indices(lo,hi,q.device)
        previous=neighbor(previous_ids);following=neighbor(following_ids)
        seam_bins=sorted({x for x in (lo+4,lo+5,hi-6,hi-5) if lo<=x<hi}) if t>=11 else []
        record.update(neighbor_previous=previous_ids.detach(),neighbor_following=following_ids.detach(),
                      role5_mask=role5.detach(),seam_bin_indices=seam_bins,
                      tangent_operator='same-position-role +/-5 interior; original +/-1 boundary')
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
        if shadow_enabled and step_index in SHADOW_STEPS and layer_index in SHADOW_LAYERS and t>=11:
            shadow_started=time.perf_counter()
            # Same Q/D/m/probes; only reference K/V indices differ. Shadow is
            # masked to the common interior and never enters the main QP/state.
            p1=neighbor((bins-1).clamp_min(lo));n1=neighbor((bins+1).clamp_max(hi-1))
            z=temporal_components(sp,rp,p1,n1,mp*role5[None,:,None],
                                  basis='centered',relative_signal_floor=config.relative_floor)
            sa,sb,sn=summarize_probe_components(z)
            ss=torch.stack((sa,sb,sn.to(sa.dtype))).to(device='cpu',dtype=torch.float64)
            shadow,shadow_next=summarize_shadow(ss[0],ss[1],ss[2],state=shadow_state,
                step=step_index,layer=layer_index,coordinates=torch.arange(lo,hi,dtype=torch.float64),
                relative_floor=config.relative_floor)
            shadow.update(common_interior_half_open=[lo+5,hi-5],
                          same_query_correction_mass_probes=True,
                          source_operator='original +/-1 diagnostic only',
                          actual_operator='same-role +/-5',
                          actual_control_source='control arrays at common interior indices',
                          statistics_transfer_bytes=ss.numel()*ss.element_size())
            record.update(shadow=shadow,shadow_attention_calls=2,
                          shadow_diagnostic_host_seconds=time.perf_counter()-shadow_started)
            if shadow_state_out is not None:shadow_state_out['next_state']=shadow_next
        record['seam_statistics']=[{'bin':b,'role5':lo+5<=b<hi-5,
            **{key:control[key][b-lo] for key in ('temporal_energy','complement_energy','valid_probe_count',
                 'anchor_temporal','anchor_complement','normalized_temporal','fallback_to_prior')},
            'alpha':value[b-lo].to(dtype=dtype)} for b in seam_bins]
    correction_energy=head_energy.sum()
    applied_energy=(alpha.square()*bin_energy).sum()
    correction_view.mul_(alpha[None,None,:,None,None])
    correction.add_(full[:,:,qa:qb].to(dtype))
    changed=correction.to(full.dtype)
    finite=torch.isfinite(changed).all()
    full[:,:,qa:qb].copy_(changed)
    record.update(applied=True,alpha=alpha.detach(),control=control,
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
            self.config=feature_config;self.feature_pending=[];self.anchors={};self.shadow_anchors={}
            super().__init__(*args,**kwargs)
            self.audit.update(schema='h3-temporal-gain-field-role5-v1',feature_config=asdict(feature_config),
                feature_forward_summaries=[],full_dit_forward_calls_added=0,intermediate_vae_decode_calls=0,
                frozen_periodic_temporal_readout=False,
                controller_signal='same-query reference Value temporal tangent; not pixel or pose features',
                alpha_scope='per-layer/step/video-time-bin vector; shared over heads and spatial queries',
                metric_scope='same-time correction before output projection; per-bin anchor from interior probe temporal/complement energies')
            self.audit['effective_collateral'] = ((1-feature_config.alpha_prior)/feature_config.alpha_prior
                if feature_config.alpha_prior > 0 else None)
            self.audit['anchor_rule'] = 'per-run/per-layer/per-bin first valid step; that bin uses alpha_prior; no future-step statistics'
            self.audit['ambient_dimension_calibration'] = False
            self.audit['gain_field_geometry'] = 'uniform latent-bin coordinates; no RGB frame duration reweighting'
            self.audit['box_qp'] = {'lower':0.,'upper':.5,'collateral':3.,'smoothness':feature_config.smoothness,
                'solver':'bounded primal-feasible active set / tridiagonal Thomas'}
            self.audit['temporal_boundary_rule'] = 'selected-valid-window endpoints and no-evidence bins fixed to alpha_prior; smoothing edges cut'
            self.audit['role5_rule']='complete +/-5 neighborhood uses same-position-role tangent; other bins retain +/-1; endpoint and QP topology unchanged'
            self.audit['role5_effect_scope']='joint intervention on position-role matching and temporal span; not isolated causal proof of encoding-role bias'
            self.audit['shadow_schedule']={'steps':list(SHADOW_STEPS),'layers':list(SHADOW_LAYERS),
                'scope':'same Q/D/m/probes; common +/-5 interior only; independent step-zero +/-1 anchors; no control effect'}
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
            record={};active=state.selected(self.block);state_update={};shadow_update={}
            out=feature_attention(q,k,v,heads,self.plan,attention=core.flash_attention_lse,
                aligned_attention=core._aligned_attention,config=state.config,enabled=active,diagnostics=record,
                controller_state=state.anchors.get(self.block),controller_state_out=state_update,
                step_index=state.forward_index,layer_index=self.block,
                shadow_state=state.shadow_anchors.get(self.block),shadow_state_out=shadow_update)
            if 'next_state' in state_update:
                state.anchors[self.block]=state_update['next_state']
            if 'next_state' in shadow_update:
                state.shadow_anchors[self.block]=shadow_update['next_state']
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
