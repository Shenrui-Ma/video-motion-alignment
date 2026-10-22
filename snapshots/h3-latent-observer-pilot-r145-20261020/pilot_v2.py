"""Two bounded CPU diagnostics; thresholds and spatial descriptors come from v1."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

import pilot as v1

torch = v1.torch
POLICY = {
    **v1.POLICY,
    "version": "r145-v2-localization",
    "changes": [
        "independently subtract each clip's native-bin mod5 mean, then v1 difference",
        "v1 unmodified matching descriptor: each 4x4 tile, 4/8 transition windows",
    ],
    "phase_counts": [7, 6, 6, 6, 6],
    "phase_risk": "same-phase centering can remove genuine slow or periodic motion",
    "window_lengths": [4, 8],
    "window_stride": 1,
    "scan_anchors": [6, 23],
    "scan_count_per_clip": 416,
    "scan_domain_reason": "same fixed common lag support as v1; no edge-specific lag truncation",
    "normalization": "whole trace per tile RMS; unchanged cost and confidence thresholds",
    "local_information_gate": "same minimum RMS/temporal-RMS thresholds on the scored window",
    "phase_mean_removal": "only phase_difference; spatial matching remains unchanged",
    "rgb_labels": "read only after all latent outputs exist; no parameter fitting",
}


def phase_difference(z):
    tick = time.perf_counter()
    centered = z.clone()
    for phase in range(5):
        centered[phase::5] -= z[phase::5].mean(0)
    f = v1.F.adaptive_avg_pool2d(
        (centered[1:] - centered[:-1]).abs(), (4, 4)).flatten(1)
    return {"features": f, "mask": torch.ones_like(f, dtype=torch.bool),
            "seconds": time.perf_counter() - tick}


def tile_item(item, y, x):
    n = len(item["features"])
    return {k: item[k].reshape(n, 3, 4, 4)[:, :, y, x]
            for k in ("features", "mask")}


def window_readout(source, target, start, length):
    """Identical v1 lag scoring; spatial/time support is explicitly localized."""
    sf, tf = source["features"], target["features"]
    sm, tm = source["mask"], target["mask"]
    ss, ts = v1.stats(source), v1.stats(target)
    sn, tn = sf / max(ss["raw_rms"], 1e-12), tf / max(ts["raw_rms"], 1e-12)
    anchors = torch.arange(start, start + length)
    centers = torch.tensor([x["center_frame"] for x in v1.bin_table(len(sf) + 1)])
    tc = (centers[:-1] + centers[1:]) / 2
    curve = []
    for lag in range(-POLICY["lag_radius_bins"], POLICY["lag_radius_bins"] + 1):
        common = sm[anchors] & tm[anchors + lag]
        cost = float((sn[anchors] - tn[anchors + lag])[common].square().mean()) if common.any() else None
        curve.append({"lag_bins": lag, "normalized_mse": cost,
                      "common_fraction": float(common.float().mean()),
                      "physical_frame_offsets": sorted(set((tc[anchors + lag] - tc[anchors]).tolist()))})
    viable = [x for x in curve if x["normalized_mse"] is not None
              and x["common_fraction"] >= POLICY["minimum_common_fraction"]]
    reasons = []
    best, rival, gap = None, None, None
    if not viable:
        reasons.append("insufficient_common_support")
    else:
        best = min(viable, key=lambda x: x["normalized_mse"])
        rivals = [x for x in viable
                  if abs(x["lag_bins"] - best["lag_bins"]) > POLICY["distinct_peak_exclusion_bins"]]
        if rivals:
            rival = min(rivals, key=lambda x: x["normalized_mse"])
            gap = (rival["normalized_mse"] - best["normalized_mse"]) / max(rival["normalized_mse"], 1e-12)
        if gap is None or gap < POLICY["relative_gap_minimum"]:
            reasons.append("ambiguous_distinct_peak")
        if abs(best["lag_bins"]) == POLICY["lag_radius_bins"]:
            reasons.append("search_boundary")
        if best["normalized_mse"] > POLICY["normalized_mse_maximum"]:
            reasons.append("large_normalized_residual")
        for label, f, mask, indices in (
            ("source", sf, sm, anchors), ("target", tf, tm, anchors + best["lag_bins"])
        ):
            local = v1.stats({"features": f[indices], "mask": mask[indices]})
            if local["raw_rms"] < POLICY["minimum_rms"]:
                reasons.append(label + "_static_or_no_motion")
            if local["temporal_rms"] < POLICY["minimum_temporal_rms"]:
                reasons.append(label + "_temporally_uninformative")
    bins = v1.bin_table()
    return {
        "start_transition": start, "length": length,
        "source_frame_coverage": [bins[start]["frames"][0], bins[start + length]["frames"][1]],
        "source_transition_centers": tc[anchors].tolist(),
        "status": "unknown" if reasons else "candidate", "reasons": reasons,
        "best": best, "relative_distinct_gap": gap, "distinct_rival": rival,
        "curve": [[x["lag_bins"], x["normalized_mse"], x["common_fraction"]] for x in curve],
    }


def summarize(rows):
    candidates = [x for x in rows if x["status"] == "candidate"]
    return {
        "total": len(rows), "candidate": len(candidates), "unknown": len(rows) - len(candidates),
        "candidate_lag_bins": dict(sorted(Counter(x["best"]["lag_bins"] for x in candidates).items())),
        "all_best_lag_bins": dict(sorted(Counter(x["best"]["lag_bins"] for x in rows if x["best"]).items())),
        "unknown_reasons": dict(Counter(r for x in rows for r in x["reasons"])),
        "by_length": {str(length): dict(Counter(
            x["best"]["lag_bins"] for x in candidates if x["length"] == length))
            for length in POLICY["window_lengths"]},
        "by_tile": {f"{y},{x}": dict(Counter(
            row["best"]["lag_bins"] for row in candidates if row["tile"] == [y, x]))
            for y in range(4) for x in range(4)},
    }


def scan(source, target):
    tick = time.perf_counter()
    rows = []
    n = len(source["features"])
    for y in range(4):
        for x in range(4):
            sa, ta = tile_item(source, y, x), tile_item(target, y, x)
            for length in POLICY["window_lengths"]:
                for start in range(6, n - 6 - length + 1):
                    rows.append({"tile": [y, x], **window_readout(sa, ta, start, length)})
    assert len(rows) == POLICY["scan_count_per_clip"]
    return {"seconds": time.perf_counter() - tick, "summary": summarize(rows), "rows": rows}


def synthetic():
    g = torch.Generator().manual_seed(14502)
    texture = torch.randn(24, 32, 48, generator=g)
    base = texture.unsqueeze(0).repeat(31, 1, 1, 1)
    bias = torch.randn(5, 24, 32, 48, generator=g)
    biased_static = base + bias[torch.arange(31) % 5]
    walk = torch.randint(-1, 2, (31, 2), generator=g).cumsum(0)
    moving = torch.stack([torch.roll(texture, (int(y) * 2, int(x) * 2), (1, 2)) for y, x in walk])
    source_periodic = moving + bias[torch.arange(31) % 5]
    target_periodic = moving.roll(3, 0) + bias[torch.arange(31) % 5]
    local = base.clone()
    # A single short motion in spatial tile (1,1); outside it remains static.
    shifts = [0] * 31
    shifts[10:15] = [1, 2, 2, 1, 0]
    patch = texture[:, 8:16, 12:24]
    for t, shift in enumerate(shifts):
        local[t, :, 8:16, 12:24] = torch.roll(patch, shift * 2, 2)
    cases = [
        ("static_with_5bin_bias", biased_static, biased_static, None),
        ("delay3_plus_5bin_bias", source_periodic, target_periodic, 3),
        ("short_local_delay3", local, local.roll(3, 0), 3),
    ]
    rows = []
    for name, a, b, expected in cases:
        sa, ta = v1.descriptions(a), v1.descriptions(b)
        phase = v1.readout(phase_difference(a), phase_difference(b))
        local_scan = scan(sa["local_match"], ta["local_match"])
        selected = [r for r in local_scan["rows"] if r["status"] == "candidate"]
        correct = [r for r in selected if expected is not None and r["best"]["lag_bins"] == expected]
        wrong = [r for r in selected if expected is None or r["best"]["lag_bins"] != expected]
        phase_ok = (phase["status"] == "unknown" if expected is None else
                    phase["status"] == "candidate" and phase["best"]["lag_bins"] == expected)
        rows.append({
            "case": name, "expected_lag_bins": expected,
            "phase_difference": phase, "phase_expected_passed": phase_ok,
            "matching_global": v1.readout(sa["local_match"], ta["local_match"]),
            "local_scan": local_scan, "correct_candidate_count": len(correct),
            "wrong_candidate_count": len(wrong),
            "local_detection_passed": (not selected if expected is None else bool(correct)),
        })
    return {"scope": "deterministic tensor controls, not a trained model or video-motion truth",
            "seed": 14502, "rows": rows}


def compact_readout(row):
    return {k: v for k, v in row.items()
            if k not in ("source_stats", "target_stats", "curve", "anchors_transition_indices")}


def run(root, output):
    tick = time.perf_counter()
    output.mkdir(exist_ok=False)
    v1.write(output / "POLICY.json", POLICY)
    controls = synthetic()
    v1.write(output / "SYNTHETIC.json", controls)
    manifest = json.loads((root / "configs/CONDITION_CACHE.json").read_text())
    reference = next(x for x in manifest["tensors"] if x["role"] == "reference_vae_latent")
    ref, ref_sha = v1.load_tensor(reference["file"], reference["sha256"])
    source, source_phase = v1.descriptions(ref), phase_difference(ref)
    v1.write(output / "SOURCE.json", {
        "reference": reference, "actual_sha256": ref_sha, "bins": v1.bin_table(),
        "retained_bins": [0, 30], "phase_counts": POLICY["phase_counts"],
        "patch_grid": [23, 41],
        "tiles": [{"tile": [y, x],
                   "patch_bounds_yx_half_open": [
                       [y * 23 // 4, ((y + 1) * 23 + 3) // 4],
                       [x * 41 // 4, ((x + 1) * 41 + 3) // 4]],
                   "note": "adaptive pooling cells overlap at noninteger boundaries"}
                  for y in range(4) for x in range(4)],
    })
    rows = []
    run_id = "r144_short_0358_seed2026101701_visible_only"
    for step in POLICY["real_steps"]:
        start = time.perf_counter()
        path = root / "audit/counterfactual" / (run_id + "_snapshots") / f"step{step:03d}_native.pt"
        z, sha = v1.load_tensor(path)
        if sha != json.loads((output.parent / "results_v1" / f"step{step:03d}.json").read_text())["file_sha256"]:
            raise ValueError("endpoint differs from v1")
        desc, phase_desc = v1.descriptions(z), phase_difference(z)
        local = scan(source["local_match"], desc["local_match"])
        original = {k: v1.readout(source[k], desc[k]) for k in source}
        phase = v1.readout(source_phase, phase_desc)
        row = {
            "step": step, "file": str(path), "file_sha256": sha,
            "original_global": original, "phase_difference_global": phase,
            "phase_difference_seconds": phase_desc["seconds"],
            "matching_seconds": desc["local_match"]["seconds"],
            "local_matching": local, "total_seconds": time.perf_counter() - start,
        }
        v1.write(output / f"step{step:03d}.json", row)
        rows.append({
            "step": step, "total_seconds": row["total_seconds"],
            "phase_difference_seconds": row["phase_difference_seconds"],
            "matching_seconds": row["matching_seconds"], "scan_seconds": local["seconds"],
            "phase_difference_global": compact_readout(phase),
            "original_global": {k: compact_readout(v) for k, v in original.items()},
            "local_matching": local["summary"],
        })
        print(json.dumps({"step": step, "seconds": row["total_seconds"],
                          "phase": compact_readout(phase), "scan": local["summary"]}), flush=True)
    # Copy the already-frozen independent labels only after every latent result.
    label_path = output.parent / "results_v1/RGB_LABELS_UNTUNED.json"
    v1.write(output / "RGB_LABELS_UNTUNED.json", json.loads(label_path.read_text()))
    summary = {
        "code_sha256": v1.digest(__file__), "base_code_sha256": v1.digest(v1.__file__),
        "reference_sha256": ref_sha, "rgb_label_source_sha256": v1.digest(label_path),
        "rows": rows, "wall_seconds": time.perf_counter() - tick,
        "threads": torch.get_num_threads(), "CUDA_initialized": torch.cuda.is_initialized(),
        "GPU_model_VAE_forwards": 0,
        "synthetic": [{k: v for k, v in r.items() if k not in ("local_scan", "phase_difference", "matching_global")}
                      for r in controls["rows"]],
    }
    v1.write(output / "SUMMARY.json", summary)
    print(json.dumps({"finished": True, "wall_seconds": summary["wall_seconds"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--synthetic-only", action="store_true")
    args = parser.parse_args()
    if args.synthetic_only:
        v1.write(args.output, synthetic())
    else:
        if args.root is None:
            parser.error("--root required")
        run(args.root, args.output)
