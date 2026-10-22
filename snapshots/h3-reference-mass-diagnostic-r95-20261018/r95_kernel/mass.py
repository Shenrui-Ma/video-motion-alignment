"""Known reference-group gain controls, prepared for CPU numerical diagnostics.

Only selected output-video queries change. This module supplies a kernel API;
it does not register a Comfy node, schedule a model, or launch a service.
"""
import math
from numbers import Real
from .snapshot import core as parent

MODES = ('reference_group_gain', 'samebin_group_gain')


def _scalar(value, name, *, lower, upper=None, inclusive_lower=True):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f'{name} must be a finite real scalar')
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f'{name} must be finite') from exc
    if not math.isfinite(value) or (value < lower if inclusive_lower else value <= lower) or (upper is not None and value > upper):
        raise ValueError(f'invalid {name}')
    return value


def _summary(before, after, mass, boosted_mass, alpha):
    """Bounded samples on device; statistics describe attention, not motion."""
    import torch
    hs=max(1, math.ceil(before.shape[1]/8));qs=max(1, math.ceil(before.shape[2]/128));ds=max(1, math.ceil(before.shape[3]/16))
    old=before[:,::hs,::qs,::ds].float();new=after[:,::hs,::qs,::ds].float()
    m=mass[:,::hs,::qs].float();mr=boosted_mass[:,::hs,::qs].float()
    delta=new-old; rms=old.square().mean().sqrt();drms=delta.square().mean().sqrt()
    return {
        'ref_mass_mean':m.mean().detach(), 'ref_mass_max':m.max().detach(),
        'boosted_ref_mass_mean':mr.mean().detach(), 'boosted_ref_mass_max':mr.max().detach(),
        'effective_ref_mass_mean':(m+alpha*(mr-m)).mean().detach(),
        'original_rms':rms.detach(), 'written_delta_rms':drms.detach(),
        'written_delta_ratio':(drms/rms.clamp_min(1e-8)).detach(),
        'cast_zero_change_fraction':(delta==0).float().mean().detach(),
        'finite':(torch.isfinite(old).all() & torch.isfinite(new).all() & torch.isfinite(m).all() & torch.isfinite(mr).all()).detach(),
    }


def _fallback(q,k,v,heads,plan,mode,alpha,radius,time_offset,attention,audit):
    legacy=[] if audit is not None else None
    out=parent.route_attention(q,k,v,heads,plan,mode=mode,alpha=alpha,radius=radius,time_offset=time_offset,attention=attention,diagnostics=legacy)
    if audit is not None:
        row={'execution_path':'r85_exact_'+mode,'kernel_formula':'unchanged parent path','additional_attention_calls':0,'stats':None}
        if legacy:
            # Original mass_preserve already measures m and the final cast delta.
            x=legacy[0]
            row['stats']={'ref_mass_mean':x[0],'ref_mass_max':x[1],
                          'boosted_ref_mass_mean':x[0],'boosted_ref_mass_max':x[1],
                          'written_delta_ratio':x[2],'finite':x[3]}
        audit.append(row)
    return out


