"""Radial dose normalization using the current forward's full-resolution energy."""
import math
import sys
import time

import torch


def solve_radial(candidate, energy, mask, *, prior=.25, cap=.5, energy_floor=0.):
    """Small CPU scalar solve; inputs are finite Python lists, no model calls.

    Solve in log(c) so positive subnormal candidates do not underflow when
    squared and c need not be representable as one finite float. An impossible
    positive-energy support falls back explicitly to the fixed prior.
    """
    n=len(candidate)
    if n==0 or len(energy)!=n or len(mask)!=n or any(type(x) is not bool for x in mask):
        raise ValueError('matching nonempty vectors and boolean mask required')
    if mask[0] or mask[-1] or prior!=.25 or cap!=.5:
        raise ValueError('frozen endpoints/prior/cap required')
    if not math.isfinite(energy_floor) or energy_floor<0:
        raise ValueError('invalid energy floor')
    if any(not math.isfinite(a) or not 0<=a<=cap for a in candidate):
        raise ValueError('invalid candidate')
    if any(not math.isfinite(e) or e<0 for e in energy):
        raise ValueError('invalid energy')
    if any(not m and a!=prior for a,m in zip(candidate,mask)):
        raise ValueError('nonmodifiable candidate changed')
    try: total=math.fsum(energy)
    except OverflowError as exc: raise ValueError('nonfinite total energy reduction') from exc
    if not math.isfinite(total):raise ValueError('nonfinite total energy reduction')
    selected=math.fsum(e for e,m in zip(energy,mask) if m)
    target=prior*prior
    log_cap=math.log(cap)
    support=[i for i,(a,e,m) in enumerate(zip(candidate,energy,mask)) if m and e>0 and a>0]
    reason=None;log_scale=None;iterations=0;method='fixed_prior_fallback';normalized_residual=0.
    weights=[e/selected if m and selected>0 else 0. for e,m in zip(energy,mask)]
    capacity=cap*cap*math.fsum(weights[i] for i in support)
    if not any(mask):reason='no_modifiable_bins'
    elif selected<=energy_floor:reason='near_zero_energy'
    elif not support:reason='zero_candidate_support'
    elif capacity<target:reason='insufficient_positive_support'
    applied=[prior]*n
    if reason is None:
        logs={i:math.log(candidate[i]) for i in support}
        def values(log_c):
            result=[]
            for a,m in zip(candidate,mask):
                if not m:result.append(prior)
                elif a==0:result.append(0.)
                else:
                    z=math.log(a)+log_c
                    result.append(cap if z>=log_cap else math.exp(z))
            return result
        def dose(values_):return math.fsum(w*a*a for w,a in zip(weights,values_))
        # Log-sum-exp avoids squaring tiny but positive candidates to zero.
        terms=[math.log(weights[i])+2*logs[i] for i in support if weights[i]>0]
        high=max(terms)
        log_den=high+math.log(math.fsum(math.exp(x-high) for x in terms))
        analytic=.5*(math.log(target)-log_den)
        guess=values(analytic)
        if all(logs[i]+analytic<=log_cap for i in support):
            log_scale=analytic;applied=guess;method='uncapped_closed_form'
        else:
            lower=analytic;upper=max(log_cap-logs[i] for i in support)
            if lower>upper+1e-12:raise ArithmeticError('invalid scalar bracket')
            lower=min(lower,upper)
            # A capped piecewise quadratic is continuous and monotone in c.
            # 96 iterations bound any finite FP64 log bracket to roundoff.
            for iterations in range(1,97):
                mid=(lower+upper)/2
                if mid==lower or mid==upper:break
                if dose(values(mid))<target:lower=mid
                else:upper=mid
            log_scale=(lower+upper)/2;applied=values(log_scale);method='bounded_log_bisection'
        normalized_residual=dose(applied)-target
        if abs(normalized_residual)>2e-13:
            raise ArithmeticError('radial scalar solve did not meet energy target')
    scale=None if log_scale is None or log_scale>math.log(sys.float_info.max) else math.exp(log_scale)
    return applied,{'solver':method,'iterations':iterations,'log_scale':log_scale,'scale':scale,
        'scale_representation':'log_scale' if log_scale is not None and scale is None else 'float64',
        'fallback_reason':reason,'fallback_to_prior':reason is not None,
        'normalized_target':target,'normalized_positive_support_capacity':capacity,
        'normalized_solver_residual':normalized_residual,'energy_floor':energy_floor,
        'modifiable_energy':selected,'target_modifiable_energy':target*selected,
        'target_total_energy':target*total,'source_total_energy':total,
        'zero_candidate_with_positive_energy':sum(m and e>0 and a==0 for a,e,m in zip(candidate,energy,mask)),
        'no_modifiable_bins':not any(mask)}


@torch.no_grad()
def fixed_budget_alpha(candidate, bin_energy, modifiable, *, prior=.25, cap=.5):
    """Return radial coefficients on the input device; only 2×T stats move to CPU."""
    if candidate.ndim!=1 or bin_energy.shape!=candidate.shape or candidate.numel()==0:
        raise ValueError('matching nonempty candidate/energy required')
    if candidate.dtype not in (torch.float32,torch.float64) or candidate.dtype!=bin_energy.dtype:
        raise ValueError('matching FP32/FP64 statistics required')
    if candidate.device!=bin_energy.device or modifiable.shape!=candidate.shape or modifiable.dtype!=torch.bool:
        raise ValueError('incompatible statistics device/mask')
    start=time.perf_counter()
    stats=torch.stack((candidate,bin_energy)).to(device='cpu',dtype=torch.float64)
    mask=modifiable.detach().cpu().tolist()
    transfer_seconds=time.perf_counter()-start
    start=time.perf_counter()
    raw,info=solve_radial(stats[0].tolist(),stats[1].tolist(),mask,prior=prior,cap=cap,
        energy_floor=torch.finfo(candidate.dtype).tiny)
    solver_seconds=time.perf_counter()-start
    # Measure the source-dtype rounding before upload so energy audit describes
    # the actual coefficients, rather than the unrounded CPU root.
    rounded=torch.tensor(raw,dtype=candidate.dtype)
    a=stats[0];e=stats[1];applied64=rounded.double();selected=torch.tensor(mask,dtype=torch.bool)
    candidate_total=float((e*a.square()).sum());actual_total=float((e*applied64.square()).sum())
    target=info['target_total_energy'];relative=(actual_total-target)/target if target>0 else 0.
    if not math.isfinite(actual_total) or abs(relative)>3e-7:
        raise ArithmeticError('rounded alpha violates same-forward fixed energy budget')
    info.update(modifiable_mask=mask,candidate_alpha=a.tolist(),applied_alpha=applied64.tolist(),
        candidate_modifiable_energy=float((e[selected]*a[selected].square()).sum()),
        applied_modifiable_energy=float((e[selected]*applied64[selected].square()).sum()),
        candidate_total_energy=candidate_total,applied_total_energy=actual_total,
        energy_error=actual_total-target,energy_relative_error=relative,
        cap_mask=[m and x==cap for m,x in zip(mask,raw)],
        accumulation_dtype='float64',applied_dtype=str(candidate.dtype),
        statistics_transfer_seconds=transfer_seconds,statistics_transfer_bytes=stats.numel()*stats.element_size(),
        solver_cpu_seconds=solver_seconds,
        scope='same-forward full-resolution pre-W_o correction matched to fixed .25; not another trajectory',
        qp_scope='candidate only; applied coefficients follow capped radial normalization')
    return rounded.to(device=candidate.device),info
