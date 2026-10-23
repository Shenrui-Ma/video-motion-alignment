"""Standalone Comfy adapter. Install only in a future isolated experiment."""

import ast
import hashlib
import inspect
import itertools
import json
import math
import os
import re
import textwrap
import time
from pathlib import Path

import torch

from .core import PartialTemporalRotation, partial_phase_attention
from .layout import FRAME_RESCALE, conditioning_metadata, event_latent_range, frame_spans, validate_layout

# Same zero-based membership as frozen H3Study/schedule.py. Alpha is explicit.
SCHEDULES = {
    "native": (), "fixed": tuple(range(6, 15)), "early": tuple(range(9)),
    "late": tuple(range(11, 20)), "split": (*range(4), *range(15, 20)),
    "global_weak": tuple(range(20)), "all": tuple(range(20)),
}


def source_hash(function):
    node = ast.parse(textwrap.dedent(inspect.getsource(function))).body[0]
    # ast.dump differs between Python versions (e.g. empty type_params in 3.12).
    def normalized(value):
        if isinstance(value, ast.AST):
            return {"type": type(value).__name__, **{
                name: normalized(item) for name, item in ast.iter_fields(value)
                if item is not None and item != []}}
        if isinstance(value, list):
            return [normalized(item) for item in value]
        return value
    return hashlib.sha256(json.dumps(normalized(node), sort_keys=True).encode()).hexdigest()


def validate_runtime(h3, diffusion, model):
    """Fail closed if the audited position/attention path has changed."""
    if not isinstance(diffusion, h3.MiniMaxH3Model):
        raise TypeError("expected MiniMaxH3Model")
    if (tuple(diffusion.patch_size), diffusion.latents_dim, len(diffusion.blocks)) != ((1, 2, 2), 24, 50):
        raise ValueError("unexpected H3 architecture")
    if tuple(h3.FRAME_PER_TOKEN) != (1, 4, 4, 4, 4) or h3.FRAME_RESCALE != 5 / 3:
        raise ValueError("H3 temporal mapping changed")
    functions = {"_video_t_grid": h3._video_t_grid,
                 "rope_rotation_table": h3.rope_rotation_table,
                 "Attention.forward": h3.Attention.forward,
                 "MiniMaxH3Model.rope_freqs": h3.MiniMaxH3Model.rope_freqs}
    expected = json.loads(Path(__file__).with_name("source_contract.json").read_text())
    observed = {name: source_hash(function) for name, function in functions.items()}
    if observed != expected:
        raise ValueError("H3 source differs from audited contract; re-audit before enabling")
    if getattr(diffusion.rope_freqs, "__func__", None) is not h3.MiniMaxH3Model.rope_freqs:
        raise ValueError("instance-level RoPE replacement unsupported")
    for block in diffusion.blocks:
        if (block.attn.heads, block.attn.head_dim) != (56, 128):
            raise ValueError("unexpected H3 attention geometry")
        if getattr(block.attn.forward, "__func__", None) is not h3.Attention.forward:
            raise ValueError("patched attention forward unsupported")
    if getattr(h3.optimized_attention, "__name__", None) != "attention_pytorch":
        raise ValueError("requires --use-pytorch-cross-attention; Sage patch unsupported")
    options = model.model_options.get("transformer_options", {})
    if options.get("optimized_attention_override") is not None or options.get("patches_replace", {}).get("dit"):
        raise ValueError("existing attention or DiT block override unsupported")
    if any("attn" in key or "rope" in key for key in getattr(model, "object_patches", {})):
        raise ValueError("pending attention/RoPE object patches unsupported")
    return observed


