"""Task-local H3 event attention intervention; no changes to model weights or Core."""

import json
import math
import os
import re
import time
from pathlib import Path


FRAME_PER_TOKEN = (1, 4, 4, 4, 4)
FRAME_RESCALE = 5.0 / 3.0


def frame_spans(latent_t):
    if not isinstance(latent_t, int) or latent_t < 1:
        raise ValueError("latent_t must be a positive integer")
    return [FRAME_PER_TOKEN[i % 5] for i in range(latent_t)]


def event_latent_range(start_frame, end_frame, latent_t):
    """Inclusive pixel-frame interval -> half-open overlapping latent interval.

    These are H3 positional bins, not a claim about exact VAE receptive fields.
    """
    if type(start_frame) is not int or type(end_frame) is not int:
        raise ValueError("frame indices must be integers")
    spans = frame_spans(latent_t)
    if not 0 <= start_frame <= end_frame < sum(spans):
        raise ValueError("event must lie wholly within the reference frame bins")
    selected, cursor = [], 0
    for index, size in enumerate(spans):
        if cursor <= end_frame and cursor + size > start_frame:
            selected.append(index)
        cursor += size
    return selected[0], selected[-1] + 1


def _positive_int(value, name, allow_zero=False):
    if type(value) is not int or value < (0 if allow_zero else 1):
        raise ValueError(f"invalid {name}: {value!r}")
    return value


