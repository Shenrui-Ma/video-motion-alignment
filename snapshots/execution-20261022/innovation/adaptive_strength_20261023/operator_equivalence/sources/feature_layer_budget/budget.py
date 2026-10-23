"""Causal layer allocation in a previous-step local pre-Wo energy metric."""
import math
import torch


def allocate_layers(quality,relative_energy,evidence,*,alpha_prior=.25,alpha_max=.5):
    """CPU water filling for max sum e*u*a under sum e*a² <= prior² sum e.

    Ineligible layers remain at prior and do not enter the redistributed budget.
    No timing or current/future model state is inspected by this pure function.
    """
    if not all(isinstance(x,torch.Tensor) and x.device.type=='cpu' and x.ndim==1
               for x in (quality,relative_energy,evidence)):
        raise ValueError('CPU layer vectors required')
    if quality.shape!=relative_energy.shape or quality.shape!=evidence.shape or not len(quality):
        raise ValueError('matching nonempty vectors required')
    if not 0<=alpha_prior<=alpha_max<=1 or not all(math.isfinite(v) for v in (alpha_prior,alpha_max)):
        raise ValueError('invalid prior/cap')
    u,e=quality.double(),relative_energy.double()
    valid=evidence.bool()&torch.isfinite(u)&torch.isfinite(e)&(u>=0)&(u<=1)&(e>0)
    alpha=torch.full_like(e,alpha_prior)
    ids=valid.nonzero().flatten().tolist()
    reason='allocated';iterations=0;scale=1.;normalized_target=0.;multiplier=None
    if not ids:reason='no_eligible_layers'
    elif alpha_prior==0 or alpha_max==0:reason='zero_budget'
    elif all(float(u[i])==float(u[ids[0]]) for i in ids):
        reason='uniform_quality_prior' if float(u[ids[0]])>0 else 'zero_quality_prior'
    else:
        scale=max(float(e[i]) for i in ids)
        weights={i:float(e[i])/scale for i in ids}
        normalized_target=alpha_prior**2*math.fsum(weights.values())
        # At zero quality, spending energy has zero objective improvement.
        # The deterministic optimum chooses zero there, and may underspend.
        alpha[valid]=0.
        free=[i for i in ids if float(u[i])>0];saturated=[]
        for iterations in range(1,len(ids)+2):
            residual=max(0.,normalized_target-alpha_max**2*math.fsum(weights[i] for i in saturated))
            denom=math.fsum(weights[i]*float(u[i])**2 for i in free)
            if not free or denom<=0:
                reason='positive_quality_cap_limited';break
            multiplier=math.sqrt(residual/denom)
            hits=[i for i in free if multiplier*float(u[i])>alpha_max]
            if not hits:
                for i in free:alpha[i]=multiplier*float(u[i])
                break
            for i in hits:alpha[i]=alpha_max
            saturated.extend(hits);free=[i for i in free if i not in hits]
        else:raise RuntimeError('water-filling finite active-set bound exceeded')
    safe_e=torch.where(torch.isfinite(e)&(e>0),e,0.)
    target=alpha_prior**2*safe_e[valid].sum()
    assigned=(safe_e[valid]*alpha[valid].square()).sum()
    all_target=alpha_prior**2*safe_e.sum()
    all_assigned=(safe_e*alpha.square()).sum()
    return alpha,{
        'eligible':valid,'quality':torch.where(torch.isfinite(u),u,0.),
        'relative_energy':safe_e,'alpha':alpha.clone(),'reason':reason,'iterations':iterations,
        'eligible_target':target,'eligible_assigned':assigned,
        'eligible_budget_ratio':float(assigned/target) if float(target)>0 else None,
        'all_target':all_target,'all_assigned':all_assigned,
        'predicted_budget_ratio':float(all_assigned/all_target) if float(all_target)>0 else None,
        'energy_normalization':scale,'waterfill_multiplier':multiplier,
        'scope':'previous completed step; pre-Wo local relative correction energy',
        'zero_quality_rule':'uniform zero falls back to prior; otherwise zero-utility layers may receive zero'}


def budget_measure(energy,alpha,*,alpha_prior=.25):
    """Explicitly report undefined zero-energy ratios instead of fabricating one."""
    energy=torch.as_tensor(energy,dtype=torch.float64,device='cpu')
    alpha=torch.as_tensor(alpha,dtype=torch.float64,device='cpu')
    if energy.shape!=alpha.shape or energy.ndim!=1:raise ValueError('matching vectors required')
    if not bool((torch.isfinite(energy)&(energy>=0)&torch.isfinite(alpha)&(alpha>=0)).all()):
        raise ValueError('finite nonnegative budget inputs required')
    target=alpha_prior**2*energy.sum();actual=(energy*alpha.square()).sum()
    return {'baseline':float(target),'executed':float(actual),
        'ratio':float(actual/target) if float(target)>0 else None}
