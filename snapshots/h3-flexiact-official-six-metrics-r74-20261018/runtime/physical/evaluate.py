"""Supplementary pose timing at the original FlexiAct 8 fps timestamps."""
import copy
import hashlib
import json
from pathlib import Path
import numpy as np
import timing_metrics as metrics

ROOT = Path(__file__).resolve().parent
PROTOCOL = json.loads((ROOT / "PROTOCOL.json").read_text())
INDICES = list(range(0, 147, 3))
FEATURES = PROTOCOL["features"]
CONF = {"arm_direction": "arm_conf", "left_arm_direction": "left_arm_conf",
        "right_arm_direction": "right_arm_conf"}


def original_time_view(raw, threshold):
    records = raw["frames"]
    if len(records) != 158 or [row["frame"] for row in records] != list(range(158)):
        raise ValueError("Expected the complete cached158 pose sequence")
    if raw["video"]["fps"] != 24:
        raise ValueError("Expected the archived24fps source or generated video")
    times = np.asarray([row["time_s"] for row in records])
    if not np.isfinite(times).all() or not np.allclose(times, np.arange(158) / 24, atol=1e-6, rtol=0):
        raise ValueError("Pose physical timestamps differ")
    for row in records:
        if row["selected_person"] is not None:
            person = row["persons"][row["selected_person"]]
            coordinates, scores = np.asarray(person["coco17_xy"]), np.asarray(person["coco17_score"])
            if coordinates.shape != (17, 2) or scores.shape != (17,) or not np.isfinite(coordinates).all() or not np.isfinite(scores).all():
                raise ValueError("Selected pose has malformed or nonfinite coordinates/confidence")
    view = copy.deepcopy(raw)
    view["frames"] = [copy.deepcopy(records[j]) for j in INDICES]
    view["video"]["fps"] = 8
    xy = np.full((49, 17, 2), np.nan)
    confidence = np.zeros((49, 17))
    for i, row in enumerate(view["frames"]):
        row["frame"], row["time_s"] = i, i / 8
        selected = row["selected_person"]
        if selected is not None:
            person = row["persons"][selected]
            xy[i], confidence[i] = person["coco17_xy"], person["coco17_score"]
    # Torso normalization and all validity calculations use the original49 only.
    return metrics.pose_features(xy, confidence, np.arange(49) / 8, np.arange(49), view, threshold)


def diagnostic(source, edited, window, feature):
    curves = [metrics.pair_error(source, edited, window, lag, feature) for lag in range(-8, 9)]
    finite = [row for row in curves if np.isfinite(row["error"]) and row["valid_frame_count"] >= 8]
    same = curves[8]
    best_unqualified = min(finite, key=lambda row: row["error"]) if finite else None
    result = {"window": window, "feature": feature, "same_frame": same, "curve": curves,
              "lag_original_samples": None, "lag_ms": None, "status": "unknown", "reasons": []}
    if best_unqualified is None or same["coverage"] < .8 or best_unqualified["coverage"] < .8:
        return result | {"reasons": ["insufficient_visibility"]}
    candidates = [row for row in finite if row["coverage"] >= .8]
    best = min(candidates, key=lambda row: row["error"])
    remote = [row for row in candidates if abs(row["lag_frames"] - best["lag_frames"]) >= 2]
    second = min(remote, key=lambda row: row["error"]) if remote else None
    gain = (same["error"] - best["error"]) / max(same["error"], 1e-8)
    gap = (second["error"] - best["error"]) / max(best["error"], 1e-8) if second else None
    if abs(best["lag_frames"]) == 8:
        result["reasons"].append("search_boundary")
    if gap is None or gap < .05:
        result["reasons"].append("weak_or_ambiguous_motion")
    if best["lag_frames"] != 0 and gain < .05:
        result["reasons"].append("little_gain_over_same_time")
    if best["error"] > .5:
        result["reasons"].append("residual_pose_difference")
    result.update(best=best, distinct_basin_gap=gap, improvement_after_shift=gain)
    if not result["reasons"]:
        result.update(status="qualified_exploratory", lag_original_samples=best["lag_frames"],
                      lag_ms=125 * best["lag_frames"])
    return result


def common_error(source, edits, window, feature):
    indices = np.arange(window[0], window[1] + 1)
    original = source[feature][indices]
    valid = np.isfinite(original).all(-1)
    weights = source[CONF[feature]][indices].clip(0, 1)
    for edit in edits.values():
        valid &= np.isfinite(edit[feature][indices]).all(-1)
        weights = np.minimum(weights, edit[CONF[feature]][indices].clip(0, 1))
    weights = np.where(valid, weights, 0)
    denominator = float(weights.sum())
    return {"coverage": float(valid.mean()), "valid_frame_count": int((weights.sum(-1) > 0).sum()),
            "status": "qualified_exploratory" if valid.mean() >= .8 and (weights.sum(-1) > 0).sum() >= 8 else "unknown",
            "same_time_error": {name: float((np.nan_to_num(np.linalg.norm(original - value[feature][indices], axis=-1)) * weights).sum() / denominator)
                                if denominator else None for name, value in edits.items()}}


def evaluate(reference, native, automatic):
    output = {"protocol_sha256": hashlib.sha256((ROOT / "PROTOCOL.json").read_bytes()).hexdigest(),
              "confidence_results": {}, "paired_lag_summary": [], "physical_time_step_ms": 125}
    for confidence in (.3, .5):
        try:
            source = original_time_view(reference, confidence)
            edits = {"native": original_time_view(native, confidence), "automatic": original_time_view(automatic, confidence)}
        except ValueError as exc:
            if str(exc) != "Insufficient reliable torso anchors for scale normalization":
                raise
            output["confidence_results"][str(confidence)] = {"status": "unknown_visibility", "rows": []}
            continue
        rows = []
        for window in PROTOCOL["windows_inclusive"]:
            for feature in FEATURES:
                rows.append({"window": window, "feature": feature,
                             "diagnostics": {name: diagnostic(source, edit, window, feature) for name, edit in edits.items()},
                             "common_support": common_error(source, edits, window, feature)})
        output["confidence_results"][str(confidence)] = {"status": "measured", "rows": rows}
    for window in PROTOCOL["windows_inclusive"]:
        for feature in FEATURES:
            entry = {"window": window, "feature": feature, "methods": {}}
            for name in ("native", "automatic"):
                values = []
                for confidence in (.3, .5):
                    rows = output["confidence_results"][str(confidence)]["rows"]
                    row = next((x for x in rows if x["window"] == window and x["feature"] == feature), None)
                    values.append(row["diagnostics"][name]["lag_ms"] if row else None)
                qualified = all(x is not None for x in values) and abs(values[0] - values[1]) <= 125
                entry["methods"][name] = {"status": "qualified_exploratory" if qualified else "unknown",
                                           "lag_ms_at_confidence_03_05": values}
            output["paired_lag_summary"].append(entry)
    return metrics.clean(output)
