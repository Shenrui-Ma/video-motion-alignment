"""Remove time allocation while matching this forward's pre-W_o energy."""
import torch


@torch.no_grad()
def uniform_energy_alpha(candidate, bin_energy, modifiable, *, prior=.25, cap=.5):
    """Full-resolution energy-weighted RMS over successfully solved bins.

    Endpoints, first anchors, unsupported bins and failed-QP bins retain prior.
    This operates on the current run's candidate, not a different field run.
    """
    if candidate.ndim != 1 or candidate.numel() == 0 or bin_energy.shape != candidate.shape:
        raise ValueError('matching nonempty alpha/energy vectors required')
    if candidate.device != bin_energy.device or candidate.dtype != bin_energy.dtype:
        raise ValueError('alpha and energy dtype/device mismatch')
    if candidate.dtype not in (torch.float32,torch.float64):
        raise ValueError('FP32/FP64 correction statistics required')
    if modifiable.shape != candidate.shape or modifiable.dtype != torch.bool:
        raise ValueError('boolean per-bin mask required')
    if bool(modifiable[0]) or bool(modifiable[-1]):
        raise ValueError('endpoints must remain fixed')
    if prior != .25 or cap != .5:
        raise ValueError('frozen prior/cap required')
    mask=modifiable.to(device=candidate.device)
    a=candidate.to(torch.float64);e=bin_energy.to(torch.float64)
    # Finite elements alone do not imply a finite FP64 aggregate. Reject this
    # explicitly instead of letting inf denominators silently set b to zero.
    finite=torch.isfinite(a).all() & torch.isfinite(e).all() & (e>=0).all() & torch.isfinite(e.sum())
    bounds=((a>=0)&(a<=cap)).all()
    fixed_prior=torch.where(~mask,a==prior,True).all()
    if not bool(finite & bounds & fixed_prior):
        raise ValueError('invalid candidate/energy, nonfinite energy reduction, or nonmodifiable bin changed')
    selected_energy=torch.where(mask,e,0.)
    denominator=selected_energy.sum()
    numerator=(selected_energy*a.square()).sum()
    # FP64 accumulation avoids FP32 reduction overflow. This floor only protects
    # the source statistic's normal/subnormal boundary; it is not a tuned gate.
    floor=torch.finfo(candidate.dtype).tiny
    energy_ok=denominator>floor
    safe_denominator=torch.where(energy_ok,denominator,torch.ones_like(denominator))
    b=(numerator/safe_denominator).clamp(0.,cap*cap).sqrt()
    b=torch.where(energy_ok,b,torch.full_like(b,prior)).to(candidate.dtype)
    applied=torch.where(mask,b,torch.full_like(candidate,prior))
    applied64=applied.to(torch.float64)
    candidate_total=(e*a.square()).sum()
    applied_total=(e*applied64.square()).sum()
    error=applied_total-candidate_total
    relative=torch.where(candidate_total>0,error/candidate_total.clamp_min(torch.finfo(torch.float64).tiny),torch.zeros_like(error))
    return applied,{
        'modifiable_mask':mask.detach(),'uniform_alpha':b.detach(),
        'candidate_alpha':candidate.detach().clone(),'applied_alpha':applied.detach().clone(),
        'modifiable_energy':denominator.detach(),'candidate_modifiable_energy':numerator.detach(),
        'applied_modifiable_energy':(selected_energy*applied64.square()).sum().detach(),
        'candidate_total_energy':candidate_total.detach(),'applied_total_energy':applied_total.detach(),
        'energy_error':error.detach(),'energy_relative_error':relative.detach(),
        'energy_floor':floor,'near_zero_energy_fallback':(~energy_ok).detach(),
        'no_modifiable_bins':(~mask.any()).detach(),
        'accumulation_dtype':'float64','applied_dtype':str(candidate.dtype),
        'scope':'same-forward full-resolution pre-W_o correction; not another trajectory',
        'qp_scope':'candidate only; applied uniform gain is not asserted to solve the QP',
    }
