"""Reference-branch-only temporal RoPE diagnostic; not an automatic controller."""

import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

import torch

from .audited_flash import flash_attention_lse, _bounded_stats
from .layout import FRAME_RESCALE, validate_layout
from .architecture import architecture_contract


class TemporalRotation:
    """Post-native-RoPE extra rotation of H3's 16 split-half time pairs only."""
    def __init__(self, inv_freq, delta_frames):
        if not isinstance(inv_freq, torch.Tensor) or tuple(inv_freq.shape) != (16,):
            raise ValueError("actual checkpoint rope.inv_freq must have exactly 16 entries")
        if not inv_freq.is_floating_point():
            raise ValueError("rope.inv_freq must be floating point")
        self.inv_freq = inv_freq.detach().to(device="cpu", copy=True).contiguous()
        if not bool(torch.isfinite(self.inv_freq).all()):
            raise ValueError("rope.inv_freq contains nonfinite values")
        if isinstance(delta_frames, bool) or not math.isfinite(float(delta_frames)):
            raise ValueError("delta_frames must be a finite physical-frame offset")
        self.delta_frames = float(delta_frames)
        self.delta_rope = self.delta_frames * FRAME_RESCALE
        if not math.isfinite(self.delta_rope):
            raise ValueError("RoPE offset overflow")
        self.cache = {}

    def __call__(self, query):
        if query.ndim != 4 or query.shape[-1] != 128 or not query.is_floating_point():
            raise ValueError("H3 temporal rotation requires [B,H,N,128] floating point Q")
        if self.delta_frames == 0:
            return query
        work_dtype = torch.float64 if query.dtype == torch.float64 else torch.float32
        key = (str(query.device), work_dtype)
        if key not in self.cache:
            angles = self.inv_freq.to(device=query.device, dtype=work_dtype) * self.delta_rope
            self.cache[key] = (angles.cos(), angles.sin())
        cosine, sine = self.cache[key]
        first, second = query[..., :16].to(work_dtype), query[..., 48:64].to(work_dtype)
        rotated = query.clone()
        rotated[..., :16] = (first * cosine - second * sine).to(query.dtype)
        rotated[..., 48:64] = (first * sine + second * cosine).to(query.dtype)
        return rotated

    def metadata(self):
        return {"delta_physical_frames": self.delta_frames, "delta_rope_units": self.delta_rope,
                "fps": 24, "frame_rescale": FRAME_RESCALE,
                "frequency_source": "actual diffusion.rope.inv_freq checkpoint buffer; no assumed base",
                "inv_freq": self.inv_freq.double().tolist(), "inv_freq_dtype": str(self.inv_freq.dtype),
                "inv_freq_sha256": hashlib.sha256(self.inv_freq.view(torch.uint8).numpy().tobytes()).hexdigest(),
                "rotated_channel_pairs": [[0, 16], [48, 64]],
                "unchanged_channels": [[16, 48], [64, 128]]}