def route_attention(q,k,v,heads,plan,*,mode='reference_group_gain',reference_gain=1.0,
                    alpha=1.0,radius=0,time_offset=0,
                    attention=parent.flash_attention_lse,audit=None):
    """Blend a group-gain target with native output by alpha in [0,1].

    reference_group_gain: B=[O+(r-1)m*O_ref]/[1+(r-1)m].
    samebin_group_gain:   C=B+m_r*(O_same-O_ref), m_r=r*m/[1+(r-1)m].
    For gain<1, an explicit complement attention avoids cancellation while
    preserving the same mathematical target. Gain=1 and alpha=0 call R85.
    `audit` receives dictionaries of detached, bounded tensor statistics.
    """
    import torch
    if mode not in MODES:raise ValueError('unknown reference mass control mode')
    r=_scalar(reference_gain,'reference_gain',lower=0,inclusive_lower=False)
    alpha=_scalar(alpha,'alpha',lower=0,upper=1)
    if alpha==0:
        return _fallback(q,k,v,heads,plan,'native',0.0,radius,time_offset,attention,audit)
    if r==1:
        oldmode='native' if mode=='reference_group_gain' else 'mass_preserve'
        return _fallback(q,k,v,heads,plan,oldmode,alpha,radius,time_offset,attention,audit)
    if q.ndim!=4 or q.shape!=k.shape or q.shape!=v.shape or q.shape[0]!=1:
        raise ValueError('expected equal single-batch [B,H,N,D] tensors')
    if q.shape[1]!=heads or any(x.device!=q.device or x.dtype!=q.dtype for x in (k,v)):
        raise ValueError('head/device/dtype mismatch')
    if not q.is_floating_point():raise ValueError('attention tensors must be floating point')
    qa,qb=plan['query_interval_half_open'];ra,rb=plan['reference_video_segment']
    if not 0<=qa<qb<=q.shape[-2] or not 0<=ra<rb<=k.shape[-2]:
        raise ValueError('selected ranges exceed packed sequence')
    full,full_lse=attention(q,k,v)
    query=q[:,:,qa:qb];keys=k[:,:,ra:rb];values=v[:,:,ra:rb]
    ref,ref_lse=attention(query,keys,values)
    old=full[:,:,qa:qb]
    work_dtype=torch.float64 if q.dtype==torch.float64 else torch.float32
    log_mass=(ref_lse.to(work_dtype)-full_lse[:,:,qa:qb].to(work_dtype)).clamp(max=0)
    mass=log_mass.exp();log_r=math.log(r)
    aligned=None
    if mode=='samebin_group_gain':
        aligned,_=parent._aligned_attention(query,keys,values,
            latent_lo=plan['latent_interval_half_open'][0],frame_rows=plan['frame_rows'],
            radius=radius,time_offset=time_offset,attention=attention)
    extra=0
    if r>1:
        # Divide by D through log-coefficients. No r tensor can overflow, and
        # very small m can remain usable through log_mass even if exp(m) rounds to zero.
        log_extra=log_mass+math.log(r-1.0)
        log_den=torch.logaddexp(torch.zeros_like(log_extra),log_extra)
        w_old=(-log_den).exp();w_ref=(log_extra-log_den).exp()
        boosted_mass=(log_r+log_mass-log_den).clamp(max=0).exp()
        target=w_old.unsqueeze(-1)*old.to(work_dtype)+w_ref.unsqueeze(-1)*ref.to(work_dtype)
        if aligned is not None:
            target=target+boosted_mass.unsqueeze(-1)*(aligned.to(work_dtype)-ref.to(work_dtype))
        path='positive_gain_log_coefficients'
    else:
        # Subtracting two separately rounded BF16 aggregates can lose the
        # entire non-reference contribution. Recompute that group explicitly.
        if ra==0 and rb==k.shape[-2]:
            boosted_mass=torch.ones_like(mass)
            target=(aligned if aligned is not None else ref).to(work_dtype)
        else:
            other_k=torch.cat((k[:,:,:ra],k[:,:,rb:]),dim=-2)
            other_v=torch.cat((v[:,:,:ra],v[:,:,rb:]),dim=-2)
            other,other_lse=attention(query,other_k,other_v);extra=1
            log_ref=ref_lse.to(work_dtype)+log_r
            den=torch.logaddexp(log_ref,other_lse.to(work_dtype))
            boosted_mass=(log_ref-den).exp();other_mass=(other_lse.to(work_dtype)-den).exp()
            target=other_mass.unsqueeze(-1)*other.to(work_dtype)+boosted_mass.unsqueeze(-1)*(aligned if aligned is not None else ref).to(work_dtype)
        path='gain_below_one_explicit_complement'
    # alpha controls blending with native; it is independent of group gain r.
    changed=(old.to(work_dtype)+alpha*(target-old.to(work_dtype))).to(old.dtype)
    if audit is not None:
        # Measure before writing: old is a view into full.
        audit.append({'execution_path':path,'reference_gain':r,'alpha':alpha,
            'mode':mode,'additional_attention_calls':extra,
            'stats':_summary(old,changed,mass,boosted_mass,alpha),
            'scope':'sampled attention before out_proj/AdaLN gate; boosted mass describes target before alpha blend'})
    full[:,:,qa:qb].copy_(changed)
    return full.transpose(1,2).reshape(1,q.shape[-2],heads*q.shape[-1])
