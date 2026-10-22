"""Fixed-input wrist/nose feasibility diagnostic; no online policy dependency."""
import hashlib
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
N = 144
THRESHOLDS = (0.3, 0.5)
LAGS = range(-24, 25)
NULLS = range(-2, 3)
EPS = 1e-12  # Numerical equality only; not a pose quality/gain threshold.
POSE_DIR = Path(
    "/Users/researcher/DevProjects/h3-ive-handkerchief-full-context-metrics-r126-20261020"
    "/audit/visible_arm_feasibility_20261020/actual/poses"
)
SOURCE = POSE_DIR / "long_0059_video.pose.json"
NATIVE = POSE_DIR / "r126_long_0059_seed2026101701_native_00001_.pose.json"
DESIGN = Path("/Users/researcher/DevProjects/h3-visible-hand-observer-design-20261020")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value, compact=False):
    path = ROOT / name
    path.write_text(json.dumps(value, ensure_ascii=False,
                              indent=None if compact else 2, allow_nan=False) + "\n")
    return {"file": str(path), "sha256": sha(path)}


def read_pose(path):
    raw = json.loads(path.read_text())
    records = raw["frames"][:N]
    assert len(records) == N
    assert [r["frame"] for r in records] == list(range(N))
    assert all(abs(r["time_s"] - i / 24) < 1e-6 for i, r in enumerate(records))
    xy = np.full((N, 17, 2), np.nan)
    conf = np.zeros((N, 17))
    ambiguous = np.zeros(N, bool)
    for i, record in enumerate(records):
        selected = record["selected_person"]
        ambiguous[i] = bool(record.get("selection_ambiguous"))
        if selected is not None:
            person = record["persons"][selected]
            xy[i] = person["coco17_xy"]
            conf[i] = person["coco17_score"]
    inside = (np.isfinite(xy).all(-1) & (xy[..., 0] >= 16)
              & (xy[..., 0] < 1296) & (xy[..., 1] >= 8) & (xy[..., 1] < 728))
    return raw, xy, conf, inside, ambiguous


def trajectory(data, threshold, scale):
    _, xy, conf, inside, ambiguous = data
    mask = (inside[:, 0] & inside[:, 9] & (conf[:, 0] >= threshold)
            & (conf[:, 9] >= threshold) & ~ambiguous)
    q = (xy[:, 9] - xy[:, 0]) / scale
    q[~mask] = np.nan
    weights = np.minimum(conf[:, 0], conf[:, 9])
    weights[~mask] = 0
    return {"q": q, "valid": mask, "weights": weights}


def shift(a, lag, offset=None):
    """Positive lag delays target; out-of-domain values remain missing."""
    result = {"q": np.full_like(a["q"], np.nan),
              "valid": np.zeros(N, bool), "weights": np.zeros(N)}
    for target in range(N):
        source = target - lag
        if 0 <= source < N:
            result["q"][target] = a["q"][source]
            result["valid"][target] = a["valid"][source]
            result["weights"][target] = a["weights"][source]
    if offset is not None:
        result["q"] += np.asarray(offset)
    return result


def synthetic(q):
    return {"q": q, "valid": np.ones(N, bool), "weights": np.ones(N)}


def moments(a, b, w, indices):
    """Same common frames and same fixed weights for both compared trajectories."""
    if len(w) == 0:
        return None
    sw = float(w.sum())
    ma = (a * w[:, None]).sum(0) / sw
    mb = (b * w[:, None]).sum(0) / sw
    ca, cb = a - ma, b - mb
    rms = lambda x, weights: float(np.sqrt(
        (np.square(x).sum(-1) * weights).sum() / weights.sum()))
    consecutive = np.diff(indices) == 1
    dw = np.minimum(w[:-1], w[1:])[consecutive]
    da = np.diff(a, axis=0)[consecutive]
    db = np.diff(b, axis=0)[consecutive]
    dist_a, dist_b = np.linalg.norm(a, axis=-1), np.linalg.norm(b, axis=-1)
    dist_a -= (dist_a * w).sum() / sw
    dist_b -= (dist_b * w).sum() / sw
    return {
        "raw_RMS": rms(a - b, w),
        "centered_RMS": rms(ca - cb, w),
        "source_centered_RMS": rms(ca, w),
        "target_centered_RMS": rms(cb, w),
        "delta_RMS": rms(da - db, dw) if len(dw) else None,
        "source_delta_RMS": rms(da, dw) if len(dw) else None,
        "distance_centered_RMS": float(np.sqrt(
            (np.square(dist_a - dist_b) * w).sum() / sw)),
        "weight_sum": sw,
        "difference_pair_count": int(consecutive.sum()),
        "difference_weight_sum": float(dw.sum()),
    }


