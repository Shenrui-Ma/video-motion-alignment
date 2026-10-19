"""Frozen H3 temporal-routing diagnostic, using exact Flash attention LSE.

No novelty claim: this isolates same-time reference routing and reference-group
mass preservation from plain reference strengthening. Bounds use H3 positional
bins, not exact VAE receptive fields. No attention matrix is materialized.
"""

import json
import math
import os
from pathlib import Path
import re
import time

from .layout import conditioning_metadata, event_latent_range, validate_layout


MODES = ("native", "diagnostic", "mass_preserve", "hard_route",
         "dynamic_residual", "static_component")
VALUE_SPLIT_MODES = ("dynamic_residual", "static_component")


def temporal_neighborhood(index, temporal_length, radius=0, time_offset=0):
    """Shift center, clamp center to a real bin, then clip its neighborhood.

    A clipped edge contains fewer real bins; edge bins are never duplicated.
    """
    if any(type(x) is not int for x in (index, temporal_length, radius, time_offset)):
        raise ValueError("temporal indices must be integers")
    if not 0 <= index < temporal_length or radius not in (0, 1):
        raise ValueError("invalid temporal index or radius (only 0/1 supported)")
    center = max(0, min(temporal_length - 1, index + time_offset))
    return max(0, center - radius), min(temporal_length, center + radius + 1)


def flash_attention_lse(q, k, v):
    """Explicit CUDA Flash backend. Dense/math fallback is deliberately absent."""
    import torch

    if q.device.type != "cuda" or q.dtype not in (torch.float16, torch.bfloat16):
        raise ValueError("production Flash backend requires CUDA fp16/bf16 tensors")
    if any(x.ndim != 4 or x.stride(-1) != 1 for x in (q, k, v)):
        raise ValueError("expected [B,H,N,D] tensors with contiguous last dimension")
    result = torch.ops.aten._scaled_dot_product_flash_attention.default(
        q, k, v, 0.0, False, False
    )
    out, lse = result[:2]
    if out.shape != q.shape or lse.shape != q.shape[:-1]:
        raise ValueError(f"unexpected Flash output/LSE shapes: {out.shape}, {lse.shape}")
    return out, lse


def _aligned_attention(q_event, k_ref, v_ref, *, latent_lo, frame_rows,
                       radius, time_offset, attention):
    """Batch temporal groups of equal neighborhood length without padding keys."""
    import torch

    batch, heads, qlen, dim = q_event.shape
    if batch != 1 or qlen % frame_rows or k_ref.shape[-2] % frame_rows:
        raise ValueError("temporal grouping requires matching full spatial frames")
    count, temporal_length = qlen // frame_rows, k_ref.shape[-2] // frame_rows
    if latent_lo < 0 or latent_lo + count > temporal_length:
        raise ValueError("query temporal interval exceeds reference")
    grouped_q = q_event.reshape(1, heads, count, frame_rows, dim)[0].permute(1, 0, 2, 3)
    out = torch.empty_like(grouped_q)
    lse = torch.empty((count, heads, frame_rows), device=q_event.device, dtype=torch.float32)
    groups = {}
    for local in range(count):
        lo, hi = temporal_neighborhood(latent_lo + local, temporal_length, radius, time_offset)
        groups.setdefault(hi - lo, []).append((local, lo, hi))
    for members in groups.values():
        indices = [local for local, _, _ in members]
        q_batch = grouped_q[indices].contiguous()
        k_batch = torch.cat([k_ref[:, :, lo * frame_rows:hi * frame_rows, :]
                             for _, lo, hi in members], dim=0)
        v_batch = torch.cat([v_ref[:, :, lo * frame_rows:hi * frame_rows, :]
                             for _, lo, hi in members], dim=0)
        aligned, aligned_lse = attention(q_batch, k_batch, v_batch)
        out[indices] = aligned
        lse[indices] = aligned_lse
    out = out.permute(1, 0, 2, 3).reshape(1, heads, qlen, dim)
    lse = lse.permute(1, 0, 2).reshape(1, heads, qlen)
    return out, lse



