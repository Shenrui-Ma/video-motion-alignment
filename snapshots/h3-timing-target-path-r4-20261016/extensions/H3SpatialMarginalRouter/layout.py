"""Copied layout validation from sealed H3EventEmphasis; no inference mutation."""
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

