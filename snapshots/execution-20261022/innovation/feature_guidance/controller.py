"""Small, inference-only temporal-feature controllers; no VAE or pose model.

All inputs are [H, T, P, D] fixed attention probes. ``mass`` is [H,T,P].
Outputs and diagnostics stay on the input device; there are no .item() calls.
This module neither edits a model nor schedules any experiment.
"""
import math
import torch


def _validate(same, reference, previous, following, mass):
    if same.ndim != 4 or any(x.shape != same.shape for x in (reference, previous, following)):
        raise ValueError("features must share [head,time,probe,channel] shape")
    if mass.shape != same.shape[:-1]:
        raise ValueError("reference mass must be [head,time,probe]")
    if any(x.device != same.device for x in (reference, previous, following, mass)):
        raise ValueError("all tensors must share a device")


@torch.no_grad()
def temporal_components(same, reference, previous, following, mass, *,
                        basis="centered", ridge=1e-6, relative_signal_floor=1e-8):
    """Split the existing same-time correction by local reference-time variation.

    The default tangent following-previous excludes the target same-time value.
    ``temporal`` means variation along this feature tangent, not pure motion.
    The complement is not assumed to be an appearance/identity subspace.
    """
    _validate(same, reference, previous, following, mass)
    if basis not in ("centered", "secants") or ridge <= 0 or relative_signal_floor < 0:
        raise ValueError("invalid projection configuration")
    dtype = torch.float64 if same.dtype == torch.float64 else torch.float32
    xs = [x.to(dtype) for x in (same, reference, previous, following)]
    valid = torch.stack([torch.isfinite(x).all(-1) for x in xs]).all(0)
    # A zero mass also serves as the caller's explicit statistics mask. It must
    # not count as a valid probe when endpoints/padding are excluded.
    valid &= torch.isfinite(mass) & (mass > 0) & (mass <= 1)
    s, r, p, n = [torch.nan_to_num(x, nan=0., posinf=0., neginf=0.) for x in xs]
    m = torch.nan_to_num(mass.to(dtype), nan=0., posinf=0., neginf=0.).clamp(0, 1)
    e = s - r
    tangent = n - p
    scale = (s.square().mean(-1) + r.square().mean(-1)
             + p.square().mean(-1) + n.square().mean(-1)) / 4
    floor = torch.finfo(dtype).tiny
    if basis == "centered":
        t2 = tangent.square().sum(-1)
        projected = tangent * ((e * tangent).sum(-1) / t2.clamp_min(floor)).unsqueeze(-1)
        signal = t2 / same.shape[-1]
    else:
        # Ridge-stabilized 2x2 Gram inverse; this is an explicitly different ablation.
        a, b = s - p, n - s
        aa, ab, bb = a.square().sum(-1), (a * b).sum(-1), b.square().sum(-1)
        reg = ridge * (aa + bb).clamp_min(floor)
        ga, gb = aa + reg, bb + reg
        ea, eb = (e * a).sum(-1), (e * b).sum(-1)
        det = (ga * gb - ab.square()).clamp_min(floor)
        x, y = (gb * ea - ab * eb) / det, (ga * eb - ab * ea) / det
        projected = a * x.unsqueeze(-1) + b * y.unsqueeze(-1)
        signal = (aa + bb) / same.shape[-1]
    valid &= signal > relative_signal_floor * scale.clamp_min(floor)
    valid &= torch.isfinite(projected).all(-1)
    d = m.unsqueeze(-1) * e
    dt = m.unsqueeze(-1) * projected
    dn = d - dt
    # Invalid probes are excluded from controller sufficient statistics. The
    # caller still keeps the original same-time path as its numerical fallback.
    energies = {"total_energy": d.square().sum(-1),
                "temporal_energy": dt.square().sum(-1),
                "complement_energy": dn.square().sum(-1)}
    energies = {k: torch.where(valid, v, torch.zeros_like(v)) for k, v in energies.items()}
    return {**energies, "valid": valid, "input_finite": torch.stack([
        torch.isfinite(x).all(-1) for x in xs]).all(0) & torch.isfinite(mass),
        "tangent_signal": signal, "feature_scale": scale}


def _config(alpha_prior, alpha_max):
    if not all(math.isfinite(x) for x in (alpha_prior, alpha_max)):
        raise ValueError("finite coefficients required")
    if not 0 <= alpha_prior <= alpha_max <= 1:
        raise ValueError("require 0 <= alpha_prior <= alpha_max <= 1")