def reference_value_component(values, frame_rows, mode):
    """Per-spatial-position temporal DC split; never mutate the original V.

    The mean is over latent bins with equal weights, not physical durations.
    FP32/FP64 accumulation plus one-frame temporary avoids a full FP32 copy.
    The returned finite scalar stays on device until the forward audit flush.
    """
    import torch

    if mode not in VALUE_SPLIT_MODES:
        raise ValueError("expected a temporal value-split mode")
    if (values.ndim != 4 or type(frame_rows) is not int or frame_rows < 1
            or values.shape[-2] < 1 or values.shape[-2] % frame_rows):
        raise ValueError("value split requires complete spatial frames")
    if not values.is_floating_point():
        raise ValueError("reference values must be floating point")
    batch, heads, rows, dim = values.shape
    temporal_length = rows // frame_rows
    grouped = values.reshape(batch, heads, temporal_length, frame_rows, dim)
    work_dtype = torch.float64 if values.dtype == torch.float64 else torch.float32
    mean = grouped.mean(dim=2, dtype=work_dtype)
    component = torch.empty_like(values, memory_format=torch.contiguous_format)
    finite = []
    for t in range(temporal_length):
        if mode == "dynamic_residual":
            frame = (grouped[:, :, t].to(work_dtype) - mean).to(values.dtype)
        else:
            frame = mean.to(values.dtype)
        component[:, :, t * frame_rows:(t + 1) * frame_rows].copy_(frame)
        finite.append(torch.isfinite(frame).all())
    return component, mean, torch.stack(finite).all()


def _value_split_stats(original, component, mean, correction, component_finite):
    """Bounded RMS samples; full component finite was reduced while splitting."""
    import torch

    def rms_sample(x):
        hs = max(1, math.ceil(x.shape[1] / 8))
        qs = max(1, math.ceil(x.shape[2] / 128))
        ds = max(1, math.ceil(x.shape[3] / 16))
        sample = x[:, ::hs, ::qs, ::ds].float()
        return sample.square().mean().sqrt()

    return torch.stack((rms_sample(original), rms_sample(component),
                        rms_sample(mean), rms_sample(correction),
                        component_finite.float())).detach()


def _bounded_stats(before, after, mass, lse_delta):
    """Sample at most 8 heads x 128 queries x 16 channels, without host sync."""
    import torch

    hs = max(1, math.ceil(before.shape[1] / 8))
    qs = max(1, math.ceil(before.shape[2] / 128))
    ds = max(1, math.ceil(before.shape[3] / 16))
    a = before[:, ::hs, ::qs, ::ds].float()
    b = after[:, ::hs, ::qs, ::ds].float()
    m = mass[:, ::hs, ::qs].float()
    delta = lse_delta[:, ::hs, ::qs].float()
    finite = torch.isfinite(a).all() & torch.isfinite(b).all() & torch.isfinite(m).all()
    return torch.stack((m.mean(), m.max(),
                        (b - a).square().mean().sqrt() / a.square().mean().sqrt().clamp_min(1e-8),
                        finite.float(), delta.max())).detach()


