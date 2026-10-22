"""Offline algebra prototypes. No Comfy hooks, weights, queues or GPU launch.

These functions assume an explicitly supplied linear effective output weight.
They do not claim to reproduce a dynamically quantized Comfy operator.
"""
import math
import torch


def projected_head_features(delta,weight,sketch=None):
    """delta[P,H,D], linear weight[O,H*D] -> per-head effects[P,H,O or K]."""
    if delta.ndim!=3 or weight.ndim!=2 or weight.shape[1]!=delta.shape[1]*delta.shape[2]:
        raise ValueError('expected delta[P,H,D] and weight[O,H*D]')
    if delta.device!=weight.device or delta.dtype!=weight.dtype:
        raise ValueError('device/dtype mismatch')
    h,d=delta.shape[1:]
    effective=weight
    if sketch is not None:
        if sketch.ndim!=2 or sketch.shape[0]!=weight.shape[0]:raise ValueError('sketch[O,K] required')
        effective=(weight.T@sketch).T
    blocks=effective.reshape(effective.shape[0],h,d).permute(1,0,2)
    return torch.einsum('phd,hod->pho',delta,blocks)


def gram(features,probe_weights=None):
    """PSD head Gram on shared output-coordinate probes."""
    if features.ndim!=3:raise ValueError('features[P,H,O] required')
    if probe_weights is not None:
        if probe_weights.shape!=(features.shape[0],) or not bool((probe_weights>=0).all()):
            raise ValueError('nonnegative probe weights[P] required')
        features=features*probe_weights.sqrt()[:,None,None]
    return torch.einsum('pho,pgo->hg',features,features)


def ray_budget_guard(candidate,G,*,alpha_prior=.25,alpha_max=.5,diagonal_slack=1.,near_null=1e-6):
    """Conservative feasibility filter; NOT a full constrained optimizer.

    Clip the candidate, then reduce its common scale to obey both post-Wo and
    non-cancelled diagonal budgets. Nearly cancelled baseline -> fixed prior.
    The budget is exact for the supplied G (a probe/sketch in future use), not
    automatically for all full-resolution queries or a quantized operator.
    """
    if G.ndim!=2 or G.shape[0]!=G.shape[1] or candidate.shape!=(G.shape[0],):
        raise ValueError('candidate[H], Gram[H,H] required')
    if not 0<=alpha_prior<=alpha_max<=1 or diagonal_slack<1 or near_null<0:
        raise ValueError('invalid budget settings')
    G=(G+G.T)/2
    if not bool(torch.isfinite(G).all()&torch.isfinite(candidate).all()):raise ValueError('finite inputs required')
    eigenvalues=torch.linalg.eigvalsh(G)
    if float(eigenvalues.min()) < -1e-9*max(1.,float(G.diagonal().abs().max())):
        raise ValueError('Gram must be positive semidefinite')
    base=torch.full_like(candidate,alpha_prior)
    diagonal=G.diagonal().clamp_min(0)
    post_budget=(base@G@base).clamp_min(0)
    diagonal_budget=diagonal_slack*(diagonal*base.square()).sum()
    baseline_near_null=post_budget<=near_null*diagonal_budget
    if bool(baseline_near_null):
        return base,{'fallback_near_null':True,'post_budget':post_budget,
                     'diagonal_budget':diagonal_budget,'scale':torch.ones((),dtype=G.dtype,device=G.device)}
    x=candidate.clamp(0,alpha_max)
    post=(x@G@x).clamp_min(0);unmixed=(diagonal*x.square()).sum()
    tiny=torch.finfo(G.dtype).tiny
    scale=torch.minimum(torch.ones_like(post),torch.minimum(
        (post_budget/post.clamp_min(tiny)).sqrt(),(diagonal_budget/unmixed.clamp_min(tiny)).sqrt()))
    x=x*scale
    return x,{'fallback_near_null':False,'post_budget':post_budget,
              'diagonal_budget':diagonal_budget,'scale':scale,
              'actual_post_energy':(x@G@x).clamp_min(0),
              'actual_diagonal_energy':(diagonal*x.square()).sum()}


def projected_scalar_target(temporal,complement,*,alpha_prior=.25,alpha_max=.5,collateral=1.,prior_weight=1.):
    """Cross-term-correct solution of a distinct output-coordinate objective.

    min ||a(T+N)-T||² + collateral*a²*||N||²
                                 + prior_weight*(a-a0)²*||T+N||².
    T,N may no longer be orthogonal after W_o. Diagnostic prototype only.
    """
    A=temporal.square().sum();B=complement.square().sum();K=(temporal*complement).sum()
    C=(temporal+complement).square().sum()
    numerator=A+K+prior_weight*alpha_prior*C
    denominator=(1+prior_weight)*C+collateral*B
    if float(denominator)<=torch.finfo(temporal.dtype).tiny:
        return torch.full_like(A,alpha_prior)
    return (numerator/denominator).clamp(0,alpha_max)
