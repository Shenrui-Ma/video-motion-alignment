"""Measure one final Sam video with the unchanged historical arm-direction code."""
import argparse
import importlib.util
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import bound, read, require, verify_record, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule", required=True, choices=("early", "late", "split", "global_weak"))
    parser.add_argument("--pose", type=Path, required=True)
    args = parser.parse_args()
    plan = read(ROOT / "sam_final_pose/PLAN.json")
    pres = read(ROOT / "review/05_real_megumi_v" / args.schedule / "PRESENTATION.json")
    actual = pres["new_video"]
    verify_record(actual)
    pose = read(args.pose)
    v = pose["video"]
    require(v["sha256"] == actual["sha256"] and
            (v["width"], v["height"], v["container_frame_count"], v["fps"]) == (1312, 736, 141, 24),
            "Pose belongs to another final video or frame domain")
    require([f["frame"] for f in pose["frames"]] == list(range(141)), "All 141 frames required")
    provenance = pose["provenance"]
    require(provenance["device"] == "cpu" and provenance["providers"] == ["CPUExecutionProvider"],
            "CPU final-video extraction required")
    for record in list(plan["reuse_poses"].values()) + list(plan["code"].values()):
        verify_record(record)
    old_source = read(plan["reuse_poses"]["source"]["file"])
    for key in ("detector_sha256", "pose_sha256", "detector_code_sha256",
                "pose_code_sha256", "selection_rule"):
        require(provenance[key] == old_source["provenance"][key], "Historical extractor differs: " + key)
    for role in ("native", "fixed"):
        prior = read(plan["reuse_poses"][role]["file"])["provenance"]
        require(provenance["script_sha256"] == prior["script_sha256"] ==
                plan["code"]["pose_probe.py"]["sha256"], "Historical generated extractor differs")
    require(plan["feature"] == "arm_direction" and plan["max_lag"] == 24 and
            plan["confidence_thresholds"] == [0.3, 0.5] and
            plan["windows"] == [[50, 65], [69, 81], [80, 92], [99, 111]],
            "Frozen measurement settings differ")
    spec = importlib.util.spec_from_file_location("historical_sam_timing", plan["code"]["timing_metrics.py"]["file"])
    metric = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metric)
    measurements = []
    for threshold in plan["confidence_thresholds"]:
        source = metric.load_pose(plan["reuse_poses"]["source"]["file"], threshold)
        edited = metric.load_pose(args.pose, threshold)
        for window in plan["windows"]:
            measurements.append(dict(confidence=threshold, **metric.clean(
                metric.local_diagnostic(source, edited, window, plan["max_lag"], plan["feature"]))))
    output = ROOT / "sam_final_pose" / args.schedule / "RESULT.json"
    require(not output.exists(), "Preserve any completed measurement")
    write(output, {
        "schema": "r149-sam-final-arm-direction-v1", "source_id": "05_real_megumi_v",
        "schedule": args.schedule, "final_video": actual, "final_pose": bound(args.pose),
        "source_pose": plan["reuse_poses"]["source"], "metric_code": plan["code"]["timing_metrics.py"],
        "plan": bound(ROOT / "sam_final_pose/PLAN.json"), "measurements": measurements,
        "during_denoising": False, "manual_event_boundaries": False,
        "timing_scope": "Posthoc CPU evaluation; excluded from generation/sampler time.",
        "extractor_provenance": provenance})
    print({"result": bound(output), "lags": [
        {k: m[k] for k in ("confidence", "window", "reliable_lag_frames")} for m in measurements]})


if __name__ == "__main__":
    main()