def temporal_readout(q, k, plan):
    """Small fixed spatial/head sample of attention within the reference group.

    At most48 query rows for the usual six-bin window, against reference K.
    This is an internal attention diagnostic, never an action-timing metric.
    """
    import torch

    frame_rows = plan["frame_rows"]
    lo, hi = plan["latent_interval_half_open"]
    qa, qb = plan["query_interval_half_open"]
    ra, rb = plan["reference_video_segment"]
    temporal_length = (rb - ra) // frame_rows
    signature = plan.get("signature")
    if signature is not None:
        rows, cols = signature[2] // 2, signature[3] // 2
        center_r, center_c = rows // 2, cols // 2
        spatial = sorted({max(0, min(rows - 1, center_r + dr)) * cols
                          + max(0, min(cols - 1, center_c + dc))
                          for dr, dc in ((-1, -1), (-1, 0), (-1, 1), (0, -1),
                                         (0, 1), (1, -1), (1, 0), (1, 1))})
    else:
        spatial = list(range(min(8, frame_rows)))
    heads = list(range(0, q.shape[1], max(1, math.ceil(q.shape[1] / 8))))[:8]
    query_indices = [qa + (t - lo) * frame_rows + s for t in range(lo, hi) for s in spatial]
    head_index = torch.tensor(heads, device=q.device)
    query_index = torch.tensor(query_indices, device=q.device)
    qs = q.index_select(2, query_index).index_select(1, head_index).float()
    ks = k[:, :, ra:rb].index_select(1, head_index).float()
    logits = torch.matmul(qs, ks.transpose(-1, -2)) / math.sqrt(q.shape[-1])
    frame_logits = torch.logsumexp(logits.reshape(1, len(heads), len(query_indices),
                                                  temporal_length, frame_rows), dim=-1)
    frame_probability = frame_logits.softmax(-1)
    # One distribution per physical latent query time, averaged across fixed
    # spatial samples and heads. Keep raw distributions, not only point summary.
    probabilities = frame_probability.reshape(1, len(heads), hi - lo, len(spatial),
                                                temporal_length).mean((0, 1, 3))
    distribution = probabilities.detach().cpu().tolist()
    records = []
    for t, p in zip(range(lo, hi), distribution):
        records.append({"query_latent_bin": t, "p_ref_frame": p,
                        "reference_time_mean_bins": sum(i * x for i, x in enumerate(p)),
                        "mean_minus_query_bins": sum(i * x for i, x in enumerate(p)) - t,
                        "same_bin_mass": p[t], "within_one_bin_mass": sum(p[max(0, t - 1):min(temporal_length, t + 2)]),
                        "entropy_nats": -sum(x * math.log(max(x, 1e-30)) for x in p)})
    return {"scope": "pre-intervention QK attention conditional on all reference-video keys; not motion truth",
            "head_indices": heads, "spatial_indices": spatial,
            "reference_temporal_bins": temporal_length, "query_records": records}


def route_attention(q, k, v, heads, plan, *, mode="native", alpha=1.0,
                    radius=0, time_offset=0, attention=flash_attention_lse,
                    diagnostics=None):
    """Return native Comfy [B,N,H*D] format; optionally redistribute ref mass.

    mass_preserve: O + alpha*m_ref*(O_aligned-O_ref).
    hard_route: remove nonaligned reference logits and renormalize; alpha blends
    this hard-mask result with native output. At alpha=0 all modes are native.
    dynamic_residual/static_component: apply the same mass-preserving correction
    to V-mean_time(V) or mean_time(V), retaining the original full output.
    """
    import torch

    if mode not in MODES or not math.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ValueError("invalid mode or alpha; alpha must be in [0,1]")
    if q.ndim != 4 or q.shape != k.shape or k.shape != v.shape or q.shape[0] != 1:
        raise ValueError("expected equal single-batch [B,H,N,D] self-attention tensors")
    if q.shape[1] != heads or any(x.device != q.device or x.dtype != q.dtype for x in (k, v)):
        raise ValueError("head/device/dtype mismatch")
    full, full_lse = attention(q, k, v)
    if mode == "native" or (alpha == 0 and mode != "diagnostic"):
        return full.transpose(1, 2).reshape(1, q.shape[-2], heads * q.shape[-1])
    qa, qb = plan["query_interval_half_open"]
    ra, rb = plan["reference_video_segment"]
    if not 0 <= qa < qb <= q.shape[-2] or not 0 <= ra < rb <= k.shape[-2]:
        raise ValueError("selected ranges exceed packed sequence")
    query, keys, values = q[:, :, qa:qb], k[:, :, ra:rb], v[:, :, ra:rb]
    original_values = values
    component_mean = component_finite = None
    if mode in VALUE_SPLIT_MODES:
        values, component_mean, component_finite = reference_value_component(
            original_values, plan["frame_rows"], mode)
    ref, ref_lse = attention(query, keys, values)
    log_mass = ref_lse.float() - full_lse[:, :, qa:qb].float()
    # Subset LSE cannot exceed full LSE in exact arithmetic. Clamp tiny kernel
    # roundoff; expose sampled positive excess to the runtime audit.
    mass = log_mass.clamp(max=0).exp()
    old = full[:, :, qa:qb]
    changed = old
    if mode != "diagnostic":
        aligned, aligned_lse = _aligned_attention(
            query, keys, values, latent_lo=plan["latent_interval_half_open"][0],
            frame_rows=plan["frame_rows"], radius=radius, time_offset=time_offset,
            attention=attention)
        if mode == "mass_preserve" or mode in VALUE_SPLIT_MODES:
            correction = mass.unsqueeze(-1) * (aligned.float() - ref.float())
            changed = (old.float() + alpha * correction).to(old.dtype)
        else:
            # Do not recover O_other by subtracting bf16 attention outputs:
            # O-m_ref*O_ref is ill-conditioned when m_ref is near one. Obtain
            # the complement directly, then mix disjoint groups in log space.
            if ra == 0 and rb == k.shape[-2]:
                masked = aligned.float()
            else:
                other_k = torch.cat((k[:, :, :ra], k[:, :, rb:]), dim=-2)
                other_v = torch.cat((v[:, :, :ra], v[:, :, rb:]), dim=-2)
                other, other_lse = attention(query, other_k, other_v)
                combined_lse = torch.logaddexp(other_lse.float(), aligned_lse.float())
                other_mass = (other_lse.float() - combined_lse).exp()
                aligned_mass = (aligned_lse.float() - combined_lse).exp()
                masked = (other_mass.unsqueeze(-1) * other.float()
                          + aligned_mass.unsqueeze(-1) * aligned.float())
            changed = (old.float() + alpha * (masked - old.float())).to(old.dtype)
        if diagnostics is not None:
            stats = _bounded_stats(old, changed, mass, log_mass)
            if mode in VALUE_SPLIT_MODES:
                stats = torch.cat((stats, _value_split_stats(
                    original_values, values, component_mean,
                    alpha * correction, component_finite)))
            diagnostics.append(stats)
        full[:, :, qa:qb].copy_(changed)
    elif diagnostics is not None:
        diagnostics.append(_bounded_stats(old, old, mass, log_mass))
    return full.transpose(1, 2).reshape(1, q.shape[-2], heads * q.shape[-1])


