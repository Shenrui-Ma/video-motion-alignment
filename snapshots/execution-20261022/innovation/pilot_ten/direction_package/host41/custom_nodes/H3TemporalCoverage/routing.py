"""Small time-bin transport, independent of ComfyUI and the frozen H3 core.

Sinkhorn scaling is an existing algorithm (Cuturi, 2013), not a novelty claim.
The solver balances *conditional* reference-time coverage across equal-sized
output bins, then contracts toward identity to order expected reference times.
"""

from dataclasses import dataclass
import math

import torch


@dataclass(frozen=True)
class CoverageConfig:
    radius: int = 2
    entropy: float = 0.5
    temporal_penalty: float = 0.25
    iterations: int = 128
    tolerance: float = 2e-4
    min_quality_span: float = 1e-3
    minimum_mean_gap: float = 0.0
    max_bins: int = 256

    def __post_init__(self):
        for name in ("radius", "iterations", "max_bins"):
            value = getattr(self, name)
            if type(value) is not int or value < (0 if name == "radius" else 1):
                raise ValueError(f"invalid {name}")
        for name in ("entropy", "temporal_penalty", "tolerance",
                     "min_quality_span", "minimum_mean_gap"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid {name}")
        if self.entropy == 0 or not 0 < self.tolerance < 1:
            raise ValueError("entropy must be positive and tolerance in (0,1)")
        if self.minimum_mean_gap > 1:
            raise ValueError("minimum_mean_gap must be in [0,1] bins")


@dataclass
class CoverageResult:
    probabilities: torch.Tensor
    allowed: torch.Tensor
    applied: bool
    reason: str
    row_error: float = 0.0
    column_error: float = 0.0
    quality_span: float = 0.0
    transport_fraction: float = 0.0

    def summary(self):
        return {name: getattr(self, name) for name in (
            "applied", "reason", "row_error", "column_error",
            "quality_span", "transport_fraction")}


@torch.no_grad()
def solve_temporal_coverage(quality, *, config=CoverageConfig(), valid_mask=None,
                            allowed_mask=None):
    """Solve a square T x T conditional routing matrix without token attention.

    Input quality is a finite log-compatibility, larger is better. H3 has equal
    target/reference geometry; one validity mask pads both axes consistently.
    Active rows/columns have unit budgets; padded rows/columns are zero.

    Feasible supports must contain the diagonal so the identity anchor remains
    available. Unsupported/infeasible masks, weak signal, numerical failures or
    nonconvergence return applied=False and an all-zero matrix: callers must
    keep their native attention output. Radius=0 explicitly requests identity.
    Scalar checks synchronize a GPU caller; this CPU-tested prototype makes no
    claim of a synchronization-free or speed-validated implementation.
    """
    if (quality.ndim != 2 or quality.shape[0] != quality.shape[1]
            or quality.shape[0] < 1 or quality.shape[0] > config.max_bins
            or not quality.is_floating_point()):
        raise ValueError("quality must be floating square T x T within max_bins")
    count, device = quality.shape[0], quality.device
    valid = torch.ones(count, dtype=torch.bool, device=device)
    if valid_mask is not None:
        if valid_mask.shape != (count,) or valid_mask.dtype != torch.bool:
            raise ValueError("valid_mask must be bool [T]")
        valid = valid_mask.to(device)
    indices = torch.arange(count, device=device)
    allowed = (indices[:, None] - indices[None, :]).abs() <= config.radius
    allowed &= valid[:, None] & valid[None, :]
    if allowed_mask is not None:
        if allowed_mask.shape != quality.shape or allowed_mask.dtype != torch.bool:
            raise ValueError("allowed_mask must be bool [T,T]")
        allowed &= allowed_mask.to(device)
    dtype = torch.float64 if quality.dtype == torch.float64 else torch.float32
    empty = torch.zeros_like(quality, dtype=dtype)

    def fallback(reason, **stats):
        return CoverageResult(empty, allowed, False, reason, **stats)

    active = indices[valid]
    if active.numel() == 0:
        return fallback("no_valid_bins")
    support = allowed[active[:, None], active[None, :]]
    if not bool(support.diagonal().all()):
        return fallback("identity_anchor_infeasible")
    values = quality[active[:, None], active[None, :]].to(dtype)
    if not bool(torch.isfinite(values[support]).all()):
        return fallback("nonfinite_quality")
    identity = torch.eye(active.numel(), dtype=dtype, device=device)
    if config.radius == 0 or active.numel() == 1:
        empty[active[:, None], active[None, :]] = identity
        return CoverageResult(empty, allowed, True, "identity", transport_fraction=0.0)
    row_max = values.masked_fill(~support, -torch.inf).max(-1).values
    row_min = values.masked_fill(~support, torch.inf).min(-1).values
    span = float((row_max - row_min).mean())
    if span < config.min_quality_span:
        return fallback("low_signal", quality_span=span)
    distance = (active[:, None] - active[None, :]).to(dtype)
    log_kernel = ((values - row_max[:, None]
                   - config.temporal_penalty * distance.square()) / config.entropy)
    log_kernel = log_kernel.masked_fill(~support, -torch.inf)
    if not bool(torch.isfinite(log_kernel[support]).all()):
        return fallback("nonfinite_scaled_quality", quality_span=span)
    log_v = torch.zeros(active.numel(), dtype=dtype, device=device)
    for _ in range(config.iterations):
        log_u = -torch.logsumexp(log_kernel + log_v[None, :], dim=1)
        log_v = -torch.logsumexp(log_kernel + log_u[:, None], dim=0)
    transport = (log_kernel + log_u[:, None] + log_v[None, :]).exp()
    transport /= transport.sum(-1, keepdim=True)
    if not bool(torch.isfinite(transport).all()):
        return fallback("nonfinite_transport", quality_span=span)
    column_error = float((transport.sum(0) - 1).abs().max())
    if column_error > config.tolerance:
        return fallback("not_converged", quality_span=span, column_error=column_error)

    # Largest convex blend beta*transport + (1-beta)*I whose expected times
    # do not reverse. Both endpoints satisfy row/column budgets and support.
    means = transport @ active.to(dtype)
    gaps = means[1:] - means[:-1]
    anchor_gaps = (active[1:] - active[:-1]).to(dtype)
    bad = gaps < config.minimum_mean_gap
    beta = torch.ones((), dtype=dtype, device=device)
    if bool(bad.any()):
        beta = ((anchor_gaps[bad] - config.minimum_mean_gap)
                / (anchor_gaps[bad] - gaps[bad])).min().clamp(0, 1)
        # Leave a tiny positive safety margin for finite precision.
        beta *= 1 - 8 * torch.finfo(dtype).eps
    transport = beta * transport + (1 - beta) * identity
    row_error = float((transport.sum(1) - 1).abs().max())
    column_error = float((transport.sum(0) - 1).abs().max())
    final_means = transport @ active.to(dtype)
    if (row_error > config.tolerance or column_error > config.tolerance
            or bool((final_means[1:] - final_means[:-1]
                     < config.minimum_mean_gap - 8 * torch.finfo(dtype).eps * count).any())):
        return fallback("constraint_check_failed", quality_span=span,
                        row_error=row_error, column_error=column_error)
    empty[active[:, None], active[None, :]] = transport
    return CoverageResult(empty, allowed, True, "balanced", row_error,
                          column_error, span, float(beta))


@torch.no_grad()
def sampled_time_quality(query, keys, frame_rows, *, query_samples=8,
                         head_samples=4, key_chunk=256):
    """Return log mean reference-frame probability from bounded spatial Qs.

    query/keys: [1,H,T*S,D], same event window and matching geometries.
    Key chunks stream exact spatial logsumexp per frame. Largest logits buffer
    is [sampled_heads,T*query_samples,key_chunk], never token N x N.
    """
    if (query.ndim != 4 or keys.shape != query.shape or query.shape[0] != 1
            or query.device != keys.device or query.dtype != keys.dtype
            or not query.is_floating_point()):
        raise ValueError("expected matching floating [1,H,T*S,D] Q/K")
    for name, value in (("frame_rows", frame_rows), ("query_samples", query_samples),
                        ("head_samples", head_samples), ("key_chunk", key_chunk)):
        if type(value) is not int or value < 1:
            raise ValueError(f"invalid {name}")
    _, heads, tokens, dim = query.shape
    if heads < 1 or dim < 1 or tokens < 1 or tokens % frame_rows:
        raise ValueError("Q/K must contain complete nonempty spatial frames")
    count = tokens // frame_rows
    device = query.device
    spatial = torch.linspace(0, frame_rows - 1, min(frame_rows, query_samples),
                             device=device).round().long()
    head_ids = torch.linspace(0, heads - 1, min(heads, head_samples),
                              device=device).round().long()
    dtype = torch.float64 if query.dtype == torch.float64 else torch.float32
    q_small = query[0].reshape(heads, count, frame_rows, dim)
    q_small = q_small.index_select(0, head_ids).index_select(2, spatial)
    q_small = q_small.reshape(len(head_ids), count * len(spatial), dim).to(dtype)
    frame_lse = []
    for frame in range(count):
        total = torch.full(q_small.shape[:-1], -torch.inf, dtype=dtype, device=device)
        for offset in range(0, frame_rows, key_chunk):
            start = frame * frame_rows + offset
            stop = frame * frame_rows + min(frame_rows, offset + key_chunk)
            key = keys[0, :, start:stop].index_select(0, head_ids).to(dtype)
            logits = torch.matmul(q_small, key.transpose(-1, -2)) / math.sqrt(dim)
            total = torch.logaddexp(total, torch.logsumexp(logits, dim=-1))
        frame_lse.append(total)
    probabilities = torch.stack(frame_lse, dim=-1).softmax(-1)
    average = probabilities.reshape(len(head_ids), count, len(spatial), count).mean((0, 2))
    return average.clamp_min(torch.finfo(dtype).tiny).log()
