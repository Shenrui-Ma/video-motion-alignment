"""Summarize cached final-video poses using the frozen R149 measurement plan."""
import argparse
import importlib.util
import json
from pathlib import Path

from prepare import ROOT, bind, read
from sam_pose import OLD, verify


def compact(measurement):
    return {
        "confidence": measurement["confidence"],
        "window": measurement["window"],
        "lag_frames": measurement.get("reliable_lag_frames"),
        "same_frame_error": measurement.get("same_frame", {}).get("error"),
        "coverage": measurement.get("same_frame", {}).get("coverage"),
        "status": measurement["status"],
        "flags": measurement.get("flags", []),
    }


def summarize(final=False):
    plan_file = OLD / "PLAN.json"
    plan = read(plan_file)
    for record in [*plan["reuse_poses"].values(), *plan["code"].values()]:
        verify(record)
    spec = importlib.util.spec_from_file_location(
        "frozen_metric", plan["code"]["timing_metrics.py"]["file"])
    metric = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metric)
    manifest = read(ROOT / "EVALUATION_MANIFEST.json")
    case = next(c for c in manifest["cases"] if c["source_id"] == "05_real_megumi_v")
    native_pose = read(Path(plan["reuse_poses"]["native"]["file"]))
    assert native_pose["video"]["sha256"] == case["native_MF"]["actual_generated_video_sha256"]
    measurements = []
    for confidence in plan["confidence_thresholds"]:
        source = metric.load_pose(plan["reuse_poses"]["source"]["file"], confidence)
        native = metric.load_pose(plan["reuse_poses"]["native"]["file"], confidence)
        for window in plan["windows"]:
            measurements.append(compact(dict(confidence=confidence, **metric.clean(
                metric.local_diagnostic(source, native, window, plan["max_lag"], plan["feature"])))))
    roles = {"native": {
        "pose": plan["reuse_poses"]["native"], "measurements": measurements}}
    inputs = {"forward": OLD / "early" / "RESULT.json"}
    inputs.update({role: ROOT / "sam_final_pose" / role / "RESULT.json"
                   for role in ("reverse", "combined")})
    for role, path in inputs.items():
        if not path.exists():
            if final:
                raise ValueError("Missing final pose measurement: " + role)
            continue
        result = read(path)
        record = result["video"] if role != "forward" else result["final_video"]
        verify(record)
        expected = (case["forward_MF"]["actual_generated_video_sha256"] if role == "forward"
                    else read(ROOT / "results" / case["source_id"] / f"{role}.json")["video"]["sha256"])
        assert record["sha256"] == expected
        assert len(result["measurements"]) == 8 and not result["during_denoising"]
        roles[role] = {
            "evidence": bind(path),
            "measurements": [compact(m) for m in result["measurements"]],
        }
    output = ROOT / "reviews" / case["source_id"] / "TIMING_SUMMARY.json"
    output.write_text(json.dumps({
        "schema": "r151-sam-cached-pose-summary-v1",
        "plan": bind(plan_file),
        "roles": roles,
        "complete": len(roles) == 4,
        "primary_window": [50, 65],
        "units": "frames at 24 fps; positive lag means edited action occurs later",
        "scope": "Offline final-video arm-direction comparison; inference receives no pose feedback.",
    }, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "file": str(output),
        "primary_lags": {role: data["measurements"][0]["lag_frames"] for role, data in roles.items()},
    }))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--final", action="store_true")
    summarize(parser.parse_args().final)
