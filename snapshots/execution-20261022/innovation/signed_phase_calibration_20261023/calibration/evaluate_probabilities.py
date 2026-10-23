"""Offline sparse content retrieval diagnostics; never produces a control alpha.

Raw tensors stay on the inference host. All heads/probes and reference time bins
are retained in probabilities.npz; events only group rows in the small report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def validate_replay_gate(capture, capture_sha, gate, case, method):
    if gate.get("passed") is not True or gate.get("raw_full_AV_hook_exact_equal") is not True:
        raise ValueError("successful raw AV replay and passive gate required")
    if gate.get("case") != case["case_id"] or gate.get("method") != method:
        raise ValueError("replay case/method mismatch")
    if gate.get("qk_sha256") != capture_sha:
        raise ValueError("capture byte identity differs from verified replay")
    if gate.get("original_video_sha256") != case["video_provenance"][method]["sha256"]:
        raise ValueError("replayed trajectory differs from frozen event video")
    identity = gate.get("input_identity")
    if not isinstance(identity, dict) or any(k not in identity for k in
            ("state_file_sha256", "old_x0_file_sha256", "historical_capture_manifest_sha256", "packed_x")):
        raise ValueError("missing complete replay state identity")
    if identity != capture.get("forward_identity"):
        raise ValueError("capture and verified replay have different input states")
    for stream in ("video", "audio"):
        scores = gate.get("streams", {}).get(stream, {})
        if scores.get("hook_exact_equal") is not True or scores.get("historical_pass") is not True:
            raise ValueError("both historical AV streams must pass")


def normalized_content(raw, weight, epsilon):
    x = np.asarray(raw, dtype=np.float32)
    w = np.asarray(weight, dtype=np.float32)
    if x.ndim != 4 or not np.isfinite(x).all() or not np.isfinite(w).all():
        raise ValueError("finite [time, probe, head, dimension] input required")
    if w.shape not in ((x.shape[-1],), x.shape[-2:]):
        raise ValueError("unexpected per-head RMS weight shape")
    if not np.isfinite(epsilon) or epsilon <= 0:
        raise ValueError("invalid RMS epsilon")
    # FP32 reconstruction before this layer's explicit RoPE. Actual fused output
    # is a separate numerical check, not silently substituted for this tensor.
    return x * (1 / np.sqrt(np.mean(x * x, axis=-1, keepdims=True) + np.float32(epsilon))) * w


def retrieval_probabilities(query, key, valid_bins):
    q, k = np.asarray(query), np.asarray(key)
    valid = np.asarray(valid_bins, dtype=bool)
    if q.shape != k.shape or q.ndim != 4 or valid.shape != (q.shape[0],):
        raise ValueError("matching Q/K and bin mask required")
    if not valid.any() or not np.isfinite(q).all() or not np.isfinite(k).all():
        raise ValueError("nonempty finite retrieval support required")
    t, probes, heads, dim = q.shape
    result = np.zeros((heads, t, probes, t), dtype=np.float64)
    vi = np.flatnonzero(valid)
    for head in range(heads):
        logits = np.einsum("qpd,krd->qpkr", q[vi, :, head].astype(np.float64),
                           k[vi, :, head].astype(np.float64)) / np.sqrt(dim)
        maximum = logits.max(axis=-1, keepdims=True)
        grouped = maximum[..., 0] + np.log(np.exp(logits - maximum).mean(axis=-1))
        grouped -= grouped.max(axis=-1, keepdims=True)
        p = np.exp(grouped)
        p /= p.sum(axis=-1, keepdims=True)
        for row, qi in enumerate(vi):
            result[head, qi][:, vi] = p[row]
    return result


def validate_spans(spans, valid):
    spans = np.asarray(spans, dtype=np.float64)
    if spans.shape != (len(valid), 2) or not np.isfinite(spans).all():
        raise ValueError("actual inclusive physical frame spans required")
    if (spans[:, 0] > spans[:, 1]).any() or (spans < 0).any():
        raise ValueError("invalid physical frame spans")
    if len(spans) > 1 and (spans[1:, 0] <= spans[:-1, 1]).any():
        raise ValueError("overlapping or unordered physical bins")
    return spans


def quantiles(x):
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    if not len(x) or not np.isfinite(x).all():
        raise ValueError("empty/nonfinite observations must remain explicit")
    return {"count": len(x), "mean": float(x.mean()),
            **dict(zip(("min", "p10", "p25", "median", "p75", "p90", "max"),
                       map(float, np.quantile(x, [0, .1, .25, .5, .75, .9, 1]))))}


def summarize(p, reference_p, spans, valid_bins, case, method):
    if method not in ("native", "global_weak"):
        raise ValueError("only frozen historical controls permitted")
    valid = np.asarray(valid_bins, dtype=bool)
    spans = validate_spans(spans, valid)
    p, rp = np.asarray(p), np.asarray(reference_p)
    if p.shape != rp.shape or p.ndim != 4 or p.shape[1] != len(valid) or p.shape[3] != len(valid):
        raise ValueError("probability shape mismatch")
    for arr in (p, rp):
        if not np.isfinite(arr).all() or (arr < 0).any():
            raise ValueError("invalid probabilities")
        if not np.allclose(arr[:, valid].sum(axis=-1), 1, atol=1e-12, rtol=0):
            raise ValueError("valid query distributions must sum to one")
        if np.any(arr[..., ~valid]) or np.any(arr[:, ~valid]):
            raise ValueError("padded bins must not receive or produce probability mass")
    centers = spans.mean(axis=1)
    phase = centers[None, :, None] - np.einsum("htpj,j->htp", p, centers)
    self_phase = centers[None, :, None] - np.einsum("htpj,j->htp", rp, centers)
    entropy = -np.sum(np.where(p > 0, p * np.log(np.maximum(p, 1e-300)), 0), axis=-1)
    entropy /= np.log(valid.sum()) if valid.sum() > 1 else 1
    peaks = np.argmax(p, axis=-1)
    rows = []
    for event in case["frozen_events"]:
        interval, source = event[method], event["source"]
        qi = np.flatnonzero(valid & (spans[:, 0] <= interval[1]) & (spans[:, 1] >= interval[0]))
        ki = np.flatnonzero(valid & (spans[:, 0] <= source[1]) & (spans[:, 1] >= source[0]))
        base = {"event_id": event["id"], "query_interval": interval,
                "reference_interval": source, "query_bins": qi.tolist(), "reference_bins": ki.tolist(),
                "visual_midpoint_offset_frames": event["midpoint_offsets_frames"][method],
                "visual_offset_interval_frames": event["offset_uncertainty_frames"][method]}
        if not len(qi) or not len(ki):
            rows.append({**base, "status": "missing_event_bin_support"})
            continue
        mass = p[:, qi][..., ki].sum(axis=-1)
        rows.append({**base, "status": "measured_sparse_retrieval",
                     "signed_phase_frames": quantiles(phase[:, qi]),
                     "normalized_entropy": quantiles(entropy[:, qi]),
                     "reference_event_mass": quantiles(mass),
                     "uniform_event_mass": float(len(ki) / valid.sum()),
                     "peak_in_reference_event_fraction": float(np.isin(peaks[:, qi], ki).mean()),
                     "reference_self_phase_frames": quantiles(self_phase[:, qi]),
                     "self_bias_subtracted_phase_diagnostic": quantiles((phase - self_phase)[:, qi])})
    return {"case_id": case["case_id"], "method": method,
            "all_head_count": p.shape[0], "all_probe_count": p.shape[2],
            "valid_time_bins": np.flatnonzero(valid).tolist(), "events": rows,
            "scope": "sparse preRoPE content retrieval; no alpha or learned selection",
            "frame_coordinate": "nominal physical frame spans of position bins; not exact VAE receptive fields",
            "aggregation": "all observations retained; signed mean is accompanied by full spread and entropy"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capture", type=Path)
    ap.add_argument("--case", required=True)
    ap.add_argument("--method", choices=("native", "global_weak"), required=True)
    ap.add_argument("--replay-gate", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=Path(__file__).with_name("FROZEN_EVENTS.json"))
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    import torch  # Existing remote inference runtime; never downloads a dependency.
    capture = torch.load(args.capture, map_location="cpu", weights_only=True)
    if capture.get("schema") != "h3-passive-qk-capture-v1":
        raise ValueError("unexpected capture schema")
    if capture["step_zero_based"] not in (9, 19) or capture["layer_zero_based"] != 25:
        raise ValueError("capture outside frozen observation plan")
    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes)
    case = next(x for x in manifest["cases"] if x["case_id"] == args.case)
    capture_sha = hashlib.sha256(args.capture.read_bytes()).hexdigest()
    gate_bytes = args.replay_gate.read_bytes()
    validate_replay_gate(capture, capture_sha, json.loads(gate_bytes), case, args.method)
    def array(key):
        value = capture[key]
        return value.detach().float().numpy() if isinstance(value, torch.Tensor) else np.asarray(value)
    qc = normalized_content(array("raw_Q_C"), array("q_norm_weight"), capture["q_norm_eps"])
    qr = normalized_content(array("raw_Q_R"), array("q_norm_weight"), capture["q_norm_eps"])
    kr = normalized_content(array("raw_K_R"), array("k_norm_weight"), capture["k_norm_eps"])
    valid = np.asarray(capture["valid_bins"], dtype=bool)
    spans = array("physical_frame_spans_inclusive")
    p = retrieval_probabilities(qc, kr, valid)
    rp = retrieval_probabilities(qr, kr, valid)
    summary = summarize(p, rp, spans, valid, case, args.method)
    summary.update(capture_sha256=capture_sha,
                   replay_gate_sha256=hashlib.sha256(gate_bytes).hexdigest(),
                   event_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
                   step_zero_based=capture["step_zero_based"], layer_zero_based=25,
                   numerical_definition="FP32 eager RMS from raw projection; FP64 sparse logits/LSE/softmax",
                   actual_fused_agreement="separate replay numerical audit required")
    args.output.mkdir(parents=True)
    np.savez_compressed(args.output / "probabilities.npz", canvas=p, reference=rp,
                        valid_bins=valid, physical_frame_spans_inclusive=spans,
                        spatial_ids=np.asarray(capture["spatial_ids"]))
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"case": args.case, "method": args.method, "events": len(summary["events"]),
                      "output": str(args.output), "capture_sha256": summary["capture_sha256"]}))


if __name__ == "__main__":
    main()
