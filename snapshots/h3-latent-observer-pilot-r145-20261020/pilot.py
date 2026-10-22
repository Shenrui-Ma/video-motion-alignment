"""Bounded CPU readout of existing H3 clean latents; never imports model/VAE code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

os.environ["CUDA_VISIBLE_DEVICES"] = ""
for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_name] = "4"

import torch
import torch.nn.functional as F

torch.set_num_threads(4)
torch.set_num_interop_threads(1)

POLICY = {
    "version": "r145-first-pilot-v1",
    "shape": [1, 24, 32, 46, 82],
    "valid_frames": 105,
    "pure_valid_bins": 31,
    "difference": "abs(z[t+1]-z[t]); adaptive spatial mean 4x4; 24 channels",
    "matching": "2x2 latent patch (96 dimensions); local radius2; cosine; reciprocal unique top1",
    "match_radius": 2, "tie_margin": 1e-6, "norm_epsilon": 1e-12,
    "flow_descriptor": "4x4 spatial cells: mean dx,dy,displacement magnitude of accepted matches",
    "cell_minimum_support": 0.2,
    "lag_radius_bins": 6, "distinct_peak_exclusion_bins": 1,
    "relative_gap_minimum": 0.1, "normalized_mse_maximum": 0.5,
    "minimum_common_fraction": 0.8,
    "minimum_rms": 1e-6, "minimum_temporal_rms": 1e-6,
    "score": "fixed common central anchors; independently whole-trace RMS normalized MSE",
    "lag_sign": "positive means target occurs later in latent-bin index",
    "physical_units": "report actual paired transition-center differences, never bin*4",
    "temporal_interpolation": False, "phase_mean_removal": False,
    "spatial_scope": "complete spatial grid; no target label or ROI fitting",
    "threshold_scope": "predeclared exploratory confidence rules; not original pose-policy thresholds",
    "real_steps": list(range(10)), "new_model_or_VAE_forwards": 0,
}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as f:
        json.dump(obj, f, ensure_ascii=False, allow_nan=False, indent=2)
        f.write("\n")


def bin_table(n=32):
    rows = []
    start = 0
    for i in range(n):
        width = (1, 4, 4, 4, 4)[i % 5]
        rows.append({"bin": i, "frames": [start, start + width - 1],
                     "center_frame": start + (width - 1) / 2,
                     "fully_valid": start + width <= POLICY["valid_frames"]})
        start += width
    return rows


def patchify(z):
    # T,C,H,W -> T,H/2,W/2,C*2*2, matching H3 spatial patchification.
    t, c, h, w = z.shape
    return z.reshape(t, c, h // 2, 2, w // 2, 2).permute(
        0, 2, 4, 1, 3, 5).reshape(t, h // 2, w // 2, c * 4)


def local_best(left, right, h, w):
    n, p, _ = left.shape
    positions = torch.arange(p)
    rr, cc = positions // w, positions % w
    scores, targets = [], []
    radius = POLICY["match_radius"]
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            yy, xx = rr + dy, cc + dx
            valid = (yy >= 0) & (yy < h) & (xx >= 0) & (xx < w)
            index = yy.clamp(0, h - 1) * w + xx.clamp(0, w - 1)
            value = (left * right[:, index]).sum(-1)
            value[:, ~valid] = -torch.inf
            scores.append(value)
            targets.append(index)
    scores = torch.stack(scores, -1)
    best, slot = scores.topk(2, dim=-1)
    indices = torch.stack(targets, -1).unsqueeze(0).expand(n, -1, -1)
    chosen = indices.gather(2, slot[:, :, :1]).squeeze(-1)
    return chosen, best[:, :, 0], best[:, :, 0] - best[:, :, 1]


def descriptions(z):
    start = time.perf_counter()
    delta = (z[1:] - z[:-1]).abs()
    difference = F.adaptive_avg_pool2d(delta, (4, 4)).flatten(1)
    diff_seconds = time.perf_counter() - start
    start = time.perf_counter()
    patches = patchify(z)
    t, h, w, d = patches.shape
    patches = patches.reshape(t, h * w, d)
    norm = patches.norm(dim=-1)
    unit = patches / norm.clamp_min(POLICY["norm_epsilon"]).unsqueeze(-1)
    fi, cosine, margin = local_best(unit[:-1], unit[1:], h, w)
    bi, _, reverse_margin = local_best(unit[1:], unit[:-1], h, w)
    pos = torch.arange(h * w).unsqueeze(0).expand(t - 1, -1)
    accepted = ((bi.gather(1, fi) == pos)
                & (margin > POLICY["tie_margin"])
                & (reverse_margin.gather(1, fi) > POLICY["tie_margin"])
                & (norm[:-1] > POLICY["norm_epsilon"])
                & (norm[1:].gather(1, fi) > POLICY["norm_epsilon"]))
    dx = (fi % w - pos % w).float()
    dy = (fi // w - pos // w).float()
    velocity = torch.stack((dx, dy, (dx.square() + dy.square()).sqrt()), 1)
    mask = accepted.float().reshape(t - 1, 1, h, w)
    support = F.adaptive_avg_pool2d(mask, (4, 4))
    flow = F.adaptive_avg_pool2d(
        velocity.reshape(t - 1, 3, h, w) * mask, (4, 4)) / support.clamp_min(1e-12)
    valid = (support >= POLICY["cell_minimum_support"]).expand(-1, 3, -1, -1)
    flow_seconds = time.perf_counter() - start
    count = accepted.sum(1).clamp_min(1)
    details = {
        "patch_grid": [h, w], "patch_channels": d,
        "accepted_fraction": accepted.float().mean(1).tolist(),
        "mean_cosine_accepted": ((cosine * accepted).sum(1) / count).tolist(),
        "mean_margin_accepted": ((margin * accepted).sum(1) / count).tolist(),
        "mean_displacement_patches": (
            (velocity[:, 2] * accepted).sum(1) / count).tolist(),
        "spatial_support_4x4": support.flatten(1).tolist(),
    }
    return {
        "difference": {"features": difference, "mask": torch.ones_like(difference, dtype=torch.bool),
                       "seconds": diff_seconds},
        "local_match": {"features": flow.flatten(1), "mask": valid.flatten(1),
                        "seconds": flow_seconds, "matching": details},
    }


def stats(item):
    f, mask = item["features"], item["mask"]
    raw_rms = float(f[mask].square().mean().sqrt()) if mask.any() else 0.0
    temporal_rms = float(f.std(dim=0, unbiased=False).square().mean().sqrt())
    return {"raw_rms": raw_rms, "temporal_rms": temporal_rms,
            "available_fraction": float(mask.float().mean()),
            "per_transition_rms": f.square().mean(1).sqrt().tolist()}


def readout(source, target):
    sf, tf = source["features"], target["features"]
    sm, tm = source["mask"], target["mask"]
    assert sf.shape == tf.shape and sf.ndim == 2
    n = len(sf)
    radius = POLICY["lag_radius_bins"]
    anchors = torch.arange(radius, n - radius)
    ss, ts = stats(source), stats(target)
    reasons = []
    for label, s in (("source", ss), ("target", ts)):
        if s["raw_rms"] < POLICY["minimum_rms"]:
            reasons.append(label + "_static_or_no_motion")
        if s["temporal_rms"] < POLICY["minimum_temporal_rms"]:
            reasons.append(label + "_temporally_uninformative")
    sn = sf / max(ss["raw_rms"], 1e-12)
    tn = tf / max(ts["raw_rms"], 1e-12)
    curve = []
    centers = torch.tensor([x["center_frame"] for x in bin_table(n + 1)])
    transition_centers = (centers[:-1] + centers[1:]) / 2
    for lag in range(-radius, radius + 1):
        common = sm[anchors] & tm[anchors + lag]
        coverage = float(common.float().mean())
        cost = float((sn[anchors] - tn[anchors + lag])[common].square().mean()) if common.any() else None
        offsets = transition_centers[anchors + lag] - transition_centers[anchors]
        curve.append({"lag_bins": lag, "normalized_mse": cost,
                      "common_fraction": coverage,
                      "physical_frame_offsets": sorted(set(offsets.tolist())),
                      "mean_physical_offset": float(offsets.mean())})
    candidates = [x for x in curve if x["normalized_mse"] is not None
                  and x["common_fraction"] >= POLICY["minimum_common_fraction"]]
    if not candidates:
        return {"status": "unknown", "reasons": reasons + ["insufficient_common_support"],
                "best": None, "curve": curve, "source_stats": ss, "target_stats": ts}
    best = min(candidates, key=lambda x: x["normalized_mse"])
    rivals = [x for x in candidates if abs(x["lag_bins"] - best["lag_bins"]) > POLICY["distinct_peak_exclusion_bins"]]
    rival = min(rivals, key=lambda x: x["normalized_mse"])
    gap = (rival["normalized_mse"] - best["normalized_mse"]) / max(rival["normalized_mse"], 1e-12)
    if abs(best["lag_bins"]) == radius:
        reasons.append("search_boundary")
    if best["normalized_mse"] > POLICY["normalized_mse_maximum"]:
        reasons.append("large_normalized_residual")
    if gap < POLICY["relative_gap_minimum"]:
        reasons.append("ambiguous_distinct_peak")
    return {"status": "candidate" if not reasons else "unknown", "reasons": reasons,
            "best": best, "relative_distinct_gap": gap, "distinct_rival": rival,
            "anchors_transition_indices": anchors.tolist(),
            "source_stats": ss, "target_stats": ts, "curve": curve}


def synthetic_checks():
    # Isolated deterministic tensor generator; no model and no video interpolation.
    generator = torch.Generator().manual_seed(145)
    base = torch.randn(24, 16, 24, generator=generator)
    increments = torch.randint(-1, 2, (31, 2), generator=generator)
    positions = increments.cumsum(0)
    z = torch.stack([torch.roll(base, (int(y) * 2, int(x) * 2), (1, 2))
                     for y, x in positions])
    cases = [("zero", z, z, 0), ("delay_3_bins", z, z.roll(3, 0), 3),
             ("advance_3_bins", z, z.roll(-3, 0), -3),
             ("static", z[:1].expand_as(z), z[:1].expand_as(z), None),
             ("repeat_period_5", z[:5].repeat(7, 1, 1, 1)[:31],
              z[:5].repeat(7, 1, 1, 1)[:31], None)]
    rows = []
    for name, a, b, expected in cases:
        sa, sb = descriptions(a), descriptions(b)
        for method in sa:
            result = readout(sa[method], sb[method])
            passed = (result["status"] == "unknown") if expected is None else (
                result["status"] == "candidate" and result["best"]["lag_bins"] == expected)
            rows.append({"case": name, "method": method, "expected_lag_bins": expected,
                         "passed": passed, "readout": result})
    return {"all_passed": all(x["passed"] for x in rows), "rows": rows,
            "scope": "synthetic tensor/indices and ambiguity controls, not video-motion truth"}


def load_tensor(path, expected_sha=None):
    path = Path(path)
    actual = digest(path)
    if expected_sha is not None and actual != expected_sha:
        raise ValueError("file hash mismatch: " + str(path))
    payload = torch.load(path, map_location="cpu", weights_only=True)
    value = payload if isinstance(payload, torch.Tensor) else payload["video"]
    if list(value.shape) != POLICY["shape"] or value.dtype != torch.float32:
        raise ValueError("unexpected reference/endpoint tensor")
    if not bool(torch.isfinite(value).all()):
        raise ValueError("nonfinite latent")
    return value[0, :, :POLICY["pure_valid_bins"]].permute(1, 0, 2, 3).contiguous(), actual


def compact_description(item):
    return {k: v for k, v in item.items() if k not in ("features", "mask")} | {"statistics": stats(item)}


def run(root, output):
    start = time.perf_counter()
    output = Path(output)
    output.mkdir(exist_ok=False)
    write(output / "POLICY.json", POLICY)
    controls = synthetic_checks()
    write(output / "SYNTHETIC.json", controls)
    # Failed synthetic checks remain visible; actual rows are exploratory raw readouts,
    # never promoted as an eligible controller and no threshold changes occur.
    manifest = json.loads((root / "configs/CONDITION_CACHE.json").read_text())
    reference = next(x for x in manifest["tensors"] if x["role"] == "reference_vae_latent")
    ref, ref_sha = load_tensor(reference["file"], reference["sha256"])
    source = descriptions(ref)
    write(output / "SOURCE.json", {
        "reference": reference, "actual_sha256": ref_sha,
        "bins": bin_table(), "retained_bins": [0, 30],
        "omitted_mixed_bin": {"bin": 31, "frames": [103, 106], "valid_frames": [103, 104]},
        "methods": {k: compact_description(v) for k, v in source.items()},
    })
    rows = []
    run_id = "r144_short_0358_seed2026101701_visible_only"
    for step in POLICY["real_steps"]:
        path = root / "audit/counterfactual" / (run_id + "_snapshots") / f"step{step:03d}_native.pt"
        tick = time.perf_counter()
        latent, sha = load_tensor(path)
        read_seconds = time.perf_counter() - tick
        observed = descriptions(latent)
        results = {k: readout(source[k], observed[k]) for k in source}
        row = {"step": step, "file": str(path), "file_sha256": sha,
               "read_hash_load_seconds": read_seconds,
               "methods": {k: compact_description(v) | {"readout": results[k]}
                           for k, v in observed.items()},
               "total_seconds": time.perf_counter() - tick}
        write(output / f"step{step:03d}.json", row)
        rows.append(row)
        print(json.dumps({"step": step, "seconds": row["total_seconds"],
                          "results": {k: {"status": v["status"], "best": v["best"],
                                          "reasons": v["reasons"]} for k, v in results.items()}}), flush=True)
    # Only after immutable readouts exist, attach available independent RGB labels.
    labels = []
    for response_path in sorted((root / "audit/observations").glob("*/response.json")):
        response = json.loads(response_path.read_text())
        step = response.get("physical_index")
        if step not in POLICY["real_steps"]:
            continue
        observer_path = Path(response["observer"]["file"])
        observer = json.loads(observer_path.read_text())
        windows = []
        for row in observer["windows"]:
            windows.append({
                "window": row["window"], "feature": row["feature"],
                "baseline": row.get("baseline"),
                "thresholds": {
                    threshold: {
                        "status": measurement["status"],
                        "flags": measurement.get("flags", []),
                        "reliable_lag_frames": measurement.get("reliable_lag_frames"),
                        "best_lag_frames": (measurement.get("best") or {}).get("lag_frames"),
                        "best_error": (measurement.get("best") or {}).get("error"),
                        "gain": measurement.get("relative_error_reduction_after_local_shift"),
                    }
                    for threshold, measurement in row["measurements"].items()
                },
            })
        labels.append({"step": step, "response_sha256": digest(response_path),
                       "observer_sha256": digest(observer_path),
                       "decoder_stage_seconds": response.get("decoder_stage_seconds"),
                       "pose_wall_seconds": response.get("pose_process", {}).get("wall_seconds"),
                       "scan_seconds": observer.get("scan_seconds"),
                       "windows": windows})
    write(output / "RGB_LABELS_UNTUNED.json", labels)
    summary = {"policy": POLICY, "code_sha256": digest(__file__),
               "synthetic_all_passed": controls["all_passed"],
               "rows": [{"step": x["step"], "total_seconds": x["total_seconds"],
                         "methods": {k: {"seconds": v["seconds"], "readout": v["readout"]}
                                     for k, v in x["methods"].items()}} for x in rows],
               "wall_seconds": time.perf_counter() - start, "threads": torch.get_num_threads(),
               "torch": str(torch.__version__), "CUDA_initialized": torch.cuda.is_initialized(),
               "GPU_model_VAE_forwards": 0, "rgb_label_count": len(labels),
               "scope": "Exploratory observer pilot, no control decisions or threshold fitting"}
    write(output / "SUMMARY.json", summary)
    print(json.dumps({"finished": True, "wall_seconds": summary["wall_seconds"],
                      "synthetic_all_passed": controls["all_passed"],
                      "CUDA_initialized": summary["CUDA_initialized"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--synthetic-only", action="store_true")
    args = parser.parse_args()
    if args.synthetic_only:
        write(args.output, synthetic_checks())
    else:
        if args.root is None:
            parser.error("--root required")
        run(args.root, args.output)