class RouterState:
    def __init__(self, metadata, mode, alpha, radius, time_offset, start_frame,
                 end_frame, block_start, block_end, step_start, step_end,
                 run_id, audit_dir, num_blocks=50):
        if mode not in MODES or not math.isfinite(alpha) or not 0 <= alpha <= 1:
            raise ValueError("invalid router mode/alpha")
        if any(type(x) is not int for x in (radius, time_offset, block_start, block_end, step_start, step_end)):
            raise ValueError("router intervals and offsets must be integers")
        if radius not in (0, 1) or not 0 <= block_start < block_end <= num_blocks or not 0 <= step_start < step_end:
            raise ValueError("invalid radius or half-open block/step interval")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", run_id):
            raise ValueError("invalid unique run identifier")
        root = Path(audit_dir)
        if not root.is_absolute():
            raise ValueError("audit root must be absolute")
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / f"{run_id}.json"
        if self.path.exists():
            raise FileExistsError(self.path)
        self.metadata, self.mode, self.alpha = metadata, mode, alpha
        self.radius, self.time_offset = radius, time_offset
        self.start_frame, self.end_frame = start_frame, end_frame
        self.block_start, self.block_end = block_start, block_end
        self.step_start, self.step_end = step_start, step_end
        self.num_blocks, self.next_block, self.forward_index = num_blocks, 0, -1
        self.layout_object, self.plan, self.pending_stats = None, None, []
        self.audit = {"schema": "h3-temporal-router-v1", "run_id": run_id,
                      "mode": mode, "alpha": alpha, "radius": radius, "time_offset": time_offset,
                      "block_interval_half_open": [block_start, block_end],
                      "step_interval_half_open": [step_start, step_end],
                      "pixel_interval_inclusive": [start_frame, end_frame],
                      "backend": "aten._scaled_dot_product_flash_attention.default",
                      "metric_scope": "sampled at most8heads x128queries x16channels per routed layer; mean/max refmass sampled",
                      "metadata": metadata, "created_unix": time.time(),
                      "started_calls": 0, "completed_calls": 0, "native_override_calls": 0,
                      "routed_calls": 0, "diagnostic_calls": 0,
                      "calls_by_block": [0] * num_blocks, "calls_by_forward": [],
                      "routed_by_block": [0] * num_blocks, "routed_by_forward": [],
                      "completed_forward_calls": 0, "forward_summaries": [],
                      "temporal_readouts": [], "status": "installed"}
        if mode in VALUE_SPLIT_MODES:
            self.audit["value_split"] = {
                "projection": "equal-weight temporal mean at each head/spatial position/channel",
                "time_weights": "latent-bin uniform; not physical-duration weighted",
                "mean_accumulation_dtype": "float64 for float64 inputs; float32 otherwise",
                "component_cast": "original V dtype before Flash; one temporal frame temporary",
                "correction": "alpha*m_ref*(A_same-A_ref)*component_V",
                "bound": None,
                "scope": "same-input algebra only; not independently identified motion or appearance",
                "component_finite_scope": "all component elements, GPU reduction",
                "rms_scope": "sampled at most8heads x128rows x16channels; not global RMS"}
        self.write()

    def write(self):
        self.audit["updated_unix"] = time.time()
        temp = self.path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(self.audit, indent=2, ensure_ascii=False) + "\n")
        os.replace(temp, self.path)

    def plan_for(self, layout):
        if layout is not self.layout_object:
            plan = validate_layout(self.metadata, layout, self.start_frame, self.end_frame)
            positions = layout.position_ids
            if tuple(positions.shape) != (plan["seq_len"], 3):
                raise ValueError("packed position shape mismatch")
            for interval, key in (("key_interval_half_open", "key_first_time_coordinate"),
                                  ("query_interval_half_open", "query_first_time_coordinate")):
                if not math.isclose(float(positions[plan[interval][0], 0]), plan[key], abs_tol=1e-8, rel_tol=0):
                    raise ValueError("packed RoPE coordinates mismatch")
            if self.plan is not None and plan != self.plan:
                raise ValueError("packed layout changed during fixed geometry run")
            self.layout_object, self.plan = layout, plan
            self.audit["validated_layout"] = plan
        return self.plan

    def selected(self, block):
        return self.block_start <= block < self.block_end and self.step_start <= self.forward_index < self.step_end

    def finish_forward(self):
        summary = {"forward_index": self.forward_index, "completed_blocks": self.num_blocks,
                   "routed_blocks": self.audit["routed_by_forward"][-1]}
        if self.pending_stats:
            import torch

            blocks = [b for b, _ in self.pending_stats]
            rows = torch.stack([s for _, s in self.pending_stats]).float().cpu().tolist()
            summary.update(sampled_ref_mass_mean=sum(r[0] for r in rows) / len(rows),
                           sampled_ref_mass_max=max(r[1] for r in rows),
                           sampled_correction_ratio_mean=sum(r[2] for r in rows) / len(rows),
                           sampled_correction_ratio_max=max(r[2] for r in rows),
                           sampled_finite=all(r[3] == 1.0 for r in rows),
                           sampled_log_mass_positive_excess=max(r[4] for r in rows),
                           layer_stats=[{"block": b, "ref_mass_mean": r[0], "ref_mass_max": r[1],
                                         "correction_ratio": r[2], "finite": r[3] == 1.0,
                                         "log_mass_max": r[4]} for b, r in zip(blocks, rows)])
            if self.mode in VALUE_SPLIT_MODES:
                if any(len(row) != 10 for row in rows):
                    raise ValueError("incomplete value-split audit statistics")
                summary["component_finite"] = all(row[9] == 1.0 for row in rows)
                summary["sampled_component_correction_rms_mean"] = sum(row[8] for row in rows) / len(rows)
                for item, row in zip(summary["layer_stats"], rows):
                    item.update(sampled_reference_value_rms=row[5],
                                sampled_component_value_rms=row[6],
                                sampled_temporal_mean_rms=row[7],
                                sampled_component_correction_rms=row[8],
                                component_finite=row[9] == 1.0)
            self.pending_stats.clear()
            if not summary["sampled_finite"] or not summary.get("component_finite", True):
                raise FloatingPointError("nonfinite sampled router output/mass")
        self.audit["forward_summaries"].append(summary)
        self.audit["completed_forward_calls"] += 1
        self.write()


