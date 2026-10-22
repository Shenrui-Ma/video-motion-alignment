"""Bind a completed producer result to the matched R151 evaluation controls."""
import argparse
import hashlib
import json
from pathlib import Path

from prepare import ROOT, bind, read

PRODUCER = ROOT.parent / "h3-reference-feedback-r151-20261021"


def import_result(source_id, role, gate_path, video_path):
    if role not in ("reverse", "combined"):
        raise ValueError("Only new R151 arms may be imported.")
    manifest = read(ROOT / "EVALUATION_MANIFEST.json")
    case = next(c for c in manifest["cases"] if c["source_id"] == source_id)
    handoff = next(c for c in read(PRODUCER / "HANDOFF.json")["cases"] if c["source_id"] == source_id)
    recipe = next(c for c in read(PRODUCER / "CODE_FEASIBILITY.json")["cases"] if c["source_id"] == source_id)
    gate = read(gate_path)
    producer_role = "reverse_only" if role == "reverse" else "combined"
    alpha = int(role == "combined")
    expected = {
        "schema": "r151-bidirectional-job-gate-v1", "passed": True,
        "run_id": f"r151_{source_id}_seed{case['seed']}_{producer_role}",
        "role": producer_role, "alpha": alpha, "beta": 1.0,
        "producer_seal_sha256": handoff["seal_sha256"],
        "NFE": 20, "Euler_updates": 20, "routed_blocks": 450,
        "forward_routed_calls": alpha * 450, "reverse_routed_calls": 450,
        "actual_routed_steps_zero_based": list(range(9)),
        "phase_displacement": 0, "physical_query_window": recipe["physical_window"],
        "noise_sha256": recipe["noise_file_sha256"],
        "valid_frames": case["geometry"]["valid_frames"],
        "evaluation_crop_xywh": case["geometry"]["crop_xywh"],
    }
    for key, value in expected.items():
        if gate.get(key) != value:
            raise ValueError(f"Unexpected result field {key}: {gate.get(key)}")
    for relative, digest in gate["binding_artifacts"].items():
        path = Path(handoff["local_root"]) / relative
        if bind(path)["sha256"] != digest:
            raise ValueError(f"Actual execution evidence changed: {relative}")
    video = bind(video_path)
    if video["sha256"] != gate["video"]["sha256"]:
        raise ValueError("Transferred video differs from producer output.")
    props = gate["video"]["properties"]
    geometry = case["geometry"]
    if (props["width"], props["height"], int(props["nb_read_frames"]), props["avg_frame_rate"]) != (
            geometry["width"], geometry["height"], geometry["sampled_frames"], "24/1"):
        raise ValueError("Wrong generated geometry.")
    result = {
        "source_id": source_id, "role": role, "video": video,
        "execution_verified": True, "execution_evidence": bind(gate_path),
        "sampled_frames": geometry["sampled_frames"], "valid_frames": geometry["valid_frames"],
        "sampler_seconds": gate["sampler_timing"]["sampler_wall_seconds"],
        "job_seconds": gate["job_wall_seconds"],
        "batch_release_status": "pending_separate_receipt",
    }
    destination = ROOT / "results" / source_id / f"{role}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and read(destination) != result:
        raise ValueError("Existing result differs; preserve it and inspect before importing a replacement.")
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--role", choices=("reverse", "combined"), required=True)
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    args = parser.parse_args()
    import_result(args.case, args.role, args.gate, args.video)