class PartialPhaseState:
    def __init__(self, metadata, rotation, *, enabled, alpha, schedule,
                 start_frame, end_frame, block_start, block_end, run_id, audit_dir,
                 runtime_source_hashes, delta_mode="explicit"):
        if type(enabled) is not bool or isinstance(alpha, bool) or not math.isfinite(float(alpha)) or not 0 <= alpha <= 1:
            raise ValueError("invalid enabled/alpha")
        if schedule not in SCHEDULES:
            raise ValueError("unregistered schedule")
        if delta_mode not in ("explicit", "reference_origin"):
            raise ValueError("invalid delta_mode")
        if type(block_start) is not int or type(block_end) is not int or not 0 <= block_start < block_end <= 50:
            raise ValueError("invalid half-open block interval")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", run_id):
            raise ValueError("invalid run_id")
        reference = next(r for r in metadata["refs"] if r["kind"] in ("video", "video_audio"))
        event_latent_range(start_frame, end_frame, reference["latent_t"])
        root = Path(audit_dir)
        if not root.is_absolute():
            raise ValueError("audit_dir must be absolute")
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / (run_id + ".json")
        if self.path.exists():
            raise FileExistsError(self.path)
        self.metadata, self.rotation = metadata, rotation
        self.delta_mode = delta_mode
        self.enabled, self.alpha, self.active_steps = enabled, float(alpha), SCHEDULES[schedule]
        self.start_frame, self.end_frame = start_frame, end_frame
        self.block_start, self.block_end = block_start, block_end
        self.next_block, self.forward_index = 0, -1
        self.plan, self.layout_object, self.pending_stats = None, None, []
        self.audit = {
            "schema": "h3-partial-temporal-rope-v1", "run_id": run_id,
            "status": "installed", "enabled": enabled, "alpha": alpha,
            "schedule": schedule, "step_set_zero_based": list(self.active_steps),
            "block_interval_half_open": [block_start, block_end],
            "pixel_interval_inclusive": [start_frame, end_frame],
            "rotation": rotation.metadata(), "metadata": metadata,
            "delta_mode": delta_mode,
            "delta_resolved": delta_mode == "explicit",
            "runtime_source_hashes": runtime_source_hashes,
            "backend": "aten._scaled_dot_product_flash_attention.default",
            "correction": "alpha*m_ref*(A(R_selected(delta)Q,K_ref,V_ref)-A(Q,K_ref,V_ref))",
            "mass_scope": "native reference group mass at this layer input",
            "created_unix": time.time(), "completed_forwards": 0,
            "completed_blocks": 0, "compensated_calls": 0, "forward_summaries": [],
        }
        self.write()

    def write(self):
        self.audit["updated_unix"] = time.time()
        temp = self.path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(self.audit, indent=2, allow_nan=False) + "\n")
        os.replace(temp, self.path)

    def selected(self, block):
        return (self.enabled and self.alpha != 0 and not self.rotation.is_identity
                and self.block_start <= block < self.block_end
                and self.forward_index in self.active_steps)

    def plan_for(self, layout):
        if layout is not self.layout_object:
            plan = validate_layout(self.metadata, layout, self.start_frame, self.end_frame)
            if tuple(layout.position_ids.shape) != (plan["seq_len"], 3):
                raise ValueError("unexpected packed position shape")
            for interval, key in (("key_interval_half_open", "key_first_time_coordinate"),
                                  ("query_interval_half_open", "query_first_time_coordinate")):
                if not math.isclose(float(layout.position_ids[plan[interval][0], 0]), plan[key], abs_tol=1e-8, rel_tol=0):
                    raise ValueError("packed temporal coordinate mismatch")
            if self.plan is not None and plan != self.plan:
                raise ValueError("layout changed within a fixed-geometry experiment")
            if self.delta_mode == "reference_origin":
                delta, evidence = reference_origin_delta(self.metadata, layout, plan)
                if self.plan is not None and not math.isclose(delta, self.rotation.delta_frames, abs_tol=1e-8, rel_tol=0):
                    raise ValueError("reference-output origin offset changed")
                self.rotation = PartialTemporalRotation(self.rotation.inv_freq, delta,
                    [int(value) for value in self.rotation.frequency_mask])
                self.audit.update(rotation=self.rotation.metadata(), delta_resolved=True,
                    delta_derivation=evidence)
            self.plan, self.layout_object = plan, layout
            self.audit["validated_layout"] = plan
        return self.plan

    def finish_forward(self):
        summary = {"forward_index": self.forward_index, "compensated_blocks": len(self.pending_stats)}
        if self.pending_stats:
            blocks = [block for block, _ in self.pending_stats]
            values = torch.stack([row for _, row in self.pending_stats]).cpu().tolist()
            summary["layers"] = [{"block": b, "reference_mass_mean": v[0], "reference_mass_max": v[1],
                                       "log_mass_max": v[2], "correction_rms": v[3], "finite": bool(v[4])}
                                 for b, v in zip(blocks, values)]
            if not all(v[4] == 1 for v in values):
                raise FloatingPointError("nonfinite compensated output")
            self.pending_stats.clear()
        self.audit["forward_summaries"].append(summary)
        self.audit["completed_forwards"] += 1
        self.audit["status"] = "complete" if self.forward_index == 19 else "sampling"
        self.write()