@torch.no_grad()
def dynamic_strength(same, reference, previous, following, mass, *,
                     alpha_prior=.25, alpha_max=.5, collateral=1., prior_weight=1.,
                     reduction="block", basis="centered", ridge=1e-6,
                     relative_signal_floor=1e-8):
    """Regularized scalar fit of temporal feature correction versus collateral.

    argmin_a (1-a)^2 E_T + collateral*a^2 E_N
                  + prior_weight*(a-alpha_prior)^2 E_D, 0<=a<=alpha_max.
    ``block`` returns a scalar per invocation; ``head_bin`` returns [H,T].
    No reliable probes returns the fixed alpha_prior. A zero prior/max disables.
    """
    _config(alpha_prior, alpha_max)
    if reduction not in ("block", "head_bin"):
        raise ValueError("unknown reduction")
    if not all(math.isfinite(x) and x >= 0 for x in (collateral, prior_weight)):
        raise ValueError("nonnegative finite regularizers required")
    z = temporal_components(same, reference, previous, following, mass, basis=basis,
                            ridge=ridge, relative_signal_floor=relative_signal_floor)
    dims = (0, 1, 2) if reduction == "block" else (2,)
    et, en, ed = [z[k].sum(dims) for k in ("temporal_energy", "complement_energy", "total_energy")]
    numerator = et + prior_weight * alpha_prior * ed
    denominator = et + collateral * en + prior_weight * ed
    informative = (denominator > torch.finfo(denominator.dtype).tiny) & z["valid"].any(dims)
    alpha = torch.where(informative, numerator / denominator.clamp_min(torch.finfo(denominator.dtype).tiny),
                        torch.full_like(denominator, alpha_prior)).clamp(0, alpha_max)
    return {"alpha": alpha, "valid_probe_count": z["valid"].sum(dims),
            "fallback": ~informative, "temporal_energy": et, "complement_energy": en,
            "total_energy": ed, "objective_at_prior": ((1-alpha_prior)**2 * et + collateral*alpha_prior**2 * en),
            "objective_at_selected": ((1-alpha)**2 * et + collateral*alpha.square()*en
                                      + prior_weight*(alpha-alpha_prior).square()*ed),
            "basis": basis}


@torch.no_grad()
def dynamic_strength_dof(same, reference, previous, following, mass, *,
                         alpha_prior=.25, alpha_max=.5, prior_weight=1.,
                         reduction="block", relative_signal_floor=1e-8):
    """Dimension-calibrated version with the same-time prior as isotropic null.

    Rank-one tangent: minimize (1-a)^2 E_T + c*a^2 E_N/(D-1)
    + mu*(a-a0)^2 E_D/D, with c=(1-a0)/a0.
    If temporal and complementary variance per degree of freedom agree,
    a*=a0 exactly. This removes high feature dimensionality as a suppression bias.
    """
    _config(alpha_prior, alpha_max)
    if reduction not in ("block", "head_bin") or not math.isfinite(prior_weight) or prior_weight < 0:
        raise ValueError("invalid controller configuration")
    if alpha_prior == 0:
        return dynamic_strength(same, reference, previous, following, mass,
                                alpha_prior=0, alpha_max=0, reduction=reduction)
    z = temporal_components(same, reference, previous, following, mass,
                            basis="centered", relative_signal_floor=relative_signal_floor)
    dims = (0, 1, 2) if reduction == "block" else (2,)
    et, en, ed = [z[k].sum(dims) for k in ("temporal_energy", "complement_energy", "total_energy")]
    dim = same.shape[-1]
    temporal_variance = et
    complement_variance = en / max(1, dim - 1)
    overall_variance = ed / dim
    collateral = (1-alpha_prior) / alpha_prior
    denominator = temporal_variance + collateral*complement_variance + prior_weight*overall_variance
    numerator = temporal_variance + prior_weight*alpha_prior*overall_variance
    informative = (denominator > torch.finfo(denominator.dtype).tiny) & z["valid"].any(dims)
    informative &= dim > 1
    alpha = torch.where(informative, numerator/denominator.clamp_min(torch.finfo(denominator.dtype).tiny),
                        torch.full_like(denominator,alpha_prior)).clamp(0,alpha_max)
    return {"alpha":alpha,"fallback":~informative,"valid_probe_count":z["valid"].sum(dims),
            "temporal_energy":et,"complement_energy":en,"total_energy":ed,
            "temporal_variance":temporal_variance,"complement_variance":complement_variance,
            "overall_variance":overall_variance,"feature_dimension":dim,
            "basis":"centered", "calibration":"equal_variance_per_degree_of_freedom",
            "objective_at_prior":(1-alpha_prior)**2*temporal_variance+collateral*alpha_prior**2*complement_variance,
            "objective_at_selected":(1-alpha)**2*temporal_variance+collateral*alpha.square()*complement_variance
                +prior_weight*(alpha-alpha_prior).square()*overall_variance}


