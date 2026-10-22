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