def phase_attention(q, k, v, heads, plan, *, rotation, alpha=1.0,
                    attention=flash_attention_lse, diagnostics=None):
    """Keep native reference mass; redistribute only its conditional probabilities.

    O' = O + alpha*m_ref*(O_ref(Q_rotated,K_ref,V_ref)-O_ref(Q,K_ref,V_ref)).
    The reference branch uses all video-reference keys, never the identity image.
    """
    if isinstance(alpha, bool) or not math.isfinite(float(alpha)) or not 0 <= alpha <= 1:
        raise ValueError("alpha must be finite and within [0,1]")
    if q.ndim != 4 or q.shape != k.shape or k.shape != v.shape or q.shape[0] != 1:
        raise ValueError("expected equal single-batch [B,H,N,D] self-attention tensors")
    if q.shape[1] != heads or q.shape[-1] != 128:
        raise ValueError("unexpected H3 heads/head dimension")
    if any(t.device != q.device or t.dtype != q.dtype for t in (k, v)):
        raise ValueError("QKV device/dtype mismatch")
    full, full_lse = attention(q, k, v)
    if alpha == 0 or rotation.delta_frames == 0:
        return full.transpose(1, 2).reshape(1, q.shape[-2], heads * 128)
    qa, qb = plan["query_interval_half_open"]
    ra, rb = plan["reference_video_segment"]
    if not 0 <= qa <= qb <= q.shape[-2] or not 0 <= ra < rb <= k.shape[-2]:
        raise ValueError("selected ranges exceed packed sequence")
    if qa == qb:
        return full.transpose(1, 2).reshape(1, q.shape[-2], heads * 128)
    if max(qa, ra) < min(qb, rb):
        raise ValueError("output-video queries must not overlap the reference-video segment")
    query, keys, values = q[:, :, qa:qb], k[:, :, ra:rb], v[:, :, ra:rb]
    original_ref, original_lse = attention(query, keys, values)
    rotated_query = rotation(query)
    rotated_ref, _ = attention(rotated_query, keys, values)
    work_dtype = torch.float64 if q.dtype == torch.float64 else torch.float32
    log_mass = original_lse.to(work_dtype) - full_lse[:, :, qa:qb].to(work_dtype)
    mass = log_mass.clamp(max=0).exp()
    before = full[:, :, qa:qb]
    changed = (before.to(work_dtype) + alpha * mass.unsqueeze(-1)
               * (rotated_ref.to(work_dtype) - original_ref.to(work_dtype))).to(before.dtype)
    if diagnostics is not None:
        diagnostics.append(_bounded_stats(before, changed, mass, log_mass))
    full[:, :, qa:qb].copy_(changed)
    return full.transpose(1, 2).reshape(1, q.shape[-2], heads * 128)


