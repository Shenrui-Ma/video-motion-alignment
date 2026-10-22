"""Posthoc descriptive comparison: never alters pilot parameters or selects a winner."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results_v2"
POSE = ROOT.parent / "h3-threecase-auto-r144-20261020/input_audit/short_0358/source_full.pose.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")


pose = json.loads(POSE.read_text())
labels = json.loads((OUT / "RGB_LABELS_UNTUNED.json").read_text())
summary = json.loads((OUT / "SUMMARY.json").read_text())
source = json.loads((OUT / "SOURCE.json").read_text())
windows = [[20, 51], [40, 71], [60, 91]]
source_tiles = []
for window in windows:
    occupancy = Counter()
    joints = []
    for frame in pose["frames"]:
        if not window[0] <= frame["frame"] <= window[1]:
            continue
        person = frame["persons"][frame["selected_person"]]
        for index in range(5, 11):  # both shoulders, elbows and wrists
            if person["coco17_score"][index] < 0.3:
                continue
            px, py = person["coco17_xy"][index]
            if not (0 <= px < pose["video"]["width"] and 0 <= py < pose["video"]["height"]):
                continue
            # H3 patch grid 41x23 exactly maps the 1312x736 canvas at 32px/patch.
            gy, gx = py / 32, px / 32
            for tile in source["tiles"]:
                (y0, y1), (x0, x1) = tile["patch_bounds_yx_half_open"]
                if y0 <= gy < y1 and x0 <= gx < x1:
                    occupancy[tuple(tile["tile"])] += 1
            joints.append([frame["frame"], index, px, py])
    source_tiles.append({
        "window": window, "joint_occupancy_by_tile": {str(k): v for k, v in sorted(occupancy.items())},
        "tiles": [list(k) for k in sorted(occupancy)], "valid_joint_samples": len(joints),
    })

rows = []
global_preserved = True
for step in range(10):
    row = json.loads((OUT / f"step{step:03d}.json").read_text())
    old = json.loads((ROOT / "results_v1" / f"step{step:03d}.json").read_text())
    preserved = all(row["original_global"][k] == v["readout"] for k, v in old["methods"].items())
    global_preserved &= preserved
    label = next((x for x in labels if x["step"] == step), None)
    regional = []
    for source_scope in source_tiles:
        lo, hi = source_scope["window"]
        # All windows entirely inside the RGB interval, and every tile touched by
        # at least one source arm joint. No lag, score or target label is used here.
        selected = [
            r for r in row["local_matching"]["rows"]
            if r["tile"] in source_scope["tiles"]
            and lo <= r["source_frame_coverage"][0]
            and r["source_frame_coverage"][1] <= hi
        ]
        accepted = [r for r in selected if r["status"] == "candidate"]
        regional.append({
            "window": [lo, hi], "tiles": source_scope["tiles"], "scan_count": len(selected),
            "candidate_count": len(accepted),
            "candidate_lag_counts": dict(sorted(Counter(r["best"]["lag_bins"] for r in accepted).items())),
            "candidate_physical_offset_sets": dict(Counter(
                str(r["best"]["physical_frame_offsets"]) for r in accepted)),
            "all_rows": [{k: v for k, v in r.items() if k not in ("curve", "distinct_rival")}
                         for r in selected],
            "rgb_measurements": ([w for w in label["windows"] if w["window"] == [lo, hi]] if label else None),
        })
    rows.append({"step": step, "v1_global_exactly_preserved": preserved, "regions": regional})

analysis = {
    "role": "posthoc evaluation; no tuning, no control decision",
    "pose_source": str(POSE), "pose_sha256": sha(POSE),
    "input_summary_sha256": sha(OUT / "SUMMARY.json"),
    "source_scope_rule": "all source arm joints with confidence>=0.3 inside canvas; all touched adaptive cells",
    "source_window_rule": "scan window must be fully within the RGB source interval",
    "source_joint_tile_mapping": source_tiles,
    "tile_warning": "coordinate overlap is approximate; VAE features have wider receptive fields",
    "time_warning": "4/8 transitions span nonuniform frame durations; no interpolation; physical offsets remain sets",
    "rows": rows, "v1_global_exactly_preserved": global_preserved,
    "total_scan_rows": sum(r["local_matching"]["total"] for r in summary["rows"]),
    "total_candidates": sum(r["local_matching"]["candidate"] for r in summary["rows"]),
    "timing_median_seconds": {k: statistics.median(r[k] for r in summary["rows"])
                              for k in ("total_seconds", "phase_difference_seconds",
                                        "matching_seconds", "scan_seconds")},
    "constraints": {"CPU_threads": summary["threads"], "CUDA_initialized": summary["CUDA_initialized"],
                    "GPU_model_VAE_forwards": summary["GPU_model_VAE_forwards"]},
}
write(OUT / "POSTHOC_EVALUATION.json", analysis)
print(json.dumps({k: v for k, v in analysis.items() if k not in ("rows", "source_joint_tile_mapping")}, indent=2))
for row in rows:
    print(row["step"], [(r["window"], r["scan_count"], r["candidate_count"], r["candidate_lag_counts"])
                        for r in row["regions"]])