class TemporalAttentionOverride:
    def __init__(self, state, plan, block):
        self.state, self.plan, self.block, self.calls = state, plan, block, 0

    def __call__(self, native, q, k, v, heads, **kwargs):
        if getattr(native, "__name__", None) != "attention_pytorch":
            raise ValueError("router requires native attention_pytorch entry point")
        if kwargs.get("mask") is not None or not kwargs.get("skip_reshape") or kwargs.get("skip_output_reshape", False):
            raise ValueError("router requires unmasked preshaped native attention")
        if q.shape[-2] != self.plan["seq_len"]:
            raise ValueError("packed attention length differs from layout")
        self.calls += 1
        if self.calls != 1:
            raise ValueError("expected one attention per DiT block")
        state = self.state
        if self.block == 25 and state.forward_index in (0, 5, 10, 15, 19):
            readout = temporal_readout(q, k, self.plan)
            readout.update(block_index=self.block, forward_index=state.forward_index)
            state.audit["temporal_readouts"].append(readout)
        active = state.selected(self.block)
        mode = state.mode if active else "native"
        stats = []
        out = route_attention(q, k, v, heads, self.plan, mode=mode, alpha=state.alpha,
                              radius=state.radius, time_offset=state.time_offset, diagnostics=stats)
        state.audit["native_override_calls"] += 1
        if active and mode in ("mass_preserve", "hard_route") + VALUE_SPLIT_MODES and state.alpha != 0:
            state.audit["routed_calls"] += 1
            state.audit["routed_by_block"][self.block] += 1
            state.audit["routed_by_forward"][state.forward_index] += 1
        elif active and mode == "diagnostic":
            state.audit["diagnostic_calls"] += 1
        if stats:
            state.pending_stats.append((self.block, stats[0]))
        if "first_attention" not in state.audit:
            state.audit["first_attention"] = {"qkv_shape": list(q.shape), "dtype": str(q.dtype),
                                             "device": str(q.device), "heads": heads,
                                             "flash_lse": True, "returned_shape": list(out.shape)}
        return out