class PartialAttentionOverride:
    def __init__(self, state, plan, block):
        self.state, self.plan, self.block, self.calls = state, plan, block, 0

    def __call__(self, native, q, k, v, heads, **kwargs):
        if getattr(native, "__name__", None) != "attention_pytorch":
            raise ValueError("requires native attention_pytorch")
        if kwargs.get("mask") is not None or not kwargs.get("skip_reshape") or kwargs.get("skip_output_reshape", False):
            raise ValueError("expected unmasked preshaped attention")
        if q.shape[-2] != self.plan["seq_len"] or heads != 56:
            raise ValueError("unexpected packed H3 attention shape")
        self.calls += 1
        if self.calls != 1:
            raise ValueError("expected one attention invocation per block")
        active = self.state.selected(self.block)
        stats = []
        out = partial_phase_attention(q, k, v, heads, self.plan,
            rotation=self.state.rotation, alpha=self.state.alpha, enabled=active, diagnostics=stats)
        if active:
            self.state.audit["compensated_calls"] += 1
            self.state.pending_stats.append((self.block, stats[0]))
        return out


class PartialBlockPatch:
    def __init__(self, state, block_index):
        self.state, self.block_index = state, block_index

    def __call__(self, args, extra_args):
        state = self.state
        try:
            if self.block_index != state.next_block:
                raise ValueError("unexpected block order; interleaved CFG/parallel calls unsupported")
            if self.block_index == 0:
                state.forward_index += 1
                if state.forward_index >= 20:
                    raise ValueError("requires 20 single-branch denoiser forwards")
            options = args["transformer_options"]
            if options.get("block_index") != self.block_index or options.get("minimax_h3_layout") is not args["layout"]:
                raise ValueError("block/layout identity mismatch")
            if options.get("optimized_attention_override") is not None:
                raise ValueError("cannot combine attention overrides")
            if self.block_index == 0:
                sigmas = options.get("sample_sigmas")
                if sigmas is None or sigmas.ndim != 1 or len(sigmas) != 21:
                    raise ValueError("requires explicit 20-step sigma schedule")
                values = sigmas.detach().cpu().tolist()
                if not all(math.isfinite(v) for v in values) or values[-1] != 0 or any(a <= b for a, b in itertools.pairwise(values)):
                    raise ValueError("invalid sigma schedule")
                if "sample_sigmas" in state.audit and values != state.audit["sample_sigmas"]:
                    raise ValueError("sigma schedule changed")
                state.audit["sample_sigmas"] = values
            override = PartialAttentionOverride(state, state.plan_for(args["layout"]), self.block_index)
            local_args, local_options = dict(args), dict(options)
            local_options["optimized_attention_override"] = override
            local_args["transformer_options"] = local_options
            result = extra_args["original_block"](local_args)
            if override.calls != 1:
                raise ValueError("attention override was not invoked exactly once")
            state.audit["completed_blocks"] += 1
            state.next_block = (self.block_index + 1) % 50
            if state.next_block == 0:
                state.finish_forward()
            return result
        except Exception as error:
            state.audit.update(status="failed", error=repr(error))
            state.write()
            raise


