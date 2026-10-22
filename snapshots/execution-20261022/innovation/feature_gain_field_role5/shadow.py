"""Read-only diagnostic summaries; separate step-zero anchors, no QP or gains."""
import torch

STEPS=(0,9,19)
LAYERS=(8,25,42)


def summarize_shadow(A,B,count,*,state,step,layer,coordinates,relative_floor=1e-8):
    if any(x.device.type!='cpu' or x.ndim!=1 for x in (A,B,count,coordinates)):
        raise ValueError('shadow requires explicit CPU vectors')
    if not (A.shape==B.shape==count.shape==coordinates.shape):
        raise ValueError('shadow vector lengths differ')
    A,B,count,coordinates=[x.detach().double() for x in (A,B,count,coordinates)]
    n=len(A);tiny=torch.finfo(torch.float64).tiny
    if state is not None:
        if state['layer']!=layer or not torch.equal(state['coordinates'],coordinates):
            raise ValueError('shadow geometry/layer changed')
        if step<=state['last_step']:raise ValueError('shadow step out of order')
        A0=state['A0'].clone();B0=state['B0'].clone();anchored=state['anchored'].clone()
    else:
        A0=torch.ones(n,dtype=torch.float64);B0=A0.clone();anchored=torch.zeros(n,dtype=torch.bool)
    valid=torch.isfinite(A)&torch.isfinite(B)&torch.isfinite(count)&(A>=0)&(B>=0)&(count>0)
    scale=torch.maximum(A,B)
    eligible=valid&(scale>tiny)&(A>relative_floor*scale)&(B>relative_floor*scale)
    if step==0:
        anchored=eligible;A0=torch.where(anchored,A,A0);B0=torch.where(anchored,B,B0)
    available=anchored&valid&(scale>relative_floor*torch.maximum(A0,B0))
    at=A/A0;bn=B/B0;total=(at+bn).clamp_min(tiny)
    report={'temporal_energy':A.clone(),'complement_energy':B.clone(),'valid_probe_count':count.clone(),
            'raw_temporal_share':torch.where(valid,A/(A+B).clamp_min(tiny),0.),
            'anchor_temporal':A0.clone(),'anchor_complement':B0.clone(),
            'anchor_step':torch.where(anchored,0,-1),'usable_anchor':available,
            'normalized_temporal':torch.where(available,at/total,0.),
            'normalized_complement':torch.where(available,bn/total,0.),
            'normalization_scope':'diagnostic step-zero +/-1 anchors only; no control update'}
    next_state={'A0':A0.clone(),'B0':B0.clone(),'anchored':anchored.clone(),'coordinates':coordinates.clone(),
                'layer':layer,'last_step':step}
    return report,next_state
