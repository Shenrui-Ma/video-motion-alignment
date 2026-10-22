"""Apply the unchanged historical final-video pose metric to one new final pose."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from prepare_comparison import bound, read, require


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pose", type=Path, required=True)
    args = parser.parse_args()
    plan = read(ROOT / "sam_final_pose/PLAN.json")
    presentation = read(ROOT / "review/05_real_megumi_v/PRESENTATION.json")
    actual = presentation["inputs"]["fixed_phase"]
    require(bound(actual["file"]) == actual, "Final video changed")
    pose = read(args.pose)
    video = pose["video"]
    require(video["sha256"] == actual["sha256"]
            and (video["width"], video["height"], video["container_frame_count"], video["fps"])
            == (1312, 736, 141, 24), "Pose belongs to another video/domain")
    require([f["frame"] for f in pose["frames"]] == list(range(141)), "Full final-video pose required")
    provenance = pose["provenance"]
    require(provenance["device"] == "cpu" and provenance["providers"] == ["CPUExecutionProvider"],
            "Expected CPU final-video extraction")
    source = plan["reuse_poses"]["source"]
    require(bound(source["file"]) == source, "Historical source pose changed")
    old_pose = read(source["file"])
    for key in ("detector_sha256", "pose_sha256", "detector_code_sha256",
                "pose_code_sha256", "selection_rule"):
        require(provenance[key] == old_pose["provenance"][key], "Pose extraction differs: " + key)
    # The cached source predates the generated-video extractor revision.
    # Match the latter exactly for the new generated video, retaining both hashes.
    for role in ("native", "fixed"):
        cached = plan["reuse_poses"][role]
        require(bound(cached["file"]) == cached, "Historical generated pose changed")
        prior = read(cached["file"])["provenance"]
        require(provenance["script_sha256"] == prior["script_sha256"]
                == plan["code"]["pose_probe.py"]["sha256"],
                "Generated-video extractor differs")
    code = plan["code"]["timing_metrics.py"]
    require(bound(code["file"]) == code, "Historical metric changed")
    spec = importlib.util.spec_from_file_location("sam_historical_timing", code["file"])
    metric = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metric)
    measurements = []
    for threshold in plan["confidence_thresholds"]:
        original = metric.load_pose(source["file"], threshold)
        edited = metric.load_pose(args.pose, threshold)
        for window in plan["windows"]:
            measurements.append(dict(
                confidence=threshold,
                **metric.clean(metric.local_diagnostic(
                    original, edited, window, plan["max_lag"], plan["feature"]))))
    result = {
        "schema": "r148-sam-final-arm-direction-v1",
        "source_id": "05_real_megumi_v", "final_video": actual,
        "source_pose": source, "final_pose": bound(args.pose), "metric_code": code,
        "plan": bound(ROOT / "sam_final_pose/PLAN.json"), "measurements": measurements,
        "manual_event_boundaries": False, "during_denoising": False,
        "extractor_provenance": {
            "source_script_sha256": old_pose["provenance"]["script_sha256"],
            "generated_script_sha256": provenance["script_sha256"],
            "historical_native_fixed_script_equal": True,
            "detector_pose_weights_code_and_selection_equal": True,
            "software_versions": {k: provenance[k] for k in ("torch", "opencv", "onnxruntime")},
            "source_software_versions": {k: old_pose["provenance"][k]
                                        for k in ("torch", "opencv", "onnxruntime")},
        },
        "scope_zh": "成片后沿用历史手臂方向时差诊断；缺测保留为空，不改人工动作事件定义。",
    }
    output = ROOT / "sam_final_pose/RESULT.json"
    require(not output.exists(), "Do not overwrite a completed diagnostic")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"result": bound(output), "measurements": [
        {k: m[k] for k in ("confidence", "window", "reliable_lag_frames")}
        for m in measurements]}))


if __name__ == "__main__":
    main()