@torch.no_grad()
def allocate_energy_budget(temporal_fraction, exact_head_energy, *,
                           alpha_prior=.25, alpha_max=.5):
    """Maximize linear temporal utility with a fixed correction L2 budget.

    max sum_h E_h*f_h*a_h subject sum_h E_h*a_h^2 =
    alpha_prior^2 sum_h E_h and 0<=a_h<=alpha_max. KKT gives a_h=min(tau*f_h,amax).
    Zero-utility heads receive residual budget only if positive heads saturate.
    With no reliable utility, the optimum is degenerate: use the fixed prior.
    """
    _config(alpha_prior, alpha_max)
    if temporal_fraction.ndim != 1 or temporal_fraction.shape != exact_head_energy.shape:
        raise ValueError("head utility and energy must be matching vectors")
    dtype = torch.float64 if exact_head_energy.dtype == torch.float64 else torch.float32
    e = exact_head_energy.to(dtype)
    u = temporal_fraction.to(dtype)
    finite = torch.isfinite(e).all() & torch.isfinite(u).all() & (e >= 0).all()
    e = torch.nan_to_num(e, nan=0., posinf=0., neginf=0.).clamp_min(0)
    u = torch.nan_to_num(u, nan=0., posinf=0., neginf=0.).clamp(0, 1)
    positive = (u > 0) & (e > 0)
    budget = alpha_prior**2 * e.sum()
    capacity = alpha_max**2 * torch.where(positive, e, 0).sum()
    zero_energy = torch.where(~positive, e, 0).sum()
    tiny = torch.finfo(dtype).tiny
    # Enumerate H possible saturated prefixes. This exact water-filling form
    # avoids an iterative solve and remains accurate for disparate utilities.
    order = u.argsort(descending=True)
    us, es = u[order], e[order]
    saturated = alpha_max**2 * (es.cumsum(0) - es)
    weighted = es * us.square()
    unsaturated = weighted.flip(0).cumsum(0).flip(0)
    taus = ((budget - saturated).clamp_min(0) / unsaturated.clamp_min(tiny)).sqrt()
    previous = torch.cat((torch.ones_like(us[:1]), us[:-1]))
    indices = torch.arange(us.numel(), device=us.device)
    tolerance = 8 * torch.finfo(dtype).eps
    feasible = (saturated <= budget + tolerance * budget.abs()) & (unsaturated > tiny)
    feasible &= (taus * us <= alpha_max + tolerance)
    feasible &= (indices == 0) | (taus * previous >= alpha_max - tolerance)
    chosen = feasible.to(torch.int64).argmax()
    tau = taus[chosen]
    alpha = (tau * u).clamp(max=alpha_max)
    residual = ((budget - capacity).clamp_min(0) / zero_energy.clamp_min(tiny)).sqrt().clamp(max=alpha_max)
    saturated_solution = torch.where(positive, torch.full_like(u, alpha_max), residual)
    alpha = torch.where(capacity < budget, saturated_solution, alpha)
    fallback = (~finite) | (~positive.any()) | (e.sum() <= tiny)
    fallback |= (~feasible.any()) & (capacity >= budget) & (budget > 0)
    alpha = torch.where(fallback, torch.full_like(alpha, alpha_prior), alpha)
    return {"alpha": alpha, "fallback": fallback, "requested_energy": budget,
            "allocated_energy": (e * alpha.square()).sum(),
            "energy_error": (e * alpha.square()).sum() - budget,
            "utility": (e * u * alpha).sum(),
            "uniform_utility": (e * u * alpha_prior).sum()}


@torch.no_grad()
def heads_budget_strength(same, reference, previous, following, mass, *,
                         exact_head_energy=None, alpha_prior=.25, alpha_max=.5,
                         basis="centered", ridge=1e-6, relative_signal_floor=1e-8):
    """Independent heads allocation: fixed block energy, adaptive per-head alpha.

    Pass full-resolution sum_{time,space,channel} D_h^2 as exact_head_energy.
    Omitting it conserves probe energy only and is intended for CPU prototypes.
    """
    z = temporal_components(same, reference, previous, following, mass, basis=basis,
                            ridge=ridge, relative_signal_floor=relative_signal_floor)
    et = z["temporal_energy"].sum((1, 2))
    ed = z["total_energy"].sum((1, 2))
    fraction = (et / ed.clamp_min(torch.finfo(ed.dtype).tiny)).clamp(0, 1)
    # No local temporal information should not be mistaken for negative evidence.
    valid = z["valid"].any((1, 2)) & (ed > torch.finfo(ed.dtype).tiny)
    mean = torch.where(valid, fraction, 0).sum() / valid.sum().clamp_min(1)
    fraction = torch.where(valid, fraction, mean)
    energy = ed if exact_head_energy is None else exact_head_energy
    result = allocate_energy_budget(fraction, energy, alpha_prior=alpha_prior, alpha_max=alpha_max)
    result.update(temporal_fraction=fraction, valid_head=valid,
                  exact_full_correction_budget=exact_head_energy is not None)
    return result
