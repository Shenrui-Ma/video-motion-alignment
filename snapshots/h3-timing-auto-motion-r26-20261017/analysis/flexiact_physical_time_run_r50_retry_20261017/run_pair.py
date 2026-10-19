"""Bind public reference/Native/Auto artifacts, then run the frozen CPU metric."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
CONTRACT = json.loads((HERE / "CONTRACT.json").read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def snapshot(path):
    raw = Path(path).read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "content": json.loads(raw)}


def artifact(path, digest):
    path = Path(path)
    require(path.is_absolute() and path.is_file(), "Missing absolute artifact: " + str(path))
    require(sha(path) == digest, "Artifact hash differs: " + str(path))
    return path


def frozen(root, filename, digest):
    root = Path(root)
    manifest = artifact(root / filename, digest)
    for name, value in read(manifest)["files"].items():
        artifact(root / name, value["sha256"] if isinstance(value, dict) else value)


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_pose(raw, video, video_sha):
    require(raw["schema"] == "h3_cpu_pose_v1", "Pose schema differs")
    require(raw["provenance"] == CONTRACT["pose_provenance"], "Pose model/code/runtime provenance differs")
    require(raw["joint_order"] == CONTRACT["joint_order"], "Joint order differs")
    require(raw["extraction"] == {"start": 0, "end": None, "stride": 1}, "Pose extraction differs")
    info = raw["video"]
    require(Path(info["path"]).resolve() == Path(video).resolve() and info["sha256"] == video_sha,
            "Pose belongs to a different video")
    require((info["fps"], info["container_frame_count"], info["width"], info["height"]) == (24, 158, 1152, 768),
            "Pose video geometry differs")
    require(len(raw["frames"]) == 158 and [r["frame"] for r in raw["frames"]] == list(range(158)),
            "Incomplete pose frames")
    for row in raw["frames"]:
        selected = row["selected_person"]
        require(selected is None or (type(selected) is int and 0 <= selected < len(row["persons"])),
                "Invalid selected-person index")
    # The numeric intake additionally verifies finite timestamps, coordinates and scores.
    return raw


def validate_manifest(records):
    expected = [(pair, method) for pair in CONTRACT["pair_order"] for method in CONTRACT["methods"]]
    require([(r["pair_id"], r["method"]) for r in records] == expected,
            "Generated manifest must retain all ten planned records in fixed order")


def source_pose(pair, source_manifest, source_protocol, metric_root, source_folder=None):
    action = pair.split("/")[1]
    require(source_manifest["status"] == "complete", "Five-source pose cache incomplete")
    require(source_manifest["protocol_sha256"] == CONTRACT["source_pose_protocol_sha256"],
            "Source cache protocol differs")
    require(source_manifest["code_freeze_sha256"] == CONTRACT["source_pose_freeze_sha256"],
            "Source cache code freeze differs")
    item = source_manifest["sources"][action]
    planned = source_protocol["sources"][action]
    require(item["status"] == "complete" and item["source_id"] == action, "Source identity differs")
    require(item["video_sha256"] == planned["video_sha256"], "Prepared source hash differs")
    video = artifact(item["remote_video_path"], planned["video_sha256"])
    provenance_path = artifact(Path(source_protocol["root_remote"]) / planned["input_provenance"],
                               planned["input_provenance_sha256"])
    provenance = read(provenance_path)
    official = next(r for r in read(Path(metric_root) / "SOURCE_INPUTS.json")["inputs"] if r["id"] == pair)
    require(provenance["official_pair"]["stable_id"] == pair and
            provenance["source_original_sha256"] == official["sha256"] and
            provenance["video_sha256"] == planned["video_sha256"] and
            provenance["input_to_original"] == [min(i // 3, 48) for i in range(158)] and
            provenance["evaluate_indices"] == CONTRACT["frame_indices"] and
            provenance["all158_decoded_frames_match_declared_source_exactly"] is True,
            "Prepared source mapping to official video differs")
    pose = artifact(item["remote_pose_path"], item["pose_sha256"])
    folder = Path(source_folder) / action if source_folder else pose.parent
    complete = read(artifact(folder / "COMPLETE.json", item["complete_sha256"]))
    require(complete["status"] == "complete" and complete["source_id"] == action and
            complete["code_freeze_sha256"] == CONTRACT["source_pose_freeze_sha256"],
            "Source extraction receipt differs")
    require({p.name for p in folder.iterdir()} == set(complete["files"]) | {"COMPLETE.json"},
            "Source extraction inventory differs")
    for name, digest in complete["files"].items():
        require(Path(name).name == name, "Nonlocal source inventory entry")
        artifact(folder / name, digest)
    provenance = read(artifact(folder / "PROVENANCE.json", item["provenance_sha256"]))
    require(provenance["source_id"] == action and provenance["pose_sha256"] == item["pose_sha256"] and
            provenance["video_sha256"] == item["video_sha256"] and
            provenance["input_provenance_sha256"] == planned["input_provenance_sha256"] and
            provenance["code_freeze_sha256"] == CONTRACT["source_pose_freeze_sha256"] and
            provenance["protocol_sha256"] == CONTRACT["source_pose_protocol_sha256"] and
            provenance["pose_provenance"] == CONTRACT["pose_provenance"],
            "Source provenance receipt differs")
    return validate_pose(read(pose), video, planned["video_sha256"]), item


def generated_pose(record, pair, method, metric_module):
    require(record["status"] == "complete" and record["pair_id"] == pair and record["method"] == method,
            "Paired generated pose is pending or mismatched")
    action = pair.split("/")[1]
    expected_run = (f"r49_source_{action}_seed2026101701_native" if method == "native"
                    else f"r50_source_{action}_seed2026101701_auto")
    metric_path = artifact(record["metric_inputs_path"], record["metric_inputs_sha256"])
    mapping_path = artifact(record["release49_mapping_path"], record["release49_mapping_sha256"])
    metric = read(metric_path)
    require(metric["run_id"] == expected_run and metric["official_pair_id"] == pair, "Wrong producer run")
    full = artifact(record["full158_path"], record["full158_sha256"])
    require(full.resolve() == Path(metric["full158_output"]).resolve() and
            record["full158_sha256"] == metric["full158_output_sha256"], "Generated pose parent differs")
    released = artifact(metric["edited49"], metric["edited49_sha256"])
    item = {"id": pair, "sha256": metric["edited49_sha256"], "generation_binding": {
        "metric_inputs": {"file": str(metric_path), "sha256": record["metric_inputs_sha256"]},
        "release_mapping": {"file": str(mapping_path), "sha256": record["release49_mapping_sha256"]}}}
    metric_module.validate_generated_binding(item, released)
    pose = artifact(record["pose_path"], record["pose_sha256"])
    artifact(record["extraction_complete_path"], record["extraction_complete_sha256"])
    artifact(record["provenance_path"], record["provenance_sha256"])
    return validate_pose(read(pose), full, record["full158_sha256"])


def main():
    parser = argparse.ArgumentParser()
    for name in ("generated-manifest", "source-manifest", "source-protocol", "numeric-root", "metric-root", "pair", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    require(args.pair in CONTRACT["pair_order"], "Pair outside fixed pilot")
    frozen(args.numeric_root, "FREEZE.json", CONTRACT["numeric_freeze_sha256"])
    frozen(args.metric_root, "RUNTIME_FREEZE.json", CONTRACT["metric_runtime_freeze_sha256"])
    artifact(Path(args.source_protocol).resolve(), CONTRACT["source_pose_protocol_sha256"])
    os.environ["OMP_NUM_THREADS"] = "2"
    os.environ["MKL_NUM_THREADS"] = "2"
    sys.path.insert(0, args.numeric_root)
    evaluator = import_file("public_frozen_pose_evaluator", Path(args.numeric_root) / "evaluate.py")
    tracker_contract = import_file("public_frozen_video_binding", Path(args.metric_root) / "run_tracks.py")
    snapshots = {"generated": snapshot(args.generated_manifest), "source": snapshot(args.source_manifest)}
    generated = snapshots["generated"]["content"]
    validate_manifest(generated["records"])
    generated_folder = Path(args.generated_manifest).resolve().parent
    frozen(generated_folder, "FREEZE.json", CONTRACT["generated_pose_freeze_sha256"])
    require(generated["code_freeze_sha256"] == CONTRACT["generated_pose_freeze_sha256"] and
            generated["protocol_sha256"] == CONTRACT["generated_pose_protocol_sha256"],
            "Generated sidecar manifest belongs to a different protocol/code")
    receipt_validator = import_file("public_generated_pose_receipt_validator", generated_folder / "manifest.py")
    source_folder = Path(args.source_manifest).resolve().parent
    frozen(source_folder, "FREEZE.json", CONTRACT["source_pose_freeze_sha256"])
    source, source_item = source_pose(args.pair, snapshots["source"]["content"], read(args.source_protocol),
                                      args.metric_root, source_folder)
    selected = {method: next(r for r in generated["records"] if r["pair_id"] == args.pair and r["method"] == method)
                for method in CONTRACT["methods"]}
    for record in selected.values():
        receipt_validator.verify_supplied_record(record)
    poses = {method: generated_pose(record, args.pair, method, tracker_contract) for method, record in selected.items()}
    started = time.monotonic()
    result = evaluator.evaluate(source, poses["native"], poses["automatic"])
    output = {"pair_id": args.pair, "status": "complete", "fixed_pair_denominator": 5,
              "result": result, "cpu_seconds": time.monotonic() - started,
              "source": source_item, "generated": selected,
              "contract_sha256": sha(HERE / "CONTRACT.json"), "runner_sha256": sha(__file__),
              "input_manifests": snapshots,
              "scope": CONTRACT["scope"]}
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x") as stream:
        json.dump(output, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"pair": args.pair, "output": str(destination), "sha256": sha(destination),
                      "cpu_seconds": output["cpu_seconds"]}))


if __name__ == "__main__":
    main()