class EventBlockPatch:
    def __init__(self, state, block_index):
        self.state, self.block_index = state, block_index

    def __call__(self, args, extra_args):
        state = self.state
        try:
            if self.block_index != state.next_block:
                raise ValueError("unexpected block order; CFG/parallel interleaving unsupported")
            if self.block_index == 0:
                state.forward_index += 1
                state.audit["calls_by_forward"].append(0)
                state.audit["routed_by_forward"].append(0)
            plan = state.plan_for(args["layout"])
            options = args["transformer_options"]
            if options.get("block_index") != self.block_index or options.get("minimax_h3_layout") is not args["layout"]:
                raise ValueError("block/layout runtime identity mismatch")
            if options.get("optimized_attention_override") is not None:
                raise ValueError("cannot combine attention overrides")
            if self.block_index == 0 and options.get("sample_sigmas") is not None:
                schedule = options["sample_sigmas"]
                if schedule.ndim != 1 or len(schedule) < 2:
                    raise ValueError("invalid sigma schedule")
                values = schedule.detach().cpu().tolist()
                if "sample_sigmas" in state.audit and values != state.audit["sample_sigmas"]:
                    raise ValueError("sigma schedule changed")
                state.audit["sample_sigmas"] = values
                state.audit["expected_sampling_steps"] = len(values) - 1
            state.audit["started_calls"] += 1
            override = TemporalAttentionOverride(state, plan, self.block_index)
            local_args, local_options = dict(args), dict(options)
            local_options["optimized_attention_override"] = override
            local_args["transformer_options"] = local_options
            result = extra_args["original_block"](local_args)
            if override.calls != 1:
                raise ValueError("attention override not invoked exactly once")
            state.audit["completed_calls"] += 1
            state.audit["calls_by_block"][self.block_index] += 1
            state.audit["calls_by_forward"][state.forward_index] += 1
            state.next_block = (self.block_index + 1) % state.num_blocks
            state.audit["last_completed_block"] = self.block_index
            state.audit["last_completed_forward_index"] = state.forward_index
            state.audit["status"] = "sampling"
            if state.next_block == 0:
                state.finish_forward()
            return result
        except Exception as error:
            state.audit["status"], state.audit["error"] = "failed", repr(error)
            state.write()
            raise