def conditioning_metadata(positive):
    """Keep only validated metadata, never retain conditioning tensors in patches."""
    if not isinstance(positive, (list, tuple)) or len(positive) != 1:
        raise ValueError("pilot requires exactly one positive conditioning entry")
    context, options = positive[0]
    shape = tuple(context.shape)
    if len(shape) != 3 or shape[0] != 1 or shape[1] < 1:
        raise ValueError(f"expected a single packed text presentation, got {shape}")
    if options.get("minimax_keyframes"):
        raise ValueError("keyframe conditioning is outside this Ref2VA pilot")
    if any(options.get(key) is not None for key in ("area", "mask", "control")):
        raise ValueError("regional/control conditioning is outside this pilot")
    raw_refs = options.get("minimax_refs")
    if not isinstance(raw_refs, (list, tuple)) or not raw_refs:
        raise ValueError("positive conditioning must contain minimax_refs")
    refs = []
    for index, raw in enumerate(raw_refs):
        kind = raw.get("kind")
        if kind not in ("image", "video", "video_audio", "audio"):
            raise ValueError(f"unsupported reference kind {kind!r}")
        item = {"kind": kind, "index": index}
        if kind != "audio":
            h = _positive_int(raw.get("latent_h"), "latent_h")
            w = _positive_int(raw.get("latent_w"), "latent_w")
            t = 1 if kind == "image" else _positive_int(raw.get("latent_t"), "latent_t")
            if h % 2 or w % 2:
                raise ValueError("reference dimensions must be divisible by the 2x2 patch")
            z = raw.get("latent")
            if z is None or tuple(z.shape) != (1, 24, t, h, w):
                raise ValueError(f"reference {index} latent tensor disagrees with its metadata")
            item.update(latent_t=t, latent_h=h, latent_w=w,
                        latent_shape=list(z.shape), frame_rows=(h // 2) * (w // 2))
        rt = 0 if kind == "image" else _positive_int(raw.get("ref_audio_t"), "ref_audio_t", True)
        if (kind == "video" and rt != 0) or (kind == "video_audio" and rt == 0):
            raise ValueError("reference video/audio kind disagrees with ref_audio_t")
        if rt:
            audio = raw.get("audio_latent")
            if audio is None or tuple(audio.shape) != (1, 32, 2, rt):
                raise ValueError("reference audio tensor disagrees with ref_audio_t")
        item["ref_audio_t"] = rt
        refs.append(item)
    if sum(r["kind"] in ("video", "video_audio") for r in refs) != 1:
        raise ValueError("pilot requires exactly one reference video")
    if sum(r["kind"] == "image" for r in refs) != 1:
        raise ValueError("pilot requires exactly one character reference image")
    return {"text_len": shape[1], "context_shape": list(shape), "refs": refs}


def _reference_span(ref):
    if ref["kind"] == "image":
        return 1.0
    if ref["kind"] == "audio":
        return float(ref["ref_audio_t"])
    return max(float(ref["ref_audio_t"]), sum(frame_spans(ref["latent_t"])) * FRAME_RESCALE)


def validate_layout(metadata, layout, start_frame, end_frame):
    """Rebuild the complete segment table from positive refs and compare exactly."""
    signature = tuple(layout.signature)
    if len(signature) != 5 or signature[0] != metadata["text_len"]:
        raise ValueError("runtime presentation length differs from the supplied positive")
    text_len, target_t, target_h, target_w, target_audio_t = signature
    for value, name in ((target_t, "target_t"), (target_h, "target_h"),
                        (target_w, "target_w"), (target_audio_t, "target_audio_t")):
        _positive_int(value, name, allow_zero=(name == "target_audio_t"))
    if target_h % 2 or target_w % 2:
        raise ValueError("target patch dimensions must be even")
    expected, offset, cursor = [], 0, float(text_len)

    def append(kind, rows):
        nonlocal offset
        start = offset
        expected.append((offset, offset + rows, kind))
        offset += rows
        return start

    append("text", text_len)
    reference = None
    image_segments = []
    for ref in metadata["refs"]:
        kind = ref["kind"]
        if kind == "image":
            a = append("ref_img", ref["frame_rows"])
            image_segments.append([a, offset])
        elif kind == "audio":
            if ref["ref_audio_t"]:
                append("ref_audio", ref["ref_audio_t"] * 2)
        else:
            if ref["ref_audio_t"]:
                append("ref_audio", ref["ref_audio_t"] * 2)
            a = append("ref_img", ref["latent_t"] * ref["frame_rows"])
            reference = (ref, a, offset, cursor)
        cursor += _reference_span(ref)
    append("audio", target_audio_t * 2)
    target_frame_rows = (target_h // 2) * (target_w // 2)
    target_start = append("video", target_t * target_frame_rows)
    actual = [tuple(s) for s in layout.segments]
    if actual != expected or layout.seq_len != offset:
        raise ValueError(f"runtime packed segment table disagrees with positive refs: {actual!r}")
    ref, ref_start, ref_stop, ref_origin = reference
    if (target_t, target_h, target_w) != (ref["latent_t"], ref["latent_h"], ref["latent_w"]):
        raise ValueError("pilot requires matching reference and target video geometries")
    lo, hi = event_latent_range(start_frame, end_frame, ref["latent_t"])
    key = (ref_start + lo * ref["frame_rows"], ref_start + hi * ref["frame_rows"])
    query = (target_start + lo * target_frame_rows, target_start + hi * target_frame_rows)
    if not ref_start <= key[0] < key[1] <= ref_stop:
        raise ValueError("event key slice escaped the reference video segment")
    if any(max(key[0], a) < min(key[1], b) for a, b in image_segments):
        raise ValueError("event key slice accidentally includes a reference image")
    pixel_prefix = sum(frame_spans(ref["latent_t"])[:lo])
    span_prefix = pixel_prefix * FRAME_RESCALE
    return {"seq_len": offset, "segments": expected, "signature": list(signature),
            "reference_index": ref["index"], "reference_kind": ref["kind"],
            "reference_video_segment": [ref_start, ref_stop],
            "reference_image_segments": image_segments,
            "target_video_segment": [target_start, offset],
            "latent_interval_half_open": [lo, hi],
            "pixel_interval_inclusive": [start_frame, end_frame],
            "position_bin_coverage_inclusive": [pixel_prefix,
                sum(frame_spans(ref["latent_t"])[:hi]) - 1],
            "key_interval_half_open": list(key), "query_interval_half_open": list(query),
            "key_first_time_coordinate": ref_origin + span_prefix,
            "query_first_time_coordinate": cursor + span_prefix,
            "frame_rows": target_frame_rows}


def duplicate_event_attention(native, q, k, v, heads, factor, key_interval, query_interval,
                              diagnostics=None, **kwargs):
    """Native full attention plus a native local-query recomputation; no N x N mask."""
    if type(factor) is not int or factor not in (1, 2):
        raise ValueError("only integer factors 1 and 2 are supported")
    if factor == 1:
        return native(q, k, v, heads, **kwargs)
    import torch
    if kwargs.get("mask") is not None or not kwargs.get("skip_reshape"):
        raise ValueError("event duplication requires native unmasked pre-shaped attention")
    if kwargs.get("skip_output_reshape", False):
        raise ValueError("expected native [B, sequence, heads*dim] output")
    if q.ndim != 4 or q.shape != k.shape or k.shape != v.shape or q.shape[0] != 1:
        raise ValueError("expected single-batch dense self-attention Q/K/V of equal shape")
    if q.shape[1] != heads or q.device != k.device or q.device != v.device:
        raise ValueError("attention head/device mismatch")
    if q.dtype != k.dtype or q.dtype != v.dtype:
        raise ValueError("attention dtype mismatch")
    ka, kb = key_interval
    qa, qb = query_interval
    if not (0 <= ka < kb <= k.shape[-2] and 0 <= qa < qb <= q.shape[-2]):
        raise ValueError("attention event slice outside packed sequence")
    out = native(q, k, v, heads, **kwargs)
    if tuple(out.shape) != (1, q.shape[-2], heads * q.shape[-1]):
        raise ValueError("unexpected native attention output shape")
    weighted = native(q[:, :, qa:qb, :],
                      torch.cat((k, k[:, :, ka:kb, :]), dim=-2),
                      torch.cat((v, v[:, :, ka:kb, :]), dim=-2), heads, **kwargs)
    if diagnostics is not None:
        before = _flat_prefix(out[:, qa:qb, :], 65536).to(torch.float32)
        after = _flat_prefix(weighted, 65536).to(torch.float32)
        difference = after - before
        diagnostics["weighted_vs_native_output_sample"] = {
            "sample_kind": "first_at_most_65536_flat_elements_of_selected_query_output",
            "sample_count": difference.numel(),
            "finite": bool(torch.isfinite(difference).all().item()),
            "max_absolute_difference": float(difference.abs().max().item()),
            "rms_difference": float(difference.square().mean().sqrt().item())}
    out[:, qa:qb, :].copy_(weighted)
    return out


def _flat_prefix(tensor, limit):
    """Logical flattened prefix without first copying a complete strided tensor."""
    import torch
    tensor = tensor.detach()
    if tensor.numel() <= limit:
        return tensor.reshape(-1)
    if tensor.ndim == 1:
        return tensor[:limit]
    per_item = math.prod(tensor.shape[1:])
    whole, remainder = divmod(limit, per_item)
    pieces = []
    if whole:
        pieces.append(tensor[:whole].reshape(-1))
    if remainder:
        pieces.append(_flat_prefix(tensor[whole], remainder))
    return pieces[0] if len(pieces) == 1 else torch.cat(pieces)


def _sample_stats(tensor):
    """Bounded first-call diagnostics; do not scan/copy the entire attention tensor."""
    import torch
    count = min(tensor.numel(), 65536)
    sample = _flat_prefix(tensor, count).to(dtype=torch.float32)
    return {"sample_kind": "first_at_most_65536_flat_elements", "sample_count": count,
            "total_elements": tensor.numel(), "finite": bool(torch.isfinite(sample).all().item()),
            "min": float(sample.min().item()), "max": float(sample.max().item()),
            "mean": float(sample.mean().item()), "rms": float(sample.square().mean().sqrt().item())}


class EventState:
    def __init__(self, metadata, factor, start_frame, end_frame, run_id, audit_dir,
                 num_blocks=50):
        if type(factor) is not int or factor not in (1, 2):
            raise ValueError("factor must be integer 1 or 2")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", run_id):
            raise ValueError("run_id must be a safe unique filename component")
        audit = Path(audit_dir)
        if not audit.is_absolute():
            raise ValueError("audit_dir must be an absolute task-local path")
        audit.mkdir(parents=True, exist_ok=True)
        self.path = audit / f"{run_id}.json"
        if self.path.exists():
            raise FileExistsError(f"refusing to overwrite an earlier intervention audit: {self.path}")
        self.metadata, self.factor = metadata, factor
        self.start_frame, self.end_frame = start_frame, end_frame
        self.num_blocks = num_blocks
        self.layout_object = None
        self.plan = None
        self.next_block = 0
        self.forward_index = -1
        self.audit = {"schema": 1, "run_id": run_id, "factor": factor,
                      "mechanism": "post-QKnorm/post-RoPE reference-event KV duplication for local target queries",
                      "factor_1_path": "original_block with original transformer_options and native Attention.forward",
                      "formal_planned_sampling_steps": 20, "expected_sampling_steps": None,
                      "expected_steps_source": "runtime sample_sigmas if available",
                      "expected_num_blocks": num_blocks,
                      "scope": "all DiT blocks and all forward calls; no token-refiner intervention",
                      "metadata": metadata, "pixel_interval_inclusive": [start_frame, end_frame],
                      "created_unix": time.time(), "started_calls": 0, "completed_calls": 0,
                      "native_override_calls": 0, "calls_by_block": [0] * num_blocks,
                      "calls_by_forward": [],
                      "completed_forward_calls": 0, "status": "installed"}
        self.write()

    def write(self):
        self.audit["updated_unix"] = time.time()
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(self.audit, indent=2, ensure_ascii=False) + "\n")
        os.replace(temporary, self.path)

    def plan_for(self, layout):
        if layout is not self.layout_object:
            plan = validate_layout(self.metadata, layout, self.start_frame, self.end_frame)
            positions = layout.position_ids
            if tuple(positions.shape) != (plan["seq_len"], 3):
                raise ValueError("runtime RoPE coordinate tensor shape mismatch")
            for interval, coordinate in (("key_interval_half_open", "key_first_time_coordinate"),
                                          ("query_interval_half_open", "query_first_time_coordinate")):
                actual = float(positions[plan[interval][0], 0])
                if not math.isclose(actual, plan[coordinate], rel_tol=0, abs_tol=1e-8):
                    raise ValueError("runtime RoPE time coordinates differ from expected reference ordering")
            if self.plan is not None and plan != self.plan:
                raise ValueError("layout changed during this fixed-geometry experiment")
            self.layout_object, self.plan = layout, plan
            self.audit["validated_layout"] = plan
            self.write()
        return self.plan


class LocalAttentionOverride:
    def __init__(self, state, plan, block_index):
        self.state, self.plan, self.block_index = state, plan, block_index
        self.calls = 0

    def __call__(self, native, q, k, v, heads, **kwargs):
        if getattr(native, "__name__", None) != "attention_pytorch":
            raise ValueError("pilot requires ComfyUI native attention_pytorch / SDPA")
        if q.shape[-2] != self.plan["seq_len"]:
            raise ValueError("attention sequence does not match validated packed layout")
        self.calls += 1
        if self.calls != 1:
            raise ValueError("expected exactly one attention call in each H3 DiT block")
        self.state.audit["native_override_calls"] += 1
        first = "first_attention_diagnostics" not in self.state.audit
        if first:
            ka, kb = self.plan["key_interval_half_open"]
            qa, qb = self.plan["query_interval_half_open"]
            self.state.audit["first_attention_diagnostics"] = {
                "block_index": self.block_index, "forward_index": self.state.forward_index,
                "native_function": native.__module__ + "." + native.__name__,
                "qkv_shape": list(q.shape), "dtype": str(q.dtype), "device": str(q.device),
                "key_slice_stats": _sample_stats(k[:, :, ka:kb, :]),
                "value_slice_stats": _sample_stats(v[:, :, ka:kb, :]),
                "query_slice_stats": _sample_stats(q[:, :, qa:qb, :]),
                "selected_keys": kb - ka, "selected_queries": qb - qa,
                "kv_length_after_duplication": k.shape[-2] + kb - ka,
                "mask": None, "logit_bias_equivalent": math.log(2.0)}
        out = duplicate_event_attention(native, q, k, v, heads, self.state.factor,
                                        self.plan["key_interval_half_open"],
                                        self.plan["query_interval_half_open"],
                                        diagnostics=self.state.audit["first_attention_diagnostics"] if first else None,
                                        **kwargs)
        if first:
            qa, qb = self.plan["query_interval_half_open"]
            self.state.audit["first_attention_diagnostics"]["weighted_output_slice_stats"] = _sample_stats(out[:, qa:qb, :])
        return out


class EventBlockPatch:
    def __init__(self, state, block_index):
        self.state, self.block_index = state, block_index

    def __call__(self, args, extra_args):
        state = self.state
        try:
            if self.block_index != state.next_block:
                raise ValueError("unexpected block order; parallel/CFG interleaving is unsupported")
            if self.block_index == 0:
                state.forward_index += 1
                state.audit["calls_by_forward"].append(0)
            plan = state.plan_for(args["layout"])
            options = args["transformer_options"]
            if options.get("block_index") != self.block_index:
                raise ValueError("runtime block index differs from registered patch")
            if options.get("minimax_h3_layout") is not args["layout"]:
                raise ValueError("block/layout identity mismatch")
            if options.get("optimized_attention_override") is not None:
                raise ValueError("refusing to combine this intervention with another attention override")
            if self.block_index == 0 and options.get("sample_sigmas") is not None:
                schedule = options["sample_sigmas"]
                if schedule.ndim != 1 or schedule.shape[0] < 2:
                    raise ValueError("expected a one-dimensional sampler sigma schedule")
                values = schedule.detach().cpu().tolist()
                if "sample_sigmas" in state.audit and values != state.audit["sample_sigmas"]:
                    raise ValueError("sampler sigma schedule changed within the run")
                state.audit["sample_sigmas"] = values
                state.audit["expected_sampling_steps"] = len(values) - 1
            state.audit["started_calls"] += 1
            if state.factor == 1:
                result = extra_args["original_block"](args)
            else:
                override = LocalAttentionOverride(state, plan, self.block_index)
                local_args = dict(args)
                local_options = dict(options)
                local_options["optimized_attention_override"] = override
                local_args["transformer_options"] = local_options
                result = extra_args["original_block"](local_args)
                if override.calls != 1:
                    raise ValueError("native attention override was not invoked exactly once")
            state.audit["completed_calls"] += 1
            state.audit["calls_by_block"][self.block_index] += 1
            state.audit["calls_by_forward"][state.forward_index] += 1
            state.next_block = (self.block_index + 1) % state.num_blocks
            if state.next_block == 0:
                state.audit["completed_forward_calls"] += 1
            state.audit["last_completed_block"] = self.block_index
            state.audit["last_completed_forward_index"] = state.forward_index
            state.audit["status"] = "sampling"
            state.write()
            return result
        except Exception as error:
            state.audit["status"] = "failed"
            state.audit["error"] = repr(error)
            state.write()
            raise
