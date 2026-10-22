"""Prepare or summarize final-video CPU pose measurements with frozen R149 settings."""
import argparse
import importlib.util
import json
import shutil
from pathlib import Path

from prepare import ROOT, bind, read

OLD = ROOT.parent / "h3-guidance-schedule-eval-r149-20261020" / "sam_final_pose"


def verify(record):
    if bind(Path(record["file"]))["sha256"] != record["sha256"]:
        raise ValueError("Evidence hash changed: " + record["file"])


def prepare(role):
    result = read(ROOT / "results" / "05_real_megumi_v" / f"{role}.json")
    verify(result["video"])
    verify(result["execution_evidence"])
    folder = ROOT / "sam_final_pose" / role
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / "REQUEST.json"
    if destination.exists():
        raise ValueError("Preserve the existing extraction request.")
    remote = Path("/data4/researcher/h3_runs/reciprocal_time_eval_r151_20261021/sam_final_pose") / role
    request = read(OLD / "early" / "REQUEST.json")
    request.update(
        video={"file": str(remote / "video.mp4"), "sha256": result["video"]["sha256"]},
        gate=result["execution_evidence"], output_dir=str(remote),
        plan=bind(OLD / "PLAN.json"))
    destination.write_text(json.dumps(request, indent=2) + "\n")
    shutil.copy2(OLD / "early" / "extract_final_cpu.py", folder / "extract_final_cpu.py")
    print(json.dumps({"request": str(destination), "local_video": result["video"]["file"],
                      "remote_directory": str(remote)}, ensure_ascii=False))


def summarize(role):
    folder = ROOT / "sam_final_pose" / role
    output = folder / "RESULT.json"
    if output.exists():
        raise ValueError("Preserve completed measurement.")
    pose_file = folder / "video.pose.json"
    pose = read(pose_file)
    result = read(ROOT / "results" / "05_real_megumi_v" / f"{role}.json")
    verify(result["video"])
    plan = read(OLD / "PLAN.json")
    for record in [*plan["reuse_poses"].values(), *plan["code"].values()]:
        verify(record)
    v = pose["video"]
    assert v["sha256"] == result["video"]["sha256"]
    assert (v["width"], v["height"], v["container_frame_count"], v["fps"]) == (1312, 736, 141, 24)
    assert [f["frame"] for f in pose["frames"]] == list(range(141))
    provenance = pose["provenance"]
    assert provenance["device"] == "cpu" and provenance["providers"] == ["CPUExecutionProvider"]
    source_provenance = read(Path(plan["reuse_poses"]["source"]["file"]))["provenance"]
    for key in ("detector_sha256", "pose_sha256", "detector_code_sha256",
                "pose_code_sha256", "selection_rule"):
        assert provenance[key] == source_provenance[key], key
    assert provenance["script_sha256"] == plan["code"]["pose_probe.py"]["sha256"]
    assert plan["windows"] == [[50, 65], [69, 81], [80, 92], [99, 111]]
    assert plan["confidence_thresholds"] == [0.3, 0.5]
    assert plan["max_lag"] == 24 and plan["feature"] == "arm_direction"
    spec = importlib.util.spec_from_file_location("frozen_metric", plan["code"]["timing_metrics.py"]["file"])
    metric = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metric)
    measurements = []
    for threshold in plan["confidence_thresholds"]:
        source = metric.load_pose(plan["reuse_poses"]["source"]["file"], threshold)
        edited = metric.load_pose(pose_file, threshold)
        for window in plan["windows"]:
            measurements.append(dict(confidence=threshold, **metric.clean(
                metric.local_diagnostic(source, edited, window, plan["max_lag"], plan["feature"]))))
    output.write_text(json.dumps({
        "schema": "r151-final-video-arm-direction-v1", "role": role,
        "video": result["video"], "pose": bind(pose_file), "plan": bind(OLD / "PLAN.json"),
        "measurements": measurements, "during_denoising": False,
        "extractor_provenance": provenance,
    }, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"result": str(output), "lags": [
        {k: m[k] for k in ("confidence", "window", "reliable_lag_frames")}
        for m in measurements]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "summarize"))
    parser.add_argument("--role", choices=("reverse", "combined"), required=True)
    args = parser.parse_args()
    (prepare if args.action == "prepare" else summarize)(args.role)