def support(a, b, start, length, lags):
    i = np.arange(start, start + length)
    keep = a["valid"][i].copy()
    for lag in lags:
        j = i + lag
        in_domain = (j >= 0) & (j < N)
        keep &= in_domain & b["valid"][np.clip(j, 0, N - 1)]
    i = i[keep]
    w = a["weights"][i].copy()
    for lag in lags:
        w = np.minimum(w, b["weights"][i + lag])
    return i, w


def cost(a, b, start, length, lag):
    i, w = support(a, b, start, length, [lag])
    n = len(i)
    out = {"lag": lag, "valid_frames": n, "coverage": n / length,
           "support_qualified": n >= 8 and n / length >= 0.8}
    if n:
        out.update(moments(a["q"][i], b["q"][i + lag], w, i))
    return out


def compare(a, b, start, length, proposal, null):
    i, w = support(a, b, start, length, [proposal, null])
    n = len(i)
    out = {"proposal_lag": proposal, "null_lag": null,
           "valid_frames": n, "coverage": n / length,
           "support_qualified": n >= 8 and n / length >= 0.8,
           "source_indices": i.tolist(), "weight_sum": float(w.sum())}
    if not n:
        return out
    p = moments(a["q"][i], b["q"][i + proposal], w, i)
    z = moments(a["q"][i], b["q"][i + null], w, i)
    out.update({"proposal": p, "null": z,
                "difference_coverage": p["difference_pair_count"] / (length - 1)})
    denominator = z["centered_RMS"]
    out["centered_absolute_improvement"] = denominator - p["centered_RMS"]
    out["centered_relative_improvement"] = (
        1 - p["centered_RMS"] / denominator if denominator > EPS else None)
    out["delta_absolute_improvement"] = (
        z["delta_RMS"] - p["delta_RMS"] if z["delta_RMS"] is not None else None)
    return out


def scan(a, b, threshold, keep_curves):
    rows = []
    for length in (16, 32):
        starts = sorted(set(range(0, N - length + 1, 4)) | {N - length})
        for start in starts:
            curve = [cost(a, b, start, length, lag) for lag in LAGS]
            eligible = [x for x in curve if x["support_qualified"]]
            row = {"window": [start, start + length - 1], "length": length,
                   "confidence": threshold, "eligible_lags": len(eligible),
                   "best_lag": None, "status": "UNKNOWN_INSUFFICIENT_SUPPORT"}
            if eligible:
                minimum = min(x["centered_RMS"] for x in eligible)
                tied = [x for x in eligible if x["centered_RMS"] <= minimum + EPS]
                row["tied_best_lags"] = [x["lag"] for x in tied]
                row["minimum_centered_RMS"] = minimum
                if all(x["source_centered_RMS"] <= EPS for x in eligible):
                    row["status"] = "UNKNOWN_STATIC_SOURCE"
                elif len(tied) != 1:
                    row["status"] = "UNKNOWN_NONIDENTIFIABLE_LAG"
                else:
                    best = tied[0]
                    row.update({"status": "MEASURED_UNCALIBRATED",
                                "best_lag": best["lag"], "best": best,
                                "null_comparisons": [
                                    compare(a, b, start, length, best["lag"], z)
                                    for z in NULLS],
                                "source_self_tolerance_curve": [
                                    cost(a, a, start, length, z) for z in NULLS]})
                    qualified = [x for x in row["null_comparisons"]
                                 if x["support_qualified"]]
                    gains = [x["centered_relative_improvement"] for x in qualified
                             if x["centered_relative_improvement"] is not None]
                    row["all_null_support_qualified"] = len(qualified) == 5
                    row["minimum_centered_relative_improvement"] = (
                        min(gains) if len(gains) == 5 else None)
                    delta = [x["delta_absolute_improvement"] for x in qualified
                             if x.get("delta_absolute_improvement") is not None]
                    row["delta_same_lag_improves_every_null"] = (
                        len(delta) == 5 and min(delta) > EPS)
                    row["delta_support_qualified_every_null"] = (
                        len(qualified) == 5
                        and all(x["difference_coverage"] >= .8
                                and x["proposal"]["difference_pair_count"] >= 8
                                for x in qualified))
            if keep_curves:
                row["lag_curve"] = curve
            rows.append(row)
    return rows


