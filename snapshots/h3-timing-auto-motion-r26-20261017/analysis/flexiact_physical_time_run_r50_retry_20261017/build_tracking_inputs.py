"""Prepare a fixed five-video official-metric input manifest from complete receipts."""
import argparse
import json
from pathlib import Path

from run_pair import CONTRACT, frozen, import_file, require, sha, snapshot, validate_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated-manifest", required=True)
    parser.add_argument("--method", choices=CONTRACT["methods"], required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    path = Path(args.generated_manifest).resolve()
    captured = snapshot(path)
    data = captured["content"]
    validate_manifest(data["records"])
    frozen(path.parent, "FREEZE.json", CONTRACT["generated_pose_freeze_sha256"])
    require(data["code_freeze_sha256"] == CONTRACT["generated_pose_freeze_sha256"] and
            data["protocol_sha256"] == CONTRACT["generated_pose_protocol_sha256"], "Wrong sidecar version")
    verifier = import_file("official_metric_pose_receipt_intake", path.parent / "manifest.py")
    inputs = []
    for pair in CONTRACT["pair_order"]:
        record = next(r for r in data["records"] if r["pair_id"] == pair and r["method"] == args.method)
        verifier.verify_supplied_record(record)
        metric = json.loads(Path(record["metric_inputs_path"]).read_text())
        inputs.append({"id": pair, "method": args.method, "role": "generated", "file": metric["edited49"],
                       "sha256": metric["edited49_sha256"], "generation_frame_indices": CONTRACT["frame_indices"],
                       "generation_binding": {
                           "metric_inputs": {"file": record["metric_inputs_path"], "sha256": record["metric_inputs_sha256"]},
                           "release_mapping": {"file": record["release49_mapping_path"], "sha256": record["release49_mapping_sha256"]}}})
    result = {"inputs": inputs, "fixed_pair_denominator": 5, "method": args.method,
              "generated_pose_manifest_snapshot": captured, "builder_sha256": sha(__file__)}
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"output": str(destination), "sha256": sha(destination), "count": len(inputs)}))


if __name__ == "__main__":
    main()
