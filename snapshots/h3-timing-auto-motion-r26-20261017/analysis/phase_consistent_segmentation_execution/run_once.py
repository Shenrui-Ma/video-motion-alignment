"""One locked CPU phase. Real numeric phases require root-bound authorization."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import traceback
import uuid

for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[name] = "4"

HERE = Path(__file__).resolve().parent
DESIGN = HERE.parent / "phase_consistent_segmentation_design"
DESIGN_SHA = "1cea183950477d773a6297169ef8b77fd3a0b65cddc73feafc3cc64e37943119"
INPUT_SHA = "2386219d3264c320365dd8ce076310103d6085a37ff56b8a266cccb3b0e6f3fc"
LOCK = Path("/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock")


def record(path):
    path = Path(path)
    data = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def read(path):
    return json.loads(Path(path).read_text())


def write_new(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(obj, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def commit_new(path, obj, used_records):
    """A complete JSON becomes visible atomically and never replaces a result."""
    path = Path(path)
    data = (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        for item in used_records:
            require_record(item)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def ensure_no_complete(path):
    if not Path(path).exists():
        return
    try:
        existing = read(path)
        if existing.get("status") != "complete" or not isinstance(existing.get("files"), list):
            raise ValueError("invalid completion structure")
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Partial/corrupt completion marker requires explicit recovery: " + str(path)) from exc
    raise FileExistsError("Already complete: " + str(path))


def require_record(item):
    actual = record(item["path"])
    if actual["sha256"] != item["sha256"]:
        raise ValueError("SHA mismatch: " + item["path"])
    return actual


def check_design():
    if record(DESIGN / "FREEZE.json")["sha256"] != DESIGN_SHA:
        raise ValueError("Design freeze changed")
    for item in read(DESIGN / "FREEZE.json")["files"]:
        require_record(item)
    if record(DESIGN / "INPUTS.json")["sha256"] != INPUT_SHA:
        raise ValueError("Inputs manifest changed")
    return read(DESIGN / "INPUTS.json")


def verify_execution():
    freeze = read(HERE / "FREEZE.json")
    for item in freeze["files"]:
        require_record(item)
    return record(HERE / "FREEZE.json")["sha256"]


def authorize(phase, target_id=None):
    execution_sha = verify_execution()
    name = "ROOT_CALIBRATION_AUTHORIZATION.json" if phase == "calibration" else "ROOT_TARGET_AUTHORIZATION.json"
    auth = read(HERE / name)
    expected = {"authorized": True, "phase": phase,
                "execution_freeze_sha256": execution_sha, "design_freeze_sha256": DESIGN_SHA,
                "inputs_sha256": INPUT_SHA}
    for key, value in expected.items():
        if (key == "authorized" and auth.get(key) is not True) or auth.get(key) != value:
            raise ValueError("Authorization mismatch: " + key)
    if phase == "target":
        if target_id not in auth.get("allowed_target_ids", []):
            raise ValueError("Target not authorized")
        complete = read(HERE / "results/CALIBRATION_COMPLETE.json")
        for item in complete["files"]:
            require_record(item)
        calibration_path = Path(complete["calibration_json"]["path"])
        if record(calibration_path)["sha256"] != auth.get("calibration_sha256"):
            raise ValueError("Calibration not bound by authorization")
    return record(HERE / name)


def validate_grid(data):
    frames = data["frames"]
    ids = [r["frame"] for r in frames]
    fps = data["video"]["fps"]
    if len(frames) != 141 or ids != list(range(141)):
        raise ValueError("Input must retain all 141 zero-based physical frame records")
    if not isinstance(fps, (int, float)) or isinstance(fps, bool) or not math.isfinite(fps) or abs(fps - 24.0) > 1e-9:
        raise ValueError("Input fps must be finite and match the frozen 24 fps grid")
    for i, item in enumerate(frames):
        timestamp = item["time_s"]
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool) or not math.isfinite(timestamp) or abs(timestamp - i / 24.0) > 1e-8:
            raise ValueError("Physical timestamps must match the frozen i/24 grid")
    return {"records": 141, "fps": fps}


def check_metadata(inputs):
    checks = []
    poses = [s["identity_pose"] for s in inputs["sources"]]
    poses += [v for s in inputs["sources"] for v in s["calibration_views"] if v["view"] != "identity"]
    poses += [t["pose"] for t in inputs["targets"]]
    for item in poses:
        actual = require_record(item)
        data = read(item["path"])
        checks.append(actual | validate_grid(data))
    return {"status": "pass", "pose_files": len(checks), "checks": checks,
            "scope": "hash/schema/frame metadata only; no pose scores"}


def save_npz(path, arrays):
    import numpy as np
    with Path(path).open("xb") as handle:
        np.savez_compressed(handle, **arrays)


def source_metadata(source):
    data = read(source["identity_pose"]["path"])
    import numpy as np
    return np.array([r["time_s"] for r in data["frames"]]), float(data["video"]["fps"])


def calibrate(inputs, attempt, used_records):
    import segmentation as s
    source = next(x for x in inputs["sources"] if x["source_id"] == "source05")
    results_dir = HERE / "results/calibration" / attempt
    ensure_no_complete(HERE / "results/CALIBRATION_COMPLETE.json")
    results_dir.mkdir(parents=True, exist_ok=False)
    times, fps = source_metadata(source)
    start = time.perf_counter()
    loaded, feature_failures = {}, {}
    for view in source["calibration_views"]:
        require_record(view)
        loaded[view["view"]], feature_failures[view["view"]] = s.load_thresholds(view["path"])
    load_seconds = time.perf_counter() - start
    all_scans, evidence_files, pair_reports = [], [], []
    scan_seconds = 0.0
    for first in ("identity", "flip", "pad16"):
        for second in ("identity", "flip", "pad16"):
            if first == second:
                continue
            pair = first + "__" + second
            start = time.perf_counter()
            scan = s.full_scan(loaded[first], loaded[second], times, fps)
            duration = time.perf_counter() - start
            scan_seconds += duration
            all_scans.append((pair, scan))
            path = results_dir / (pair + ".npz")
            save_npz(path, s.evidence_archive(scan))
            evidence_files.append(record(path))
            pair_reports.append({"pair": pair, "scan_seconds": duration,
                                 "counts": {p: scan[p]["counts"] for p in s.PARTS}})
    result = s.calibration_max(all_scans)
    result.update(source_id="source05", views=list(loaded), pairs=pair_reports,
                  feature_failures=feature_failures, inputs_sha256=INPUT_SHA,
                  timing_seconds={"feature_load": load_seconds, "scan": scan_seconds})
    path = results_dir / "CALIBRATION.json"
    write_new(path, result)
    complete = {"status": "complete", "calibration_json": record(path),
                "files": [record(path), *evidence_files], "semantic_guarantee": None}
    commit_new(HERE / "results/CALIBRATION_COMPLETE.json", complete,
               [*used_records, source["identity_pose"], *source["calibration_views"], *complete["files"]])
    return complete


def target_phase(inputs, target_id, attempt, used_records):
    import segmentation as s
    target = next(x for x in inputs["targets"] if x["id"] == target_id)
    source = next(x for x in inputs["sources"] if x["source_id"] == target["source_id"])
    safe_id = target_id.replace(":", "__")
    root = HERE / "results/targets" / safe_id
    ensure_no_complete(root / "COMPLETE.json")
    results_dir = root / attempt
    results_dir.mkdir(parents=True, exist_ok=False)
    complete = read(HERE / "results/CALIBRATION_COMPLETE.json")
    calibration_records = [record(HERE / "results/CALIBRATION_COMPLETE.json"), *complete["files"]]
    calibration = read(complete["calibration_json"]["path"])
    if calibration["lambda"] is None:
        raise ValueError("UNKNOWN_CALIBRATION; target scoring not permitted")
    require_record(source["identity_pose"])
    require_record(target["pose"])
    times, fps = source_metadata(source)
    start = time.perf_counter()
    a, source_failure = s.load_thresholds(source["identity_pose"]["path"])
    b, target_failure = s.load_thresholds(target["pose"]["path"])
    load_seconds = time.perf_counter() - start
    start = time.perf_counter()
    scan = s.full_scan(a, b, times, fps)
    scan_seconds = time.perf_counter() - start
    methods = s.evaluate(scan, calibration["lambda"])
    result = {"target": target, "lambda": calibration["lambda"],
              "calibration_sha256": complete["calibration_json"]["sha256"],
              "scale_transfer": target["source_id"] != "source05",
              "feature_failures": {"source": source_failure, "target": target_failure},
              "methods": methods, "frame_observability": s.frame_observability(scan),
              "scan_counts": {p: scan[p]["counts"] for p in s.PARTS},
              "timing_seconds": {"feature_load": load_seconds, "full_scan": scan_seconds},
              "interpretation": "observer proposals on historical trajectory or final-only pose; semantic labels UNKNOWN"}
    path = results_dir / "RESULT.json"
    write_new(path, result)
    evidence = results_dir / "EVIDENCE.npz"
    save_npz(evidence, s.evidence_archive(scan))
    complete = {"status": "complete", "target_id": target_id,
                "result": record(path), "files": [record(path), record(evidence)]}
    commit_new(root / "COMPLETE.json", complete,
               [*used_records, source["identity_pose"], target["pose"], *calibration_records, *complete["files"]])
    return complete


def finalize(inputs, used_records):
    # Aggregate only immutable result rows; no numerical rescoring.
    import segmentation as s
    rows = []
    full_results = {}
    result_records = []
    for target in inputs["targets"]:
        complete = read(HERE / "results/targets" / target["id"].replace(":", "__") / "COMPLETE.json")
        for item in complete["files"]:
            require_record(item)
        result_records.extend(complete["files"])
        result_records.append(record(HERE / "results/targets" / target["id"].replace(":", "__") / "COMPLETE.json"))
        result = read(complete["result"]["path"])
        full_results[target["id"]] = result
        methods = {}
        for name, method in result["methods"].items():
            qualified = [r for r in method["selected"] if r["status"].startswith("PHASE_CANDIDATE")]
            methods[name] = {"K": method["K"], "qualified_K": method["qualified_K"],
                             "delay": sum(r["lag"] > 0 for r in qualified),
                             "advance": sum(r["lag"] < 0 for r in qualified),
                             "rejected_K": method["rejected_K"],
                             "coverage": method["coverage"],
                             "positive_best_phase_intervals_by_part": method["positive_best_phase_intervals_by_part"],
                             "reasons": [r["reasons"] for r in method["selected"] if r["reasons"]],
                             "timing_seconds": method["timing_seconds"]}
        rows.append({"id": target["id"], "stage": target["stage"], "run_id": target["run_id"],
                     "endpoint_index": target["endpoint_index"], "source_id": target["source_id"],
                     "methods": methods, "result": complete["result"]})
    trajectory = []
    for run in sorted({r["run_id"] for r in rows if r["endpoint_index"] is not None}):
        group = [r for r in rows if r["run_id"] == run]
        if sorted(r["endpoint_index"] for r in group) != list(range(20)):
            raise ValueError("Incomplete trajectory")
        trajectory.append({"run_id": run, "endpoint_count": 20,
                           "methods": {m: {"endpoints_with_delay": sum(r["methods"][m]["delay"] > 0 for r in group),
                                            "denominator_endpoints": 20,
                                            "qualified_proposals": sum(r["methods"][m]["qualified_K"] for r in group),
                                            "coverage_sum": {k: sum(r["methods"][m]["coverage"][k] for r in group)
                                                             for k in group[0]["methods"][m]["coverage"] if k != "note"},
                                            "persistence": s.adjacent_persistence({r["endpoint_index"]: full_results[r["id"]]["methods"][m] for r in group})}
                                       for m in group[0]["methods"]}})
    output = {"status": "complete", "rows": rows, "trajectories": trajectory,
              "full_trajectory_endpoints": 60, "final_only_stress": 3,
              "semantic_accuracy": None, "false_positive_rate": None,
              "note": "Full per-slot coverage and competitors remain in each RESULT.json. Correlated endpoints are not independent samples."}
    commit_new(HERE / "results/SUMMARY.json", output, [*used_records, *result_records])
    return record(HERE / "results/SUMMARY.json")


def timeout_handler(signum, frame):
    raise TimeoutError("Bounded phase exceeded 120 seconds")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("check", "tests", "calibration", "target", "finalize"))
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--target-id")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", args.attempt):
        parser.error("Invalid attempt id")
    audit = HERE / "audit"
    audit.mkdir(exist_ok=True)
    receipt_path = audit / (args.attempt + ".json")
    if receipt_path.exists():
        raise FileExistsError("Attempt receipt already exists")
    start = time.monotonic()
    receipt = {"phase": args.phase, "attempt": args.attempt, "target_id": args.target_id,
               "started_unix": time.time(), "pid": os.getpid(), "threads_max": 4}
    write_new(audit / (args.attempt + ".claim"), receipt)
    with LOCK.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            write_new(receipt_path, receipt | {"status": "busy", "exit_code": 75})
            print("BUSY")
            return 75
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(120)
        try:
            inputs = check_design()
            receipt["code_files"] = [record(p) for p in sorted(HERE.rglob("*.py"))]
            used = [*receipt["code_files"], record(DESIGN / "FREEZE.json"), record(DESIGN / "INPUTS.json")]
            if args.phase == "check":
                result = check_metadata(inputs)
            elif args.phase == "tests":
                command = [sys.executable, "-m", "unittest", "discover", "-s", str(HERE / "tests"), "-v"]
                run = subprocess.run(command, cwd=HERE, capture_output=True, text=True, timeout=100)
                log = audit / (args.attempt + ".log")
                with log.open("x") as handle:
                    handle.write(run.stdout + run.stderr)
                if run.returncode:
                    raise RuntimeError("Synthetic tests failed: " + str(log))
                stress = subprocess.run([sys.executable, str(HERE / "tests/test_segmentation.py"), "--stress"],
                                        cwd=HERE, capture_output=True, text=True, timeout=max(1, 110 - (time.monotonic() - start)))
                if stress.returncode:
                    raise RuntimeError("Synthetic stress failed: " + stress.stderr)
                stress_path = audit / (args.attempt + "_stress.json")
                write_new(stress_path, json.loads(stress.stdout))
                result = {"unit_log": record(log), "stress": record(stress_path)}
            elif args.phase == "calibration":
                receipt["authorization"] = authorize("calibration")
                receipt["metadata_gate"] = check_metadata(inputs)
                result = calibrate(inputs, args.attempt, [*used, receipt["authorization"], record(HERE / "FREEZE.json")])
            elif args.phase == "target":
                receipt["authorization"] = authorize("target", args.target_id)
                receipt["metadata_gate"] = check_metadata(inputs)
                result = target_phase(inputs, args.target_id, args.attempt, [*used, receipt["authorization"], record(HERE / "FREEZE.json")])
            else:
                # No endpoint rescoring; admission still binds all target authorizations.
                for target in inputs["targets"]:
                    authorize("target", target["id"])
                result = finalize(inputs, [*used, record(HERE / "ROOT_TARGET_AUTHORIZATION.json"), record(HERE / "FREEZE.json")])
            receipt.update(status="pass", result=result, exit_code=0)
        except Exception as exc:
            receipt.update(status="failed", error=str(exc), traceback=traceback.format_exc(), exit_code=1)
        finally:
            signal.alarm(0)
            receipt["elapsed_seconds"] = time.monotonic() - start
            write_new(receipt_path, receipt)
    print(json.dumps({k: receipt[k] for k in ("phase", "status", "exit_code", "elapsed_seconds")}))
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