def control_summary(rows, expected, require_unknown=False):
    measured = [x for x in rows if x["best_lag"] is not None]
    wrong = [x for x in measured if expected is not None and x["best_lag"] != expected]
    if require_unknown:
        wrong = measured
    return {"window_count": len(rows), "measured_count": len(measured),
            "expected_lag": expected,
            "measured_lag_counts": {
                str(k): sum(x["best_lag"] == k for x in measured)
                for k in sorted(set(x["best_lag"] for x in measured))},
            "UNKNOWN_count": len(rows) - len(measured),
            "failure_count": len(wrong),
            "failures": [{"window": x["window"], "confidence": x["confidence"],
                          "best_lag": x["best_lag"]} for x in wrong],
            "passed": len(wrong) == 0 and (require_unknown or len(measured) > 0)}


def main():
    started = time.perf_counter()
    assert not (ROOT / "RESULT.json").exists(), "preserve first frozen diagnostic"
    design_freeze = json.loads((DESIGN / "FREEZE.json").read_text())
    for name, item in design_freeze["files"].items():
        assert sha(DESIGN / name) == item["sha256"], name
    protocol = {
        "schema": "r144-hand-observer-fixed-input-offline-protocol-v1",
        "design_freeze_sha256": sha(DESIGN / "FREEZE.json"),
        "inputs": {"source_pose": {"file": str(SOURCE), "sha256": sha(SOURCE)},
                   "native_pose": {"file": str(NATIVE), "sha256": sha(NATIVE)}},
        "valid_frames": N, "fps": 24, "excluded_container_frames": [144, 157],
        "content_crop_xywh": [16, 8, 1280, 720],
        "feature": "(left wrist - nose) / source fixed median shoulder distance",
        "scale": "Median of all144 source shoulder distances with both inside content, confidence>=.5, unambiguous selection",
        "confidence": THRESHOLDS, "window_lengths": [16, 32], "stride": 4,
        "include_last_full_window": True, "lags": [-24, 24], "null_lags": [-2, 2],
        "support": {"coverage": .8, "minimum_frames": 8,
                    "missing": "Keep original physical indices; no fill/interpolation/wrap"},
        "weights": "minimum source/target nose/wrist confidence on each comparison's common support",
        "primary": "Weighted demeaned2D RMS; independent lag costs recorded; unique numerical minimum reported as uncalibrated estimate",
        "paired_gain": "Each proposal/null uses a shared frame intersection, same weights and weighted means. Different null comparisons may have different supports.",
        "delta_check": "Adjacent physical pairs only; same proposed lag, no derivative-lag optimization",
        "numerical_equality_atol": EPS,
        "scientific_gain_or_activity_thresholds_added": False,
        "controls": ["self", "delay+4", "delay-4", "delay+8", "delay-8",
                     "constant2Doffset", "delay+8_plus_offset", "delay-8_plus_offset",
                     "static", "constant_velocity", "missing64..79",
                     "equal_distance_opposite_direction"],
        "manual_event_intervals_used_to_select_windows_or_lags": False,
        "policy_changed": False, "GPU_started": False, "new_pose_extraction": False,
    }
    protocol_binding = save("PROTOCOL.json", protocol)
    source_data, native_data = read_pose(SOURCE), read_pose(NATIVE)
    _, xy, conf, inside, ambiguous = source_data
    reliable = (inside[:, 5] & inside[:, 6] & (conf[:, 5] >= .5)
                & (conf[:, 6] >= .5) & ~ambiguous)
    distances = np.linalg.norm(xy[:, 5] - xy[:, 6], axis=-1)[reliable]
    scale = float(np.median(distances))
    assert len(distances) > 0 and np.isfinite(scale) and scale > 0
    actual, controls, tracks = [], {}, {}
    for threshold in THRESHOLDS:
        a = trajectory(source_data, threshold, scale)
        b = trajectory(native_data, threshold, scale)
        actual.extend(scan(a, b, threshold, True))
        tracks[str(threshold)] = {
            role: {"visible_frames": np.flatnonzero(t["valid"]).tolist(),
                   "q": [p.tolist() if valid else None
                         for p, valid in zip(t["q"], t["valid"])],
                   "distance": [float(np.linalg.norm(p)) if valid else None
                                for p, valid in zip(t["q"], t["valid"])]}
            for role, t in [("source", a), ("native", b)]
        }
        tests = [("self", a, a, 0, False)]
        for lag in (-8, -4, 4, 8):
            tests.append((f"delay{lag:+d}", a, shift(a, lag), lag, False))
        tests.append(("constant2Doffset", a, shift(a, 0, [.13, -.08]), 0, False))
        for lag in (-8, 8):
            tests.append((f"delay{lag:+d}_plus_offset", a,
                          shift(a, lag, [.13, -.08]), lag, False))
        still = synthetic(np.tile([.2, -.3], (N, 1)))
        tests.append(("static", still, still, None, True))
        line = synthetic(np.column_stack((np.arange(N) * .003,
                                          np.arange(N) * -.002)))
        tests.append(("constant_velocity", line, line, None, True))
        masked = shift(a, 0)
        masked["valid"][64:80] = False
        masked["q"][64:80] = np.nan
        masked["weights"][64:80] = 0
        tests.append(("missing64..79", a, masked, 0, False))
        for name, source, target, expected, unknown in tests:
            rows = scan(source, target, threshold, False)
            controls.setdefault(name, []).extend(rows)
        opposite = shift(a, 0)
        opposite["q"] *= -1
        checks = []
        for length in (16, 32):
            starts = sorted(set(range(0, N - length + 1, 4)) | {N - length})
            for start in starts:
                z = cost(a, opposite, start, length, 0)
                if z["support_qualified"]:
                    checks.append({"window": [start, start+length-1],
                                   "confidence": threshold,
                                   "centered_RMS": z["centered_RMS"],
                                   "distance_centered_RMS": z["distance_centered_RMS"]})
        controls.setdefault("equal_distance_opposite_direction", []).extend(checks)
    expected = {"self": 0, "constant2Doffset": 0, "missing64..79": 0}
    for lag in (-8, -4, 4, 8):
        expected[f"delay{lag:+d}"] = lag
    expected.update({"delay-8_plus_offset": -8, "delay+8_plus_offset": 8})
    summaries = {}
    for name, rows in controls.items():
        if name == "equal_distance_opposite_direction":
            summaries[name] = {
                "support_qualified_windows": len(rows),
                "distance_cost_all_zero": all(x["distance_centered_RMS"] <= EPS for x in rows),
                "twoD_cost_all_positive": all(x["centered_RMS"] > EPS for x in rows),
                "passed": all(x["distance_centered_RMS"] <= EPS
                              and x["centered_RMS"] > EPS for x in rows),
                "meaning": "Distance alone is ambiguous; no distance OR-pass rule is implemented"}
        else:
            summaries[name] = control_summary(rows, expected.get(name),
                                               name in ("static", "constant_velocity"))
    curve_binding = save("ACTUAL_ALL_WINDOWS.json", actual, compact=True)
    save("CONTROL_WINDOWS.json", controls, compact=True)
    track_binding = save("TRAJECTORIES.json", tracks, compact=True)
    # Manual labels enter only this reporting join, after every scan was completed.
    events = {"raise": [15, 17], "touch": [28, 31], "withdrawal": [95, 98]}
    event_rows = {}
    for name, interval in events.items():
        chosen = [r for r in actual
                  if r["window"][0] <= interval[1] and r["window"][1] >= interval[0]]
        event_rows[name] = [{
            k: x.get(k) for k in [
                "window", "confidence", "status", "best_lag", "eligible_lags",
                "minimum_centered_relative_improvement", "all_null_support_qualified",
                "delta_same_lag_improves_every_null", "delta_support_qualified_every_null",
                "best"]}
            for x in chosen]
    result = {
        "schema": "r144-hand-observer-offline-result-v1",
        "protocol": protocol_binding, "code_sha256": sha(__file__),
        "source_fixed_scale_px": scale, "scale_supported_frames": int(reliable.sum()),
        "scale_p10_p90": np.quantile(distances, [.1, .9]).tolist(),
        "all_windows": curve_binding, "trajectories": track_binding,
        "coverage": {t: {role: len(row["visible_frames"]) for role, row in v.items()}
                     for t, v in tracks.items()},
        "actual_window_count": len(actual),
        "actual_status_counts": {s: sum(x["status"] == s for x in actual)
                                 for s in sorted(set(x["status"] for x in actual))},
        "controls": summaries, "all_controls_passed": all(x["passed"] for x in summaries.values()),
        "posthoc_manual_event_reporting_only": event_rows,
        "actual_closed_loop_trigger_or_benefit_tested": False,
        "reliability_calibration": "No activity/residual/gain threshold calibrated; estimates remain descriptive",
        "fixed_pose": "Not available in matched cache; no extraction performed",
        "CPU_wall_seconds": time.perf_counter() - started,
        "GPU_started": False, "original_policy_changed": False,
    }
    binding = save("RESULT.json", result)
    print(json.dumps({"result": binding, "CPU_seconds": result["CPU_wall_seconds"],
                      "controls_passed": result["all_controls_passed"],
                      "actual_status_counts": result["actual_status_counts"]}))


if __name__ == "__main__":
    main()
