"""Frozen, source-only JSON diagnostic. No model or video decoding."""
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL_SHA = "98eb0c2864571e30d649a113840fa20ab18bb350495a3448c8b646dacbece833"
LAGS = list(range(-24, 25))
TOL = 1e-12


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def save(path, value):
    require(not path.exists(), f"Refuse overwrite: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def checked(record):
    p = Path(record["path"])
    require(p.stat().st_size == record["bytes"] and sha(p) == record["sha256"], f"Input changed: {p}")
    return p


def curve(source, target, anchors):
    """Same anchors, feature cells and min confidence weight at every lag."""
    anchors = np.asarray(anchors, dtype=np.int64)
    a = source["arm_direction"][anchors]
    common = np.isfinite(a).all(axis=-1)
    weights = np.clip(source["arm_conf"][anchors], 0, 1).copy()
    reasons = []
    candidates = []
    valid_by_lag = []
    for d in LAGS:
        indices = anchors + d
        in_bounds = (indices >= 0) & (indices < len(target["arm_direction"]))
        b = np.full_like(a, np.nan)
        conf = np.zeros_like(weights)
        b[in_bounds] = target["arm_direction"][indices[in_bounds]]
        conf[in_bounds] = target["arm_conf"][indices[in_bounds]]
        valid = in_bounds[:, None] & np.isfinite(b).all(axis=-1)
        common &= valid
        weights = np.minimum(weights, np.clip(conf, 0, 1))
        candidates.append(b)
        valid_by_lag.append(valid)
    weights = np.where(common, weights, 0)
    common &= weights > 0
    weights = np.where(common, weights, 0)
    for i, t in enumerate(anchors.tolist()):
        for k in range(4):
            if not common[i, k]:
                reasons.append({"anchor_frame": t, "arm_index": k,
                                "source_valid": bool(np.isfinite(a[i, k]).all()),
                                "invalid_candidate_lags": [d for d, v in zip(LAGS, valid_by_lag) if not v[i, k]],
                                "zero_common_weight": bool(weights[i, k] == 0)})
    weight_sum = float(weights.sum())
    support_sha = hashlib.sha256(common.tobytes() + weights.tobytes()).hexdigest()
    rows = []
    for d, b in zip(LAGS, candidates):
        distances = np.linalg.norm(a - b, axis=-1)
        score = float(np.sum(np.where(common, distances, 0) * weights) / weight_sum) if weight_sum else None
        per_anchor = []
        for i in range(len(anchors)):
            den = float(weights[i].sum())
            per_anchor.append(float(np.sum(np.where(common[i], distances[i], 0) * weights[i]) / den) if den else None)
        rows.append({"lag_frames": d, "error": score, "per_anchor_error": per_anchor,
                     "target_frames": (anchors + d).tolist(), "support_sha256": support_sha,
                     "weight_sum": weight_sum})
    coverage = float(common.sum() / max(1, len(anchors) * 4))
    valid_frames = int((weights.sum(axis=-1) > 0).sum())
    finite = [r for r in rows if r["error"] is not None]
    constant = bool(finite and max(r["error"] for r in finite) <= TOL)
    if not finite:
        status = "UNKNOWN_NO_COMMON_SUPPORT"
    elif constant:
        status = "UNKNOWN_CONSTANT"
    elif valid_frames < 8:
        status = "UNKNOWN_INSUFFICIENT_TEMPORAL_SUPPORT"
    elif coverage < 0.8:
        status = "UNKNOWN_COVERAGE"
    else:
        status = "DESCRIPTIVE_SUPPORT_PASSED_NOT_A_LAG_ESTIMATOR"
    competitors = sorted([r for r in finite if abs(r["lag_frames"]) > 2], key=lambda r: (r["error"], r["lag_frames"]))
    best_error = min(r["error"] for r in finite) if finite else None
    competitor_error = competitors[0]["error"] if competitors else None
    squared = 0.0
    energy_weight = 0.0
    adjacent_pairs = []
    for i in range(len(anchors) - 1):
        if anchors[i + 1] - anchors[i] != 1:
            continue
        w = np.minimum(weights[i], weights[i + 1])
        d2 = np.sum((a[i + 1] - a[i]) ** 2, axis=-1)
        squared += float(np.sum(np.where(w > 0, d2, 0) * w))
        energy_weight += float(w.sum())
        adjacent_pairs.append([int(anchors[i]), int(anchors[i + 1])])
    endpoint = None
    if len(anchors) == 2:
        w = np.minimum(weights[0], weights[1])
        d2 = np.sum((a[1] - a[0]) ** 2, axis=-1)
        endpoint = float(np.sum(np.where(w > 0, d2, 0) * w) / w.sum()) if w.sum() else None
    return {"status": status, "anchors": anchors.tolist(), "expected_feature_cells": int(len(anchors) * 4),
            "common_feature_cells": int(common.sum()), "coverage": coverage, "valid_anchor_count": valid_frames,
            "support_mask": common.tolist(), "fixed_weights": weights.tolist(), "support_sha256": support_sha,
            "removed_support": reasons, "curve": rows,
            "global_min_error": best_error,
            "global_min_lags": [r["lag_frames"] for r in finite if abs(r["error"] - best_error) <= TOL],
            "nonzero_competitors_unqualified": [{"lag_frames": r["lag_frames"], "error": r["error"]} for r in competitors],
            "closest_competitor_error": competitor_error,
            "closest_competitor_lags": [r["lag_frames"] for r in competitors if abs(r["error"] - competitor_error) <= TOL],
            "competitor_at_search_boundary": bool(competitors and abs(competitors[0]["lag_frames"]) == 24),
            "adjacent_anchor_pairs": adjacent_pairs,
            "adjacent_squared_motion_energy": squared / energy_weight if energy_weight else None,
            "sparse_endpoint_squared_change": endpoint,
            "reliable_lag": None,
            "interpretation": "Unqualified source-only geometry projection; zero self-match is tautological. No semantic feature or branch-causal claim."}


def synthetic_tests(metric):
    t = np.arange(141, dtype=float)
    x = np.zeros((141, 17, 2))
    x[:, 5], x[:, 6], x[:, 11], x[:, 12] = [-0.4, 0], [0.4, 0], [-0.3, 1], [0.3, 1]
    for k, (a, b) in enumerate(metric.ARMS):
        theta = 0.03 * t + 0.00007 * t * t + k * 0.31
        x[:, b] = x[:, a] + np.stack([np.cos(theta), np.sin(theta)], axis=-1)
    conf = np.ones((141, 17))
    source = metric.pose_features(x, conf, t / 24, t.astype(int), {"video": {"fps": 24}}, 0.3)
    cases = []
    for anchors in [list(range(50, 66)), [48, 60]]:
        same = curve(source, source, anchors)
        require(same["curve"][24]["error"] == 0, "nonzero self diagonal")
        require(same["global_min_lags"] == [0], "synthetic nonconstant self unique")
        require(len({r["support_sha256"] for r in same["curve"]}) == 1, "candidate support changed")
        for shift in [7, -5]:
            y = np.full_like(x, np.nan)
            c = np.zeros_like(conf)
            ix = np.arange(141) - shift
            ok = (ix >= 0) & (ix < 141)
            y[ok], c[ok] = x[ix[ok]], 1
            target = metric.pose_features(y, c, t / 24, t.astype(int), {"video": {"fps": 24}}, 0.3)
            result = curve(source, target, anchors)
            require(result["global_min_lags"] == [shift], "known shift sign/mapping")
            require(result["global_min_error"] == 0, "shift residual")
        cases.append({"anchors": anchors, "self_zero": True, "shift_plus7_minus5": True,
                      "support_fixed": True, "self_status": same["status"]})
    for d in LAGS:
        expected = metric.pair_error(source, source, [50, 65], d, "arm_direction")["error"]
        actual = curve(source, source, list(range(50, 66)))["curve"][d + 24]["error"]
        require(abs(expected - actual) <= TOL, "distance differs from frozen original")
    constant = {"arm_direction": np.tile(np.array([1.0, 0.0]), (141, 4, 1)), "arm_conf": np.ones((141, 4))}
    const = curve(constant, constant, list(range(50, 66)))
    require(const["status"] == "UNKNOWN_CONSTANT" and all(r["error"] == 0 for r in const["curve"]), "constant accepted")
    return {"passed": True, "cases": cases, "all49_original_distance_equivalence": True,
            "constant_unknown": True, "new_models": 0, "cuda_imported": False}


def input_audit(case):
    paths = {k: checked(case[k]) for k in ["pose", "conditioning", "source_video", "successful_history"]}
    pose = json.loads(paths["pose"].read_text())
    cond = json.loads(paths["conditioning"].read_text())
    history = json.loads(paths["successful_history"].read_text())
    require(pose["video"]["sha256"] == case["source_video"]["sha256"], "pose/source byte SHA mismatch")
    require([r["frame"] for r in pose["frames"]] == list(range(141)), "source frame axis")
    require(all(abs(r["time_s"] - i / 24) < 1e-8 for i, r in enumerate(pose["frames"])), "source physical time")
    require(pose["video"]["width"] == 1312 and pose["video"]["height"] == 736 and pose["video"]["fps"] == 24, "source geometry")
    require(history["status"]["completed"] is True and history["status"]["status_str"] == "success", "actual successful graph")
    graph = history["prompt"][2]
    loads = [v["inputs"]["file"] for v in graph.values() if v["class_type"] == "LoadVideo"]
    require(loads == [paths["source_video"].name], "source input graph filename")
    sampling = [x["sampling"] for x in cond["qwen_presentation"] if x["type"] == "video"]
    require(sampling == [case["sampling_ledger"]], "actual semantic ledger changed")
    s = sampling[0]
    require(s["sample_indices"] == list(range(0, 133, 12)), "actual sparse samples")
    require([f for p in s["temporal_blocks"] for f in p["source_frames"]] == s["sample_indices"], "actual pair grouping")
    require(all(abs(sec - frame / 24) < 1e-8 for sec, frame in zip(s["sample_timestamps_seconds"], s["sample_indices"])), "semantic times")
    selected = [b for b in s["temporal_blocks"] if min(b["source_frames"]) <= case["window_inclusive"][1] and max(b["source_frames"]) >= case["window_inclusive"][0]]
    require(sorted({i for b in selected for i in b["source_frames"]}) == case["sparse_frames"], "pair selection mismatch")
    require(cond["input_video"] == case["input_tensor_signature"], "input tensor binding")
    return {"passed": True, "pose_sha256": sha(paths["pose"]), "source_video_sha256": sha(paths["source_video"]),
            "conditioning_sha256": sha(paths["conditioning"]), "history_sha256": sha(paths["successful_history"]),
            "actual_input_tensor": cond["input_video"], "selected_pairs": selected,
            "caveat": "Existing extraction/source byte SHA and actual graph/ledger bound; RGB decode and Qwen embeddings not regenerated."}


def main():
    require(sha(HERE / "PROTOCOL.json") == PROTOCOL_SHA, "protocol changed")
    protocol = json.loads((HERE / "PROTOCOL.json").read_text())
    frozen = json.loads((HERE / "FREEZE.json").read_text())
    require(sha(__file__) == frozen["evaluate_sha256"], "implementation changed after freeze")
    require(sha(HERE / "PROTOCOL.json") == frozen["protocol_sha256"], "freeze/protocol mismatch")
    with Path(protocol["cpu_lock"]).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("CPU_LOCK_BUSY_R24_PRIORITY", flush=True)
            return 75
        started = time.monotonic()
        metric_path = checked(protocol["feature_implementation"])
        spec = importlib.util.spec_from_file_location("frozen_timing_metrics", metric_path)
        metric = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(metric)
        tests = synthetic_tests(metric)
        save(HERE / "SELF_TESTS.json", tests)
        rows = []
        for case in protocol["cases"]:
            audit = input_audit(case)
            for threshold in protocol["confidence_thresholds"]:
                pose = metric.load_pose(case["pose"]["path"], threshold)
                views = {"dense": list(range(case["window_inclusive"][0], case["window_inclusive"][1] + 1)),
                         "sparse_pair_projection": case["sparse_frames"]}
                result = {name: curve(pose, pose, anchors) for name, anchors in views.items()}
                for value in result.values():
                    require(value["curve"][24]["error"] in (0.0, None), "actual source diagonal not zero")
                rows.append({"case_id": case["case_id"], "window": case["window_inclusive"], "threshold": threshold,
                             "input_audit": audit, "views": result})
        elapsed = time.monotonic() - started
        output = {"schema": "h3_sparse_semantic_ambiguity_results_v1", "protocol_sha256": PROTOCOL_SHA,
                  "evaluate_sha256": sha(__file__), "self_tests_sha256": sha(HERE / "SELF_TESTS.json"),
                  "implementation_checks_passed": True, "rows": rows,
                  "elapsed_seconds": elapsed, "pid": os.getpid(), "threads": 1,
                  "numpy_version": np.__version__, "python": sys.version, "cpu_lock": protocol["cpu_lock"],
                  "gpu_calls": 0, "model_calls": 0, "pose_calls": 0,
                  "limitations": protocol["limitations"], "branch_causal_evidence": False}
        save(HERE / "RESULTS.json", output)
        print(json.dumps({"finished": True, "rows": len(rows), "curves": len(rows) * 2,
                          "elapsed_seconds": elapsed, "results_sha256": sha(HERE / "RESULTS.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
