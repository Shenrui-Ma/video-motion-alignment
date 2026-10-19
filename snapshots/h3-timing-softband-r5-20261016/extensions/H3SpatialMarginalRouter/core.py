"""Staged fixed-input spatial-marginal preserving H3 diagnostic.

Copied audited lifecycle/layout/Flash/readout utilities; isolated from live nodes.
No novelty claim; nonnegative reference reweighting has a logit representation.
"""

import json
import math
import os
from pathlib import Path
import re
import time

from .layout import conditioning_metadata, event_latent_range, validate_layout
from .component_probe import component_probe


MODES = ("native", "diagnostic", "spatial_marginal")


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


def spatial_marginal_attention(q_event, k_ref, v_ref, *, latent_lo,
                               frame_rows, attention=flash_attention_lse):
    """Read V at query time using original reference spatial marginal weights.

    For each query frame t, repeat V(t,s) across reference-key times u. The
    original Q/K softmax thus yields sum_s sum_u A(u,s) V(t,s). Process one
    query frame at a time; no full attention or spatial marginal is stored.
    """
    import torch

    if type(frame_rows) is not int or frame_rows < 1 or type(latent_lo) is not int:
        raise ValueError("frame_rows/latent_lo must be valid integer indices")
    if (q_event.ndim != 4 or k_ref.ndim != 4 or v_ref.shape != k_ref.shape
            or q_event.shape[0] != 1 or k_ref.shape[:2] != q_event.shape[:2]
            or k_ref.shape[-1] != q_event.shape[-1]
            or q_event.shape[-2] < 1 or k_ref.shape[-2] < 1
            or q_event.shape[-2] % frame_rows or k_ref.shape[-2] % frame_rows):
        raise ValueError("spatial marginal routing requires matching complete frames")
    count = q_event.shape[-2] // frame_rows
    temporal_length = k_ref.shape[-2] // frame_rows
    if latent_lo < 0 or latent_lo + count > temporal_length:
        raise ValueError("query temporal interval exceeds reference")
    output = torch.empty_like(q_event)
    for local in range(count):
        t = latent_lo + local
        target_values = v_ref[:, :, t * frame_rows:(t + 1) * frame_rows]
        repeated_values = target_values.repeat(1, 1, temporal_length, 1)
        group_out, _ = attention(
            q_event[:, :, local * frame_rows:(local + 1) * frame_rows],
            k_ref, repeated_values)
        output[:, :, local * frame_rows:(local + 1) * frame_rows].copy_(group_out)
        del repeated_values, group_out
    return output


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
    """Native + alpha*m_ref*(spatial-marginal same-time V readout - ref).

    At fixed input Q/K, this preserves native reference group mass and its
    spatial marginal for alpha in [0,1]. It is a nonnegative redistribution,
    hence can be represented as an input-dependent logit bias/mask. It is NOT
    a claim of mathematical novelty or preserved semantics across layers.
    """
    import torch

    if mode not in MODES or not math.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ValueError("invalid spatial router mode/alpha")
    if type(radius) is not int or type(time_offset) is not int or radius != 0 or time_offset != 0:
        raise ValueError("this diagnostic requires strict same-frame routing without offsets")
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
    ref, ref_lse = attention(query, keys, values)
    work_dtype = torch.float64 if q.dtype == torch.float64 else torch.float32
    log_mass = ref_lse.to(work_dtype) - full_lse[:, :, qa:qb].to(work_dtype)
    mass = log_mass.clamp(max=0).exp()
    old = full[:, :, qa:qb]
    changed = old
    if mode == "spatial_marginal":
        aligned = spatial_marginal_attention(
            query, keys, values, latent_lo=plan["latent_interval_half_open"][0],
            frame_rows=plan["frame_rows"], attention=attention)
        correction = mass.unsqueeze(-1) * (aligned.to(work_dtype) - ref.to(work_dtype))
        changed = (old.to(work_dtype) + alpha * correction).to(old.dtype)
    if diagnostics is not None:
        diagnostics.append(_bounded_stats(old, changed, mass, log_mass))
    if mode == "spatial_marginal":
        full[:, :, qa:qb].copy_(changed)
    return full.transpose(1, 2).reshape(1, q.shape[-2], heads * q.shape[-1])


class RouterState:
    def __init__(self, metadata, mode, alpha, radius, time_offset, start_frame,
                 end_frame, block_start, block_end, step_start, step_end,
                 run_id, audit_dir, num_blocks=50):
        if mode not in MODES or not math.isfinite(alpha) or not 0 <= alpha <= 1:
            raise ValueError("invalid router mode/alpha")
        if any(type(x) is not int for x in (radius, time_offset, block_start, block_end, step_start, step_end)):
            raise ValueError("router intervals and offsets must be integers")
        if radius != 0 or time_offset != 0 or not 0 <= block_start < block_end <= num_blocks or not 0 <= step_start < step_end:
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
        self.audit = {"schema": "h3-spatial-marginal-router-v1", "run_id": run_id,
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
                      "temporal_readouts": [], "component_readouts": [], "status": "installed"}
        self.audit["spatial_marginal"] = {
            "operator": "native + alpha*m_ref*(sum_s sum_u A_ref(u,s)*V(query_t,s) - A_ref*V)",
            "fixed_input_invariants": ["reference group mass", "reference spatial marginal", "other-key contributions"],
            "weights": "nonnegative convex mixture for alpha in [0,1]",
            "strict_time": "at alpha=1 all reference V comes from the query latent bin",
            "implementation": "one full attention, one reference attention, one all-reference attention per selected query frame",
            "limitations": "fixed grid positions are not tracked objects; reference V is contextual; equivalent nonnegative attention reweighting exists",
            "runtime_checks": "sampled output/mass finite and correction ratio; marginals proved by algebra and CPU tests, not materialized at runtime"}
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
            self.pending_stats.clear()
            if not summary["sampled_finite"]:
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
        if self.block == 25 and state.forward_index in (6, 10, 14):
            schedule = state.audit.get("sample_sigmas")
            if not isinstance(schedule, list) or len(schedule) <= state.forward_index:
                raise ValueError("component probe requires the actual sampler sigma schedule")
            observed = component_probe(q, k, v, self.plan)
            observed.update(block_index=self.block, forward_index=state.forward_index,
                            sampler_sigma_video=schedule[state.forward_index],
                            sigma_scope="actual Euler video sigma from sample_sigmas; not audio sigma")
            state.audit["component_readouts"].append(observed)
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
        if active and mode == "spatial_marginal" and state.alpha != 0:
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