class PhaseState:
    def __init__(self, metadata, inv_freq, delta_frames, alpha, start_frame, end_frame,
                 block_start, block_end, step_start, step_end, run_id, audit_dir,
                 *, model_contract, model_ref=None, source_provenance=None):
        if isinstance(alpha, bool) or not math.isfinite(float(alpha)) or not 0 <= alpha <= 1:
            raise ValueError("alpha must be in [0,1]")
        if any(type(v) is not int for v in (block_start, block_end, step_start, step_end)):
            raise ValueError("block/step bounds must be integers")
        if not 0 <= block_start < block_end <= 50 or not 0 <= step_start < step_end <= 20:
            raise ValueError("expected half-open block bounds within [0,50] and step bounds within [0,20]")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", run_id):
            raise ValueError("invalid run_id")
        root = Path(audit_dir)
        if not root.is_absolute():
            raise ValueError("audit_dir must be absolute")
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / f"{run_id}.json"
        if self.path.exists():
            raise FileExistsError(self.path)
        self.metadata, self.rotation, self.alpha = metadata, TemporalRotation(inv_freq, delta_frames), float(alpha)
        self.start_frame, self.end_frame = start_frame, end_frame
        self.block_start, self.block_end, self.step_start, self.step_end = block_start, block_end, step_start, step_end
        self.forward_index, self.next_block = -1, 0
        if (type(model_contract.get("heads")) is not int or model_contract["heads"] < 1
                or (model_contract.get("head_dim"), model_contract.get("hidden_size"),
                    model_contract.get("num_blocks")) != (128, 5376, 50)):
            raise ValueError("invalid actual R17 model contract")
        self.model_contract, self.model_ref = model_contract, model_ref
        self.layout_object, self.plan, self.pending_stats = None, None, []
        self.audit = {"schema": "h3-phase-rope-r17-v1", "run_id": run_id, "status": "installed",
                      "model_contract": model_contract, "source_provenance": source_provenance,
                      "zero_path": "passed native attention function, no auxiliary Flash call",
                      "rotation": self.rotation.metadata(), "alpha": self.alpha,
                      "pixel_interval_inclusive": [start_frame, end_frame],
                      "block_interval_half_open": [block_start, block_end],
                      "step_interval_half_open": [step_start, step_end],
                      "backend": "aten._scaled_dot_product_flash_attention.default",
                      "mass_scope": "native reference probability mass at the same layer input; not constant across separate runs",
                      "sign_scope": "positive delta adds to query time coordinate; effect on output action lag is unknown",
                      "metadata": metadata, "created_unix": time.time(),
                      "started_calls": 0, "completed_calls": 0, "native_override_calls": 0,
                      "phase_calls": 0, "calls_by_block": [0] * 50, "calls_by_forward": [],
                      "direct_native_calls": 0,
                      "phase_by_block": [0] * 50, "phase_by_forward": [],
                      "completed_forward_calls": 0, "forward_summaries": []}
        self.write()

    def write(self):
        self.audit["updated_unix"] = time.time()
        temp = self.path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(self.audit, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
        os.replace(temp, self.path)

    def plan_for(self, layout):
        if layout is not self.layout_object:
            plan = validate_layout(self.metadata, layout, self.start_frame, self.end_frame)
            if tuple(layout.position_ids.shape) != (plan["seq_len"], 3):
                raise ValueError("unexpected packed position shape")
            for interval, key in (("key_interval_half_open", "key_first_time_coordinate"),
                                  ("query_interval_half_open", "query_first_time_coordinate")):
                actual = float(layout.position_ids[plan[interval][0], 0])
                if not math.isclose(actual, plan[key], abs_tol=1e-8, rel_tol=0):
                    raise ValueError("packed H3 time coordinate mismatch")
            if self.plan is not None and self.plan != plan:
                raise ValueError("packed layout changed")
            self.layout_object, self.plan = layout, plan
            self.audit["validated_layout"] = plan
        return self.plan

    def selected(self, block):
        return self.block_start <= block < self.block_end and self.step_start <= self.forward_index < self.step_end

    def finish_forward(self):
        summary = {"forward_index": self.forward_index, "completed_blocks": 50,
                   "phase_blocks": self.audit["phase_by_forward"][-1]}
        if self.pending_stats:
            blocks = [b for b, _ in self.pending_stats]
            rows = torch.stack([row for _, row in self.pending_stats]).float().cpu().tolist()
            summary.update(sampled_ref_mass_mean=sum(row[0] for row in rows) / len(rows),
                           sampled_ref_mass_max=max(row[1] for row in rows),
                           sampled_correction_ratio_mean=sum(row[2] for row in rows) / len(rows),
                           sampled_correction_ratio_max=max(row[2] for row in rows),
                           sampled_finite=all(row[3] == 1 for row in rows),
                           sampled_log_mass_positive_excess=max(row[4] for row in rows),
                           layer_stats=[{"block": block, "ref_mass_mean": row[0], "ref_mass_max": row[1],
                                         "correction_ratio": row[2], "finite": row[3] == 1,
                                         "log_mass_max": row[4]} for block, row in zip(blocks, rows)])
            self.pending_stats.clear()
            if not summary["sampled_finite"]:
                raise FloatingPointError("nonfinite sampled PhaseRoPE output")
        self.audit["forward_summaries"].append(summary)
        self.audit["completed_forward_calls"] += 1
        self.audit["status"] = "complete" if self.forward_index == 19 else "sampling"
        self.write()


class PhaseAttentionOverride:
    def __init__(self, state, plan, block):
        self.state, self.plan, self.block, self.calls = state, plan, block, 0

    def __call__(self, native, q, k, v, heads, **kwargs):
        if getattr(native, "__name__", None) != "attention_pytorch":
            raise ValueError("PhaseRoPE requires attention_pytorch")
        if kwargs.get("mask") is not None or not kwargs.get("skip_reshape") or kwargs.get("skip_output_reshape", False):
            raise ValueError("expected unmasked, preshaped native attention")
        expected = self.state.model_contract
        if (q.ndim != 4 or q.shape != k.shape or k.shape != v.shape or q.shape[0] != 1
                or q.shape[-2] != self.plan["seq_len"] or heads != expected["heads"]
                or q.shape[1] != heads or q.shape[-1] != expected["head_dim"]):
            raise ValueError("unexpected packed H3 attention shape")
        if any(t.device != q.device or t.dtype != q.dtype for t in (k, v)):
            raise ValueError("QKV device/dtype mismatch")
        if kwargs.get("enable_gqa", False) or kwargs.get("scale") not in (None, 128 ** -0.5):
            raise ValueError("custom attention scale/GQA unsupported")
        self.calls += 1
        if self.calls != 1:
            raise ValueError("expected one attention per block")
        state = self.state
        active = state.selected(self.block) and state.alpha != 0 and state.rotation.delta_frames != 0
        stats = []
        if active:
            output = phase_attention(q, k, v, heads, self.plan, rotation=state.rotation,
                                     alpha=state.alpha, diagnostics=stats)
        else:
            # wrap_attn passes its undecorated native function; kwargs forwarding is exact.
            output = native(q, k, v, heads, **kwargs)
            state.audit["direct_native_calls"] += 1
        if tuple(output.shape) != (1, q.shape[-2], expected["heads"] * expected["head_dim"]):
            raise ValueError("unexpected native/phase output width")
        state.audit["native_override_calls"] += 1
        if active:
            state.audit["phase_calls"] += 1
            state.audit["phase_by_block"][self.block] += 1
            state.audit["phase_by_forward"][state.forward_index] += 1
        if stats:
            state.pending_stats.append((self.block, stats[0]))
        if "first_attention" not in state.audit:
            state.audit["first_attention"] = {"qkv_shape": list(q.shape), "dtype": str(q.dtype),
                                              "device": str(q.device), "heads": heads,
                                              "returned_shape": list(output.shape)}
        return output


class PhaseBlockPatch:
    def __init__(self, state, block_index):
        self.state, self.block_index = state, block_index

    def __call__(self, args, extra_args):
        state = self.state
        try:
            if self.block_index != state.next_block:
                raise ValueError("unexpected block order; CFG/parallel interleaving unsupported")
            if self.block_index == 0:
                if state.model_ref is not None:
                    diffusion = state.model_ref()
                    if diffusion is None or architecture_contract(diffusion) != state.model_contract:
                        raise ValueError("actual model attention contract changed before forward")
                state.forward_index += 1
                if state.forward_index >= 20:
                    raise ValueError("more than 20 denoiser calls; expected Euler20 without CFG")
                state.audit["calls_by_forward"].append(0)
                state.audit["phase_by_forward"].append(0)
            plan = state.plan_for(args["layout"])
            options = args["transformer_options"]
            if options.get("block_index") != self.block_index or options.get("minimax_h3_layout") is not args["layout"]:
                raise ValueError("block/layout runtime identity mismatch")
            if options.get("optimized_attention_override") is not None:
                raise ValueError("cannot combine attention overrides")
            if self.block_index == 0:
                schedule = options.get("sample_sigmas")
                if schedule is None or schedule.ndim != 1 or len(schedule) != 21:
                    raise ValueError("PhaseRoPE requires an explicit Euler20 sigma schedule")
                values = schedule.detach().cpu().tolist()
                if not all(math.isfinite(v) for v in values) or values[-1] != 0 or any(a <= b for a, b in zip(values, values[1:])):
                    raise ValueError("invalid sigma schedule")
                if "sample_sigmas" in state.audit and values != state.audit["sample_sigmas"]:
                    raise ValueError("sigma schedule changed")
                state.audit["sample_sigmas"] = values
            state.audit["started_calls"] += 1
            override = PhaseAttentionOverride(state, plan, self.block_index)
            local_args, local_options = dict(args), dict(options)
            local_options["optimized_attention_override"] = override
            local_args["transformer_options"] = local_options
            result = extra_args["original_block"](local_args)
            if override.calls != 1:
                raise ValueError("attention override was not invoked exactly once")
            state.audit["completed_calls"] += 1
            state.audit["calls_by_block"][self.block_index] += 1
            state.audit["calls_by_forward"][state.forward_index] += 1
            state.next_block = (self.block_index + 1) % 50
            state.audit["last_completed_block"] = self.block_index
            if state.next_block == 0:
                state.finish_forward()
            return result
        except Exception as error:
            state.audit["status"], state.audit["error"] = "failed", repr(error)
            state.write()
            raise
