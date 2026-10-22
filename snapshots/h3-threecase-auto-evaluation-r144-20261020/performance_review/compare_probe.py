"""CPU comparison of saved GPU poses with the original pose and policy."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import types

import numpy as np

ROOT = Path(__file__).resolve().parent
CASE = ROOT.parents[1] / "h3-threecase-auto-r144-20261020/cases/short_0358_cached_gpu2"
# The reviewed modules are pure CPU; bypass ComfyUI node-package initialization.
sys.path.insert(0, str(CASE / "scripts"))
package = types.ModuleType("H3AutomaticWindowRouter")
package.__path__ = [str(CASE / "extensions/H3AutomaticWindowRouter")]
sys.modules[package.__name__] = package
from H3AutomaticWindowRouter.geometry import Geometry
from H3AutomaticWindowRouter.selector import Controller
from adult_selector import adult_only
from scan_current_pose import observe


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def discrete_scan(row):
    return {
        "window": row["window"], "feature": row["feature"],
        "baseline": row["baseline"], "status": row["status"],
        "measurements": {c: {k: d.get(k) for k in ("status", "flags", "reliable_lag_frames")}
                         for c, d in row["measurements"].items()},
        "gain_pass_0_5": row.get("min_gain", -1) >= .5,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--steps", type=int, nargs="+", required=True)
    parser.add_argument("--gpu-output-name", required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    manifest = read(ROOT / "PROBE_MANIFEST.json")
    protocol = read(CASE / "configs/protocol.json")
    geometry = Geometry.from_case(protocol["cases"][0])
    bounds = protocol["person_selection"]["selected_bbox_center_x_fraction"]
    rgb_by_step = {r["step"]: r for r in read(ROOT / "HOST41_DECODED_RGB.json")["steps"]}
    source = CASE / "configs/source.pose.json"
    cpu_controller, gpu_controller = Controller(geometry), Controller(geometry)
    rows = []
    # Reproduce the complete prefix because persistence is stateful.
    for step in manifest["steps"]:
        index = step["step"]
        if index > max(args.steps):
            continue
        bundle = args.bundle if index in args.steps else ROOT / "host9_step0"
        output_name = args.gpu_output_name if index in args.steps else "step0_gpu"
        directory = step["directory"]
        cpu_path = bundle / "inputs" / directory / "pose/native.pose.json"
        gpu_path = bundle / output_name / "poses" / (directory + ".pose.json")
        cpu, gpu = read(cpu_path), read(gpu_path)
        assert hashlib.sha256(cpu_path.read_bytes()).hexdigest() == step["reference_cpu_pose_sha256"]
        assert cpu["video"]["sha256"] == gpu["video"]["sha256"] == step["video"]["sha256"]
        assert cpu["extraction"] == gpu["extraction"]
        assert len(cpu["frames"]) == len(gpu["frames"]) == 107
        count_equal = all(len(a["persons"]) == len(b["persons"])
                          for a, b in zip(cpu["frames"], gpu["frames"]))
        assert count_equal, "Detector changed per-frame person count; needs matching review"
        selection_equal = all(a["selected_person"] == b["selected_person"]
                              for a, b in zip(cpu["frames"], gpu["frames"]))
        xy_diff, score_diff, box_diff, detector_diff = [], [], [], []
        conf_flips = {"0.3": 0, "0.5": 0}
        for a, b in zip(cpu["frames"], gpu["frames"]):
            for person_a, person_b in zip(a["persons"], b["persons"]):
                xy_diff.extend(np.abs(np.array(person_a["coco17_xy"]) -
                                      np.array(person_b["coco17_xy"])).ravel())
                scores_a, scores_b = np.array(person_a["coco17_score"]), np.array(person_b["coco17_score"])
                score_diff.extend(np.abs(scores_a - scores_b))
                box_diff.extend(np.abs(np.array(person_a["box_xyxy"]) - np.array(person_b["box_xyxy"])))
                detector_diff.append(abs(person_a["detector_score"] - person_b["detector_score"]))
                for threshold in (.3, .5):
                    conf_flips[str(threshold)] += int(np.sum((scores_a >= threshold) != (scores_b >= threshold)))
        cpu_filtered, cpu_rejected = adult_only(cpu, geometry.video_geometry, bounds)
        gpu_filtered, gpu_rejected = adult_only(gpu, geometry.video_geometry, bounds)
        cpu_filtered_path = args.output / f"step{index:03d}.cpu.selected.json"
        gpu_filtered_path = args.output / f"step{index:03d}.gpu.selected.json"
        write(cpu_filtered_path, cpu_filtered)
        write(gpu_filtered_path, gpu_filtered)
        cpu_scan = observe(source, cpu_filtered_path, index, geometry)
        gpu_scan = observe(source, gpu_filtered_path, index, geometry)
        scan_changes = [{"row": n, "cpu": discrete_scan(a), "gpu": discrete_scan(b)}
                        for n, (a, b) in enumerate(zip(cpu_scan["windows"], gpu_scan["windows"]))
                        if discrete_scan(a) != discrete_scan(b)]
        measurement = lambda result: {"status": "complete", "physical_index": index, "observer": result}
        cpu_decision = cpu_controller.select(index, measurement(cpu_scan))
        gpu_decision = gpu_controller.select(index, measurement(gpu_scan))
        keys = ("chosen_full", "control_state", "route_alpha", "latent_bins", "physical_intervals",
                "all_unknown", "candidate_groups", "reliable_rows", "reason")
        cpu_action = {k: cpu_decision.get(k) for k in keys}
        gpu_action = {k: gpu_decision.get(k) for k in keys}
        row = {
            "step": index, "rgb_exact": gpu["statistics"]["decoded_rgb_sha256"] == rgb_by_step[index]["decoded_rgb_sha256"],
            "person_count_equal": count_equal, "selected_person_equal": selection_equal,
            "adult_rejections_equal": cpu_rejected == gpu_rejected,
            "max_keypoint_coordinate_diff_px": float(max(xy_diff)),
            "mean_keypoint_coordinate_diff_px": float(np.mean(xy_diff)),
            "p99_keypoint_coordinate_diff_px": float(np.percentile(xy_diff, 99)),
            "max_pose_score_diff": float(max(score_diff)), "confidence_threshold_flips": conf_flips,
            "max_detector_box_coordinate_diff_px": float(max(box_diff)),
            "max_detector_score_diff": max(detector_diff),
            "scan_rows": len(cpu_scan["windows"]), "discrete_scan_changes": scan_changes,
            "action_equal": cpu_action == gpu_action, "cpu_action": cpu_action, "gpu_action": gpu_action,
            "cpu_statistics": cpu["statistics"], "gpu_statistics": gpu["statistics"],
        }
        rows.append(row)
        write(args.output / f"step{index:03d}.comparison.json", row)
    summary = {"steps": rows, "all_actions_equal": all(r["action_equal"] for r in rows),
               "all_rgb_exact": all(r["rgb_exact"] for r in rows),
               "all_discrete_scan_rows_equal": all(not r["discrete_scan_changes"] for r in rows)}
    write(args.output / "RESULT.json", summary)
    print(json.dumps([{k: r[k] for k in ("step", "rgb_exact", "max_keypoint_coordinate_diff_px",
        "max_pose_score_diff", "confidence_threshold_flips", "action_equal")} |
        {"discrete_scan_changed_rows": len(r["discrete_scan_changes"]), "gpu_elapsed_s": r["gpu_statistics"]["elapsed_s"]}
        for r in rows], ensure_ascii=False))


if __name__ == "__main__":
    main()
