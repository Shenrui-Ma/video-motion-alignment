"""Existing fixed same-bin readout with phase alignment inside that branch only."""
import math
from .core import (_aligned_attention, _bounded_stats, flash_attention_lse,
                   route_attention, temporal_readout)
from .reference_origin import ReferenceOriginState, ReferenceOriginBlockPatch


def combined_attention(q,k,v,heads,plan,rotation,*,alpha=1.0,radius=0,time_offset=0,
                       attention=flash_attention_lse,diagnostics=None):
    """O + alpha*m_ref*(z_same_bin(phase(Q),K,V) - z_all_ref(Q,K,V))."""
    if (not math.isfinite(alpha) or not 0<=alpha<=1 or radius!=0 or time_offset!=0
            or q.ndim!=4 or q.shape!=k.shape or q.shape!=v.shape or q.shape[0]!=1
            or q.shape[1]!=heads or q.shape[-1]!=128
            or any(x.device!=q.device or x.dtype!=q.dtype for x in (k,v))):
        raise ValueError('requires original single-video same-bin H3 inputs')
    if alpha==0:
        return route_attention(q,k,v,heads,plan,mode='native',attention=attention)
    if rotation.displacement==0:
        return route_attention(q,k,v,heads,plan,mode='mass_preserve',alpha=alpha,
                               radius=0,time_offset=0,attention=attention,diagnostics=diagnostics)
    qa,qb=plan['query_interval_half_open'];ra,rb=plan['reference_video_segment'];va,vb=plan['target_video_segment']
    if not (0<=ra<rb<=q.shape[-2] and 0<=va<=qa<qb<=vb<=q.shape[-2]):
        raise ValueError('selected query/reference interval is invalid')
    # Both mass terms and the subtracted all-reference readout use unmodified Q.
    full,full_lse=attention(q,k,v)
    query,keys,values=q[:,:,qa:qb],k[:,:,ra:rb],v[:,:,ra:rb]
    original,ref_lse=attention(query,keys,values)
    log_mass=ref_lse.float()-full_lse[:,:,qa:qb].float()
    mass=log_mass.clamp(max=0).exp()  # Exactly the existing fixed router arithmetic.
    local,_=_aligned_attention(rotation(query),keys,values,
        latent_lo=plan['latent_interval_half_open'][0],frame_rows=plan['frame_rows'],
        radius=0,time_offset=0,attention=attention)
    before=full[:,:,qa:qb]
    changed=(before.float()+alpha*mass.unsqueeze(-1)*(local.float()-original.float())).to(before.dtype)
    if diagnostics is not None:diagnostics.append(_bounded_stats(before,changed,mass,log_mass))
    full[:,:,qa:qb].copy_(changed)
    return full.transpose(1,2).reshape(1,q.shape[-2],heads*q.shape[-1])


class CombinedState(ReferenceOriginState):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.audit['combined_fixed_phase']={
            'formula':'O + alpha*m_ref*(z_local_shifted_Q - z_original_allRef)',
            'original_mass_and_allRef_readout':True,'single_correction':True,
            'local_reference_selection':'existing same-bin radius0/time_offset0',
            'original_QKV_positions_and_RoPE_table_preserved':True,
            'phase_source':'actual reference_origin minus target_origin',
            'local_shifted_calls':0,'phase_zero_equals_existing_fixed':True,
            'alpha_zero_equals_native':True}
        self.write()


class CombinedAttentionOverride:
    def __init__(self,state,plan,block):
        self.state,self.plan,self.block,self.calls=state,plan,block,0

    def __call__(self,native,q,k,v,heads,**kwargs):
        if getattr(native,'__name__',None)!='attention_pytorch':raise ValueError('native entry differs')
        if kwargs.get('mask') is not None or not kwargs.get('skip_reshape') or kwargs.get('skip_output_reshape',False):
            raise ValueError('requires original unmasked preshaped attention')
        if q.shape[-2]!=self.plan['seq_len']:raise ValueError('packed sequence changed')
        self.calls+=1
        if self.calls!=1:raise ValueError('one attention per block required')
        state=self.state
        if self.block==25 and state.forward_index in (0,5,10,15,19):
            record=temporal_readout(q,k,self.plan)
            record.update(block_index=self.block,forward_index=state.forward_index)
            state.audit['temporal_readouts'].append(record)
        stats=[]
        if state.selected(self.block) and state.alpha!=0:
            out=combined_attention(q,k,v,heads,self.plan,state.rotation,alpha=state.alpha,
                                   radius=state.radius,time_offset=state.time_offset,diagnostics=stats)
            state.audit['routed_calls']+=1
            state.audit['routed_by_block'][self.block]+=1
            state.audit['routed_by_forward'][state.forward_index]+=1
            state.audit['reference_origin']['rotation_calls']+=1
            state.audit['combined_fixed_phase']['local_shifted_calls']+=1
        else:out=route_attention(q,k,v,heads,self.plan,mode='native')
        state.audit['native_override_calls']+=1
        if stats:state.pending_stats.append((self.block,stats[0]))
        if 'first_attention' not in state.audit:
            state.audit['first_attention']={'qkv_shape':list(q.shape),'dtype':str(q.dtype),
                'device':str(q.device),'heads':heads,'flash_lse':True,'returned_shape':list(out.shape)}
        return out


class CombinedBlockPatch(ReferenceOriginBlockPatch):
    override_class=CombinedAttentionOverride
