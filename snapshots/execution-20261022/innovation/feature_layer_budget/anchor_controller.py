"""Causal, per-layer anchor calibration of existing attention probe energies.

No model, decoder, scheduling, hidden CPU transfer, or cross-run global state.
All tensor diagnostics remain on the energy inputs' device.
"""
import math
import torch


@torch.no_grad()
def anchor_strength_from_energies(temporal_energy, complement_energy, valid_probe_count,
                                 *, state=None, step_index, layer_index,
                                 alpha_prior=.25, alpha_max=.5, prior_weight=1.,
                                 relative_floor=1e-8):
    """Return ``(alpha, next_state, diagnostics)`` without mutating ``state``.

    The first valid step anchors A0/B0 and emits alpha_prior. Later calls solve
      (1-a)^2 vt + c*a^2*vn + mu*(a-a0)^2*(vt+vn)/2,
    where vt=A/A0, vn=B/B0 and c=(1-a0)/a0. Scalar state belongs to exactly
    one layer and one run. Each call must have a strictly increasing step.
    """
    if type(step_index) is not int or step_index < 0 or type(layer_index) is not int or layer_index < 0:
        raise ValueError('nonnegative integer step_index/layer_index required')
    if not all(math.isfinite(x) for x in (alpha_prior, alpha_max, prior_weight, relative_floor)):
        raise ValueError('finite controller settings required')
    if not 0 <= alpha_prior <= alpha_max <= 1 or prior_weight < 0 or not 0 <= relative_floor < 1:
        raise ValueError('invalid prior, cap, regularizer or floor')
    if not all(isinstance(x, torch.Tensor) and x.ndim == 0 and x.is_floating_point()
               for x in (temporal_energy, complement_energy)):
        raise ValueError('energies must be floating scalar tensors')
    if temporal_energy.device != complement_energy.device:
        raise ValueError('energies must share a device')
    device=temporal_energy.device
    dtype=torch.float64 if torch.float64 in (temporal_energy.dtype, complement_energy.dtype) else torch.float32
    A,B=(x.detach().to(dtype) for x in (temporal_energy,complement_energy))
    count=torch.as_tensor(valid_probe_count,device=device)
    if count.ndim != 0 or count.dtype == torch.bool:
        raise ValueError('valid_probe_count must be a numeric scalar')
    settings=(float(alpha_prior),float(alpha_max),float(prior_weight),float(relative_floor))
    if state is None:
        old_A,old_B=torch.ones_like(A),torch.ones_like(B)
        initialized=torch.zeros((),device=device,dtype=torch.bool)
        anchor_step=torch.full((),-1,device=device,dtype=torch.int64)
    else:
        if state['layer_index'] != layer_index or state['settings'] != settings:
            raise ValueError('state layer or controller settings changed')
        if step_index <= state['last_step']:
            raise ValueError('duplicate or out-of-order layer step')
        old_A,old_B=state['anchor_temporal'],state['anchor_complement']
        initialized,anchor_step=state['initialized'],state['anchor_step']
        for x in (old_A,old_B,initialized,anchor_step):
            if x.ndim != 0 or x.device != device:
                raise ValueError('state tensor shape/device changed')
        if old_A.dtype != dtype or old_B.dtype != dtype:
            raise ValueError('energy precision changed within a layer run')
    tiny=torch.finfo(dtype).tiny
    inputs_valid=(torch.isfinite(A)&torch.isfinite(B)&(A>=0)&(B>=0)
                  &torch.isfinite(count)&(count>0))
    safe_A=torch.where(inputs_valid,A,torch.zeros_like(A))
    safe_B=torch.where(inputs_valid,B,torch.zeros_like(B))
    scale=torch.maximum(safe_A,safe_B)
    prior=torch.full_like(A,alpha_prior)
    enabled=alpha_prior>0 and alpha_max>0
    # Both anchor components must be identified. A missing direction must not
    # be turned into a tiny denominator and an artificial saturated ratio.
    can_anchor=(inputs_valid&(scale>tiny)&(safe_A>relative_floor*scale)
                &(safe_B>relative_floor*scale)&enabled)
    created=(~initialized)&can_anchor
    anchor_A=torch.where(created,safe_A,old_A)
    anchor_B=torch.where(created,safe_B,old_B)
    next_initialized=initialized|created
    next_anchor_step=torch.where(created,torch.full_like(anchor_step,step_index),anchor_step)
    anchor_scale=torch.maximum(anchor_A,anchor_B).clamp_min(tiny)
    adequate_current=(scale>tiny)&(scale>relative_floor*anchor_scale)
    used=initialized&inputs_valid&adequate_current&enabled
    # vt/vn are homogeneous in the closed form. Cross products after separate
    # normalization avoid overflow in A/A0 when the layer's scale changes.
    # These are vt and vn multiplied by the SAME positive scalar.
    current_scale=scale.clamp_min(tiny)
    vt=(safe_A/current_scale)*(anchor_B/anchor_scale)
    vn=(safe_B/current_scale)*(anchor_A/anchor_scale)
    norm=(vt+vn).clamp_min(tiny)
    vt,vn=vt/norm,vn/norm
    variance=(vt+vn)/2
    collateral=(1-alpha_prior)/alpha_prior if enabled else 0.
    denominator=vt+collateral*vn+prior_weight*variance
    numerator=vt+prior_weight*alpha_prior*variance
    candidate=numerator/denominator.clamp_min(tiny)
    candidate_finite=torch.isfinite(candidate)
    used=used&candidate_finite
    alpha=torch.where(used,candidate.clamp(0,alpha_max),prior)
    next_state={'anchor_temporal':anchor_A.detach().clone(),
                'anchor_complement':anchor_B.detach().clone(),
                'initialized':next_initialized.detach().clone(),
                'anchor_step':next_anchor_step.detach().clone(),
                'last_step':step_index,'layer_index':layer_index,'settings':settings}
    diagnostics={
        'alpha':alpha.detach(), 'alpha_unclipped':torch.where(used,candidate,prior).detach(),
        'temporal_energy':safe_A.detach(),'complement_energy':safe_B.detach(),
        'valid_probe_count':torch.where(torch.isfinite(count)&(count>0),count,torch.zeros_like(count)).detach(), 'inputs_valid':inputs_valid.detach(),
        'normalized_temporal':vt.detach(),'normalized_complement':vn.detach(),
        'anchor_temporal':torch.where(next_initialized,anchor_A,torch.zeros_like(A)).detach(),
        'anchor_complement':torch.where(next_initialized,anchor_B,torch.zeros_like(B)).detach(),
        'anchor_step':next_anchor_step.detach(),'anchor_created':created.detach(),
        'initialized':next_initialized.detach(),'used_anchor':used.detach(),
        'fallback':((~used)&(~created)).detach(),
        'low_current_energy':(~adequate_current).detach(),
        'effective_collateral':collateral,'prior_weight':prior_weight,
        'step_index':step_index,'layer_index':layer_index,
        'calibration':'first-valid-step temporal/complement energy ratio',
        'normalized_energy_definition':'vt,vn divided by their common sum; same objective minimizer'}
    return alpha,next_state,diagnostics
