"""One frozen CPU-only self-similarity observer. Never changes inference state."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path

os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import torch
import torch.nn.functional as TF

torch.set_num_threads(1)
OFFSETS = (-12, -8, -4, 4, 8, 12)
WINDOW = (50, 65)
LAGS = tuple(range(-24, 25))
EXPECTED_SHAPE = (1, 24, 42, 46, 82)
EXPECTED_REFERENCE_SHA = "75140c3ce5f144cdce940b6cd84a56dc40c9a94f15fdc917e6ad712ba9e94734"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def centers():
    widths = torch.tensor(([1, 4, 4, 4, 4] * 9)[:42], dtype=torch.float64)
    starts = torch.cumsum(widths, 0) - widths
    return starts + (widths - 1) / 2


def interpolate(features):
    """Feature-bin centers -> physical frames, no extrapolation."""
    if features.shape != (42, 384) or not torch.isfinite(features).all():
        raise ValueError("expected finite [42,384] pooled latent features")
    c = centers()
    t = torch.arange(141, dtype=torch.float64)
    hi = torch.searchsorted(c, t).clamp(1, len(c) - 1)
    lo = hi - 1
    a = (t - c[lo]) / (c[hi] - c[lo])
    result = features[lo] * (1 - a[:, None]) + features[hi] * a[:, None]
    valid = (t >= c[0]) & (t <= c[-1])
    result[~valid] = float("nan")
    return result


def pool_latent(latent):
    if tuple(latent.shape) != EXPECTED_SHAPE or latent.dtype != torch.float32:
        raise ValueError("latent shape/dtype outside frozen full-resolution protocol")
    if latent.device.type != "cpu" or not torch.isfinite(latent).all():
        raise ValueError("latent must be finite and CPU resident")
    frames = latent[0].permute(1, 0, 2, 3)
    return TF.adaptive_avg_pool2d(frames, (4, 4)).reshape(42, 384).double()


def descriptor(features, subset=None):
    f = interpolate(features)
    offsets = OFFSETS if subset is None else tuple(OFFSETS[i] for i in subset)
    d = torch.full((141, len(offsets)), float("nan"), dtype=torch.float64)
    for t in range(141):
        neighbors = [t + u for u in offsets]
        if min(neighbors) < 0 or max(neighbors) >= 141:
            continue
        if not torch.isfinite(f[[t] + neighbors]).all():
            continue
        d[t] = ((f[neighbors] - f[t]) ** 2).mean(dim=1)
    norm = torch.linalg.vector_norm(d, dim=1)
    valid = torch.isfinite(d).all(dim=1) & (norm > 1e-12)
    d[valid] /= norm[valid, None]
    d[~valid] = float("nan")
    return d


def costs(source, target):
    s = torch.arange(WINDOW[0], WINDOW[1] + 1)
    result = []
    for lag in LAGS:
        a, b = source[s], target[s + lag]
        valid = torch.isfinite(a).all(dim=1) & torch.isfinite(b).all(dim=1)
        n = int(valid.sum())
        value = float(((a[valid] - b[valid]) ** 2).mean()) if n >= math.ceil(.8 * len(s)) else None
        result.append({"lag_frames": lag, "cost": value, "valid_anchors": n})
    return result


def best_curve(curve):
    valid = [r for r in curve if r["cost"] is not None]
    if not valid:
        return None
    # Stable fixed lag order. Ties are rejected by the distinct-peak check.
    return min(valid, key=lambda r: r["cost"])


def infer(source_features, target_features):
    reasons = []
    s, y = descriptor(source_features), descriptor(target_features)
    curve = costs(s, y)
    best = best_curve(curve)
    for label, f, d in (("source", source_features, s), ("target", target_features, y)):
        variance = float(f.var(dim=0, unbiased=False).mean())
        if variance <= 1e-12:
            reasons.append(label + "_static_features")
        anchor = d[WINDOW[0]:WINDOW[1] + 1]
        good = torch.isfinite(anchor).all(dim=1)
        diversity = float(anchor[good].std(dim=0, unbiased=False).mean()) if good.any() else 0.
        if diversity <= .01:
            reasons.append(label + "_uninformative_self_similarity")
    gap = None
    if best is None:
        reasons.append("insufficient_coverage")
    else:
        if abs(best["lag_frames"]) == 24:
            reasons.append("search_boundary")
        if best["cost"] > .10:
            reasons.append("shape_residual")
        rivals = [r for r in curve if r["cost"] is not None and abs(r["lag_frames"] - best["lag_frames"]) >= 4]
        rival = min(rivals, key=lambda r: r["cost"])
        gap = (rival["cost"] - best["cost"]) / max(rival["cost"], 1e-8)
        if gap < .10:
            reasons.append("ambiguous_distinct_peak")
    subsets = {}
    for name, subset in (("inner", (2, 3)), ("outer", (0, 1, 4, 5))):
        b = best_curve(costs(descriptor(source_features, subset), descriptor(target_features, subset)))
        subsets[name] = None if b is None else b["lag_frames"]
    if best is None or any(v is None for v in subsets.values()):
        reasons.append("missing_neighborhood_estimate")
    elif abs(subsets["inner"] - subsets["outer"]) > 2 or any(abs(v - best["lag_frames"]) > 2 for v in subsets.values()):
        reasons.append("neighborhood_disagreement")
    return {"status": "unknown" if reasons else "phase_available", "lag_frames": None if reasons else best["lag_frames"],
            "best_candidate_not_accepted_as_phase": best, "relative_distinct_peak_gap": gap,
            "neighborhood_best_lags": subsets, "reject_reasons": reasons, "cost_curve": curve}


def synthetic_motion(t, kind="nonperiodic"):
    if kind == "static":
        small = torch.ones((len(t), 8), dtype=torch.float64)
    elif kind == "linear":
        small = t[:, None] * torch.arange(1, 9, dtype=torch.float64)[None, :] / 100
    elif kind == "periodic":
        w = 2 * math.pi * t / 12
        small = torch.stack([torch.sin(w * (1 + i // 2) + i * .37) for i in range(8)], dim=1)
    else:
        # Fixed, irregular nonperiodic motion motifs. No data-derived coefficients.
        locations = (21., 37., 51., 59., 73., 89., 108., 124.)
        widths = (8., 5., 7., 3., 6., 9., 4., 7.)
        small = torch.stack([torch.exp(-.5 * ((t - c) / w) ** 2)
                             + .13 * torch.tanh((t - c - 4) / (w + 2))
                             for c, w in zip(locations, widths)], dim=1)
    # Repetition is a scaled isometry; identical descriptor result to 8 dimensions.
    return small.repeat(1, 48) / math.sqrt(48)


def appearance_transform(features):
    permutation = torch.arange(383, -1, -1)
    signs = torch.where(torch.arange(384) % 2 == 0, 1., -1.).double()
    constant = torch.sin(torch.arange(384, dtype=torch.float64) * .19)
    return 1.8 * features[:, permutation] * signs + constant


def calibrate():
    c = centers()
    source = synthetic_motion(c)
    results = []
    for appearance in (False, True):
        for lag in (0, 8, -8, 16, -16):
            target = synthetic_motion(c - lag)
            if appearance:
                target = appearance_transform(target)
            result = infer(source, target)
            passed = result["status"] == "phase_available" and abs(result["lag_frames"] - lag) <= 2
            results.append({"case": f"nonperiodic_delay_{lag}_appearance_{appearance}", "expected_lag_frames": lag,
                            "required": "phase_available_within_2_frames", "pass": passed, "readout": result})
    for kind in ("static", "periodic", "linear"):
        f = synthetic_motion(c, kind)
        result = infer(f, appearance_transform(f))
        results.append({"case": kind, "required": "unknown", "pass": result["status"] == "unknown", "readout": result})
    return {"schema": "latent-phase-synthetic-calibration-v1", "all_passed": all(r["pass"] for r in results),
            "cases": results, "true_time_spans": ([1, 4, 4, 4, 4] * 9)[:42], "bin_centers_physical_frames": c.tolist(),
            "real_x0_values_read": False, "actual_gpu_or_model_forward": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibrate", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    # A readout/calibration rerun must never silently overwrite frozen evidence.
    if args.output.exists():
        raise FileExistsError(args.output)
    result = calibrate()
    result.update(script_sha256=sha(__file__), protocol_sha256=sha(args.protocol),
                  torch_version=torch.__version__, device="cpu", torch_threads=torch.get_num_threads())
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"all_passed": result["all_passed"], "total_cases": len(result["cases"]),
                      "failed_cases": [r["case"] for r in result["cases"] if not r["pass"]]}))


if __name__ == "__main__":
    main()