def reference_origin_delta(metadata, layout, plan):
    """Resolve the physical-frame offset from actual packed video coordinates."""
    reference = next(r for r in metadata["refs"] if r["kind"] in ("video", "video_audio"))
    count, rows = reference["latent_t"], plan["frame_rows"]
    coordinates = layout.position_ids
    if count < 1 or rows < 1 or tuple(coordinates.shape) != (plan["seq_len"], 3):
        raise ValueError("empty or malformed packed temporal layout")
    prefix, cursor = [], 0
    for span in frame_spans(count):
        prefix.append(cursor * FRAME_RESCALE)
        cursor += span
    origins = []
    for key in ("reference_video_segment", "target_video_segment"):
        start, stop = plan[key]
        if not 0 <= start < stop <= len(coordinates) or stop-start != count*rows:
            raise ValueError("video interval does not match temporal bin geometry")
        times = coordinates[start:stop:rows, 0].detach().cpu().tolist()
        if not all(math.isfinite(t) for t in times):
            raise ValueError("nonfinite packed temporal coordinates")
        if any(not math.isclose(t-times[0], offset, abs_tol=1e-7, rel_tol=0)
               for t, offset in zip(times, prefix)):
            raise ValueError("packed video coordinates violate H3 5/3 temporal mapping")
        origins.append(times[0])
    difference = origins[0] - origins[1]
    return difference / FRAME_RESCALE, {
        "reference_origin_rope": origins[0], "output_origin_rope": origins[1],
        "delta_rope_units": difference, "frame_rescale": FRAME_RESCALE,
        "delta_physical_frames": difference / FRAME_RESCALE,
        "formula": "(reference_origin_rope-output_origin_rope)/(5/3)",
        "validated_temporal_bins": count,
    }


class H3PartialRoPE:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",), "positive": ("CONDITIONING",),
            "enabled": ("BOOLEAN", {"default": False}),
            "frequency_mask": ("STRING", {"default": "[0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1]"}),
            "delta_frames": ("FLOAT", {"default": 0.0, "min": -240.0, "max": 240.0}),
            "alpha": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0}),
            "schedule": (list(SCHEDULES),),
            "start_frame": ("INT", {"default": 0, "min": 0}),
            "end_frame": ("INT", {"default": 60, "min": 0}),
            "block_start": ("INT", {"default": 0, "min": 0, "max": 49}),
            "block_end": ("INT", {"default": 50, "min": 1, "max": 50}),
            "run_id": ("STRING", {"default": "partial_rope_unique_run"}),
            "audit_dir": ("STRING", {"default": "/tmp/h3-partial-rope"}),
        }, "optional": {"delta_mode": (["explicit", "reference_origin"], {"default": "explicit"})}}

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "apply"
    CATEGORY = "research/H3PartialRoPE"

    def apply(self, model, positive, enabled, frequency_mask, delta_frames, alpha,
              schedule, start_frame, end_frame, block_start, block_end, run_id, audit_dir,
              delta_mode="explicit"):
        import comfy.ldm.minimax.model as h3

        diffusion = model.get_model_object("diffusion_model")
        hashes = validate_runtime(h3, diffusion, model)
        rotation = PartialTemporalRotation(diffusion.rope.inv_freq,
            0.0 if delta_mode == "reference_origin" else delta_frames, frequency_mask)
        state = PartialPhaseState(conditioning_metadata(positive), rotation, enabled=enabled,
            alpha=alpha, schedule=schedule, start_frame=start_frame, end_frame=end_frame,
            block_start=block_start, block_end=block_end, run_id=run_id, audit_dir=audit_dir,
            runtime_source_hashes=hashes, delta_mode=delta_mode)
        cloned = model.clone()
        for index in range(50):
            cloned.set_model_patch_replace(PartialBlockPatch(state, index), "dit", "double_block", index)
        return (cloned,)
