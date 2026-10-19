"""Bind a completed R49 release to the frozen author-code MF evaluator.

This entry only reads existing artifacts and writes a derived input manifest.
It does not import torch, launch tracking, or modify the frozen evaluator.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

FREEZE_SHA = "fa573e2065d1c140ef232513d73b909d2aa2902046d4a9becf609a6e549ad580"
ACTIONS = ("chest", "crouch", "fitness", "one_leg", "rotate")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def bind(metric_root, case_dir, action):
    require(action in ACTIONS, "Action outside fixed five")
    metric_root, case_dir = Path(metric_root).resolve(), Path(case_dir).resolve()
    freeze = metric_root / "RUNTIME_FREEZE.json"
    require(sha(freeze) == FREEZE_SHA, "Frozen MF evaluator differs")
    for name, value in read(freeze)["files"].items():
        expected = value["sha256"] if isinstance(value, dict) else value
        require(sha(metric_root / name) == expected, "Frozen artifact differs: " + name)
    run_id = f"r49_source_{action}_seed2026101701_native"
    require(case_dir.name == run_id, "R49 Native case directory differs")
    inventory_path = case_dir / "CASE_FILES.json"
    inventory = read(inventory_path)
    actual = {str(p.relative_to(case_dir)) for p in case_dir.rglob("*") if p.is_file()}
    require(actual == set(inventory) | {"CASE_FILES.json"}, "Release inventory incomplete or changed")
    for name, digest in inventory.items():
        path = (case_dir / name).resolve()
        require(path.is_relative_to(case_dir), "Release inventory path escapes case")
        require(sha(path) == digest, "Released artifact differs: " + name)
    metric_path = case_dir / "METRIC_INPUTS.json"
    mapping_path = case_dir / "edited49_8fps.mapping.json"
    metric, summary = read(metric_path), read(case_dir / "SUMMARY.json")
    require(metric["run_id"] == run_id and metric["official_pair_id"] == f"human/{action}/000",
            "Run or official pair differs")
    require(summary["passed"] is True and summary["run_id"] == run_id and
            summary["metric_inputs_sha256"] == sha(metric_path) and
            summary["actual_routed_blocks"] == 0, "Native release receipt differs")
    video = Path(metric["edited49"]).resolve()
    require(video == case_dir / "edited49_8fps.mp4" and sha(video) == metric["edited49_sha256"],
            "Released video differs")
    item = {"id": metric["official_pair_id"], "method": "native", "role": "generated",
            "file": str(video), "sha256": metric["edited49_sha256"],
            "generation_frame_indices": list(range(0, 147, 3)),
            "generation_binding": {
                "metric_inputs": {"file": str(metric_path), "sha256": sha(metric_path)},
                "release_mapping": {"file": str(mapping_path), "sha256": sha(mapping_path)}}}
    spec = importlib.util.spec_from_file_location("frozen_flexiact_binding", metric_root / "run_tracks.py")
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    binding = runtime.validate_generated_binding(item, video)
    timing = runtime.check_timebase(video)
    reference = metric_root / "outputs/reference" / action
    ref_report = read(reference / "REPORT.json")
    source_row = next(row for row in read(metric_root / "SOURCE_INPUTS.json")["inputs"]
                      if row["id"] == item["id"])
    require(ref_report["passed"] is True and ref_report["case"] == source_row and
            ref_report["manifest_sha256"] == sha(metric_root / "SOURCE_INPUTS.json") and
            sha(reference / "tracks.pt") == ref_report["tracks_sha256"], "Reference track cache differs")
    return {"schema": "h3-flexiact-r49-native-mf-inputs-v1", "inputs": [item],
            "method": "native", "fixed_pair_denominator": 5,
            "planned_pair_order": [f"human/{a}/000" for a in ACTIONS],
            "metric_runtime_freeze_sha256": FREEZE_SHA,
            "release_inventory": {"file": str(inventory_path), "sha256": sha(inventory_path)},
            "preflight": {"passed": True, "binding": binding, "timebase": timing,
                          "reference_report_sha256": sha(reference / "REPORT.json"),
                          "reference_tracks_sha256": ref_report["tracks_sha256"]},
            "builder_sha256": sha(__file__),
            "scope": "One completed fixed-five Native task; original FlexiAct MF functions and tracker reused. Five-task H3 adaptation, not published leaderboard reproduction."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metric-root", required=True)
    parser.add_argument("--case-dir", required=True)
    parser.add_argument("--action", choices=ACTIONS, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    record = bind(args.metric_root, args.case_dir, args.action)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(record, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "action": args.action, "manifest": str(output),
                      "sha256": sha(output), "gpu_started": False}))


if __name__ == "__main__":
    main()
