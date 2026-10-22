"""Reference-time direction gating before H3 attention heads are merged.

Production uses the frozen CUDA Flash output/LSE primitive. The only explicit
logits are fixed spatial probes, tiled in both query and reference-key axes.
No complete video-query x reference-key matrix is constructed here.
"""
from dataclasses import asdict, dataclass
import math
import time

import torch

from .frozen import load_frozen


REASONS = ("direction_supported", "direction_conflict", "nonfinite_input",
           "invalid_reference_distribution", "diffuse_reference_routing",
           "small_internal_routing_offset", "low_feature_signal")
MODES = ("native", "mass_preserve", "direction_gated")


@dataclass(frozen=True)
class DirectionConfig:
    alpha: float = 0.45
    min_routing_offset: float = 0.25
    min_concentration: float = 0.15
    min_tangent_norm: float = 1e-6
    epsilon: float = 1e-12
    query_chunk: int = 16
    key_chunk: int = 512
    record_cuda_timing: bool = True

    def __post_init__(self):
        values = (self.alpha, self.min_routing_offset, self.min_concentration,
                  self.min_tangent_norm, self.epsilon)
        if not all(math.isfinite(x) for x in values):
            raise ValueError("direction configuration must be finite")
        if not 0 <= self.alpha <= 1 or not 0 <= self.min_concentration <= 1:
            raise ValueError("alpha and concentration must be in [0,1]")
        if min(self.min_routing_offset, self.min_tangent_norm) < 0 or self.epsilon <= 0:
            raise ValueError("thresholds must be nonnegative and epsilon positive")
        if any(type(x) is not int or x < 1 for x in (self.query_chunk, self.key_chunk)):
            raise ValueError("positive integer probe tile sizes required")


def work_dtype(tensor):
    return torch.float64 if tensor.dtype == torch.float64 else torch.float32


def vectorized_gate(correction, previous, following, probabilities, query_bins,
                    previous_bins, next_bins, config):
    """All leading dimensions broadcast; final axes are features / time bins.

    Returns one gate for each sampled query/head. UNKNOWN is a zero gate.
    This matches the sibling pure-Python prototype, including reason precedence.
    """
    dtype = work_dtype(correction)
    d, before, after, p = [x.to(dtype) for x in (correction, previous, following, probabilities)]
    if d.shape != before.shape or d.shape != after.shape or p.shape[:-1] != d.shape[:-1]:
        raise ValueError("probe feature/distribution shapes disagree")
    if p.shape[-1] < 2:
        raise ValueError("at least two reference bins required")
    finite = torch.isfinite(d).all(-1) & torch.isfinite(before).all(-1)
    finite &= torch.isfinite(after).all(-1) & torch.isfinite(p).all(-1)
    total = p.sum(-1)
    valid_p = (p >= 0).all(-1) & (total > config.epsilon)
    safe_p = torch.nan_to_num(p, nan=0.0, posinf=0.0, neginf=0.0).clamp_min(0)
    safe_p = safe_p / safe_p.sum(-1, keepdim=True).clamp_min(config.epsilon)
    entropy = -(safe_p * safe_p.clamp_min(config.epsilon).log()).sum(-1)
    concentration = (1 - entropy / math.log(p.shape[-1])).clamp(0, 1)
    timeline = torch.arange(p.shape[-1], device=p.device, dtype=dtype)
    offset = query_bins.to(dtype) - (safe_p * timeline).sum(-1)
    spacing = (next_bins - previous_bins).to(dtype)
    tangent = (after - before) / spacing.unsqueeze(-1)
    desired = offset.unsqueeze(-1) * tangent
    dn = d.norm(dim=-1)
    tn = tangent.norm(dim=-1)
    un = desired.norm(dim=-1)
    cosine = ((d * desired).sum(-1) / (dn * un).clamp_min(torch.finfo(dtype).tiny)).clamp(-1, 1)
    cosine = torch.nan_to_num(cosine, nan=0.0, posinf=0.0, neginf=0.0)
    reason = torch.where(cosine > 0, 0, 1)
    reason = torch.where((tn < config.min_tangent_norm) | (dn <= config.epsilon), 6, reason)
    reason = torch.where(offset.abs() < config.min_routing_offset, 5, reason)
    reason = torch.where(concentration < config.min_concentration, 4, reason)
    reason = torch.where(~valid_p, 3, reason)
    reason = torch.where(~finite, 2, reason)
    gate = torch.where(reason == 0, cosine.clamp_min(0).square(), 0)
    return {"gate": gate, "reason": reason, "offset": offset,
            "concentration": concentration, "cosine": cosine}


def fixed_spatial_indices(plan):
    """A fixed 2x2 quarter grid; duplicate cells only disappear on tiny grids."""
    frame_rows = plan["frame_rows"]
    signature = plan.get("signature")
    if signature is not None:
        height, width = signature[2] // 2, signature[3] // 2
        if height * width != frame_rows:
            raise ValueError("spatial geometry disagrees with frame_rows")
        return sorted({min(height - 1, (n * height) // 4) * width
                       + min(width - 1, (m * width) // 4)
                       for n in (1, 3) for m in (1, 3)})
    # Test-only geometry fallback, equally spaced flattened positions.
    return sorted({min(frame_rows - 1, (n * frame_rows) // 8) for n in (1, 3, 5, 7)})


class ComputeTrace:
    """Python counters plus deferred CUDA-event timing, no in-layer host sync."""
    def __init__(self, attention, config, device):
        self.attention = attention
        self.counts = {}
        self.host_seconds = {}
        self.events = []
        self.cuda_timing = config.record_cuda_timing and device.type == "cuda"
        self.device = device
        self.max_logits_shape = [0, 0, 0, 0]
        self.logits_matmul_calls = 0

    def measure(self, name, function):
        start = time.perf_counter()
        if self.cuda_timing:
            a, b = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
            stream = torch.cuda.current_stream(device=self.device)
            a.record(stream)
        result = function()
        if self.cuda_timing:
            b.record(stream)
            self.events.append((name, a, b))
        self.host_seconds[name] = self.host_seconds.get(name, 0.0) + time.perf_counter() - start
        return result

    def call(self, name, q, k, v):
        self.counts[name] = self.counts.get(name, 0) + 1
        return self.measure(name, lambda: self.attention(q, k, v))

    def finalize(self):
        cuda_ms = {}
        if self.events:
            self.events[-1][2].synchronize()
            for name, a, b in self.events:
                cuda_ms[name] = cuda_ms.get(name, 0.0) + a.elapsed_time(b)
        return {"attention_calls": dict(self.counts),
                "attention_call_total": sum(self.counts.values()),
                "probe_logits_matmul_calls": self.logits_matmul_calls,
                "max_probe_logits_shape": self.max_logits_shape,
                "host_dispatch_seconds": dict(self.host_seconds),
                "cuda_event_ms": cuda_ms,
                "timing_scope": "per-category device events; nested categories overlap; host times are dispatch only"}


def probe_probabilities(probe_q, ref_k, frame_rows, config, trace):
    """Stable per-bin LSE with bounded [1,H,query_chunk,key_chunk] tiles."""
    temporal_length = ref_k.shape[-2] // frame_rows
    dtype = work_dtype(probe_q)
    chunks = []
    for qa in range(0, probe_q.shape[-2], config.query_chunk):
        q = probe_q[:, :, qa:qa + config.query_chunk].to(dtype)
        frame_lse = []
        for t in range(temporal_length):
            accum = torch.full(q.shape[:-1], -torch.inf, device=q.device, dtype=dtype)
            for ka in range(t * frame_rows, (t + 1) * frame_rows, config.key_chunk):
                kb = min((t + 1) * frame_rows, ka + config.key_chunk)
                logits = torch.matmul(q, ref_k[:, :, ka:kb].to(dtype).transpose(-1, -2))
                logits = logits / math.sqrt(q.shape[-1])
                trace.logits_matmul_calls += 1
                if math.prod(logits.shape) > math.prod(trace.max_logits_shape):
                    trace.max_logits_shape = list(logits.shape)
                accum = torch.logaddexp(accum, logits.logsumexp(-1))
            frame_lse.append(accum)
        chunks.append(torch.stack(frame_lse, -1).softmax(-1))
    return torch.cat(chunks, dim=-2)


def validate_plan(q, k, v, heads, plan):
    if q.ndim != 4 or q.shape != k.shape or q.shape != v.shape or q.shape[0] != 1:
        raise ValueError("expected equal single-batch [B,H,N,D] tensors")
    if q.shape[1] != heads or not q.is_floating_point():
        raise ValueError("head count/dtype mismatch")
    if any(x.device != q.device or x.dtype != q.dtype for x in (k, v)):
        raise ValueError("device/dtype mismatch")
    qa, qb = plan["query_interval_half_open"]
    ra, rb = plan["reference_video_segment"]
    ta, tb = plan["target_video_segment"]
    lo, hi = plan["latent_interval_half_open"]
    frame_rows = plan["frame_rows"]
    if type(frame_rows) is not int or frame_rows < 1:
        raise ValueError("invalid frame_rows")
    if not (0 <= ra < rb <= ta <= qa < qb <= tb <= q.shape[-2]):
        raise ValueError("reference/target/query intervals overlap or exceed sequence")
    if (rb - ra) % frame_rows or (tb - ta) != rb - ra:
        raise ValueError("matching complete temporal geometry required")
    if not 0 <= lo < hi <= (rb - ra) // frame_rows:
        raise ValueError("invalid latent interval")
    if (qa, qb) != (ta + lo * frame_rows, ta + hi * frame_rows):
        raise ValueError("query and latent intervals disagree")
    if plan["seq_len"] != q.shape[-2]:
        raise ValueError("packed sequence mismatch")


def direction_attention(q, k, v, heads, plan, *, mode="direction_gated",
                        config=DirectionConfig(), attention=None, diagnostics=None):
    """Return Comfy [1,N,H*D] output; change only designated video queries.

    A single coefficient per head/bin is the arithmetic mean of the fixed
    sampled-query gates (UNKNOWN and conflict contribute zero). A coefficient
    in [0,alpha] preserves reference total probability algebraically.
    """
    if mode not in MODES:
        raise ValueError("unregistered direction mode")
    validate_plan(q, k, v, heads, plan)
    frozen = load_frozen().core
    trace = ComputeTrace(attention or frozen.flash_attention_lse, config, q.device)
    full, full_lse = trace.call("full", q, k, v)
    report = {"trace": trace, "mode": mode, "config": asdict(config)}

    def finish():
        if diagnostics is not None:
            diagnostics.append(report)
        return full.transpose(1, 2).reshape(1, q.shape[-2], heads * q.shape[-1])

    if mode == "native" or config.alpha == 0:
        report["skip_reason"] = "native_mode" if mode == "native" else "alpha_zero"
        return finish()
    qa, qb = plan["query_interval_half_open"]
    ra, rb = plan["reference_video_segment"]
    lo, hi = plan["latent_interval_half_open"]
    frame_rows = plan["frame_rows"]
    temporal_length = (rb - ra) // frame_rows
    if mode == "direction_gated" and temporal_length < 2:
        report["skip_reason"] = "insufficient_reference_bins"
        return finish()
    query, keys, values = q[:, :, qa:qb], k[:, :, ra:rb], v[:, :, ra:rb]
    ref, ref_lse = trace.call("reference", query, keys, values)
    dtype = work_dtype(q)
    log_mass = ref_lse.to(dtype) - full_lse[:, :, qa:qb].to(dtype)
    mass = log_mass.clamp(max=0).exp()

    def aligned_backend(a, b, c):
        output, lse = trace.call("aligned", a, b, c)
        # Frozen grouping stores LSE in fp32 (the CUDA Flash contract). The
        # cast also permits an fp64 CPU oracle; this LSE is not used below.
        return output, lse.float()

    aligned, _ = frozen._aligned_attention(
        query, keys, values, latent_lo=lo, frame_rows=frame_rows,
        radius=0, time_offset=0,
        attention=aligned_backend)
    correction = mass.unsqueeze(-1) * (aligned.to(dtype) - ref.to(dtype))
    gates = torch.ones((heads, hi - lo), device=q.device, dtype=dtype)
    if mode == "direction_gated":
        spatial = fixed_spatial_indices(plan)
        indices = torch.tensor([(t - lo) * frame_rows + s for t in range(lo, hi)
                                for s in spatial], device=q.device)
        probe_q = query.index_select(2, indices)
        probabilities = trace.measure("probe_distribution", lambda: probe_probabilities(
            probe_q, keys, frame_rows, config, trace))
        # Neighbor attention only needs sampled queries; temporal bins are the
        # batch axis, retaining all heads and full spatial reference keys.
        probe_batch = probe_q.reshape(1, heads, hi - lo, len(spatial), q.shape[-1])[0].permute(1, 0, 2, 3).contiguous()
        times = list(range(lo, hi))
        previous_bins = [max(0, t - 1) for t in times]
        next_bins = [min(temporal_length - 1, t + 1) for t in times]

        def neighbor_output(bins, name):
            kb = torch.cat([keys[:, :, t * frame_rows:(t + 1) * frame_rows] for t in bins])
            vb = torch.cat([values[:, :, t * frame_rows:(t + 1) * frame_rows] for t in bins])
            out, _ = trace.call(name, probe_batch, kb, vb)
            return out.permute(1, 0, 2, 3)

        previous = neighbor_output(previous_bins, "probe_previous")
        following = neighbor_output(next_bins, "probe_next")
        d = correction.index_select(2, indices).reshape(heads, hi - lo, len(spatial), -1)
        p = probabilities.reshape(heads, hi - lo, len(spatial), temporal_length)
        bins = lambda xs: torch.tensor(xs, device=q.device).reshape(1, -1, 1)
        probe = vectorized_gate(d, previous, following, p, bins(times),
                                bins(previous_bins), bins(next_bins), config)
        gates = probe["gate"].mean(-1)
        report.update(spatial_indices=spatial, query_bins=times,
                      mean_routing_offset_bins=probe["offset"].mean(-1).detach(),
                      mean_concentration=probe["concentration"].mean(-1).detach(),
                      reason_counts=torch.stack([(probe["reason"] == i).sum(-1)
                                                 for i in range(len(REASONS))], -1).detach())
    alpha = (config.alpha * gates).repeat_interleave(frame_rows, dim=1)[None, :, :, None]
    applied = torch.where(alpha > 0, alpha * correction, 0)
    old = full[:, :, qa:qb]
    changed = (old.to(dtype) + applied).to(old.dtype)
    # Statistics are exact over this intervention interval, accumulated on the
    # device. No per-layer .item(), .cpu(), VAE decode, or extra DiT forward.
    report.update(gate_per_head_bin=gates.detach(), alpha_per_head_bin=(config.alpha * gates).detach(),
                  totals=torch.stack((correction.square().sum(), applied.square().sum(),
                                      old.to(dtype).square().sum(),
                                      mass.sum(), mass.max(), log_mass.max(),
                                      torch.isfinite(changed).all().to(dtype))).detach(),
                  correction_element_count=correction.numel(), mass_element_count=mass.numel())
    full[:, :, qa:qb].copy_(changed)
    return finish()


def serialize_report(report):
    """Call at the forward boundary, where frozen state already flushes audits."""
    result = {key: value for key, value in report.items() if key != "trace"}
    for key, value in list(result.items()):
        if isinstance(value, torch.Tensor):
            result[key] = value.cpu().tolist()
    result["compute"] = report["trace"].finalize()
    if "totals" in result:
        native, applied, old, mass_sum, mass_max, log_max, finite = result.pop("totals")
        count = result["correction_element_count"]
        result.update(native_correction_energy=native, applied_correction_energy=applied,
                      native_correction_rms=math.sqrt(native / count),
                      applied_correction_rms=math.sqrt(applied / count),
                      correction_ratio=math.sqrt(applied / max(old, 1e-30)),
                      mean_reference_mass=mass_sum / result["mass_element_count"],
                      max_reference_mass=mass_max, log_mass_max=log_max,
                      finite_output=bool(finite))
        gates = result["gate_per_head_bin"]
        flattened = [g for head in gates for g in head]
        result.update(selected_head_bin_fraction=sum(g > 0 for g in flattened) / len(flattened),
                      gate_mean=sum(flattened) / len(flattened),
                      gate_min=min(flattened), gate_max=max(flattened))
    return result
