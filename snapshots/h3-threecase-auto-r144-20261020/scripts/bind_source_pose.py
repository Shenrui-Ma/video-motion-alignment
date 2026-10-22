"""Bind the independently audited source-only pose before sealing a case."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from prepare_cases import ROOT, sha, read, write


def bind(sid, pose, bounds, evidence):
    root = ROOT / "cases" / sid
    protocol = read(root / "configs/protocol.json")
    case = protocol["cases"][0]
    pose = Path(pose).resolve()
    evidence = Path(evidence).resolve()
    assert evidence.is_file() and pose.is_file()
    assert len(bounds) == 2 and 0 <= bounds[0] < bounds[1] <= 1
    assert not (root / "audit/ROOT_ONLINE_APPROVAL.json").exists(), "do not alter an approved run"
    assert not read(root / "configs/PARENT_CLOSURE.json").get("ready"), "already materialized"
    sys.path[:0] = [str(root / "scripts"), str(root / "extensions")]
    from H3AutomaticWindowRouter.geometry import Geometry
    from adult_selector import adult_only
    from pose_domain import validate_pose
    raw = validate_pose(pose, Geometry.from_case(case))
    assert raw["video"]["sha256"] == case["video_sha256"], "pose must cover actual input source"
    filtered, rejected = adult_only(raw, case["geometry"], bounds)
    write(root / "configs/source.raw.pose.json", raw)
    write(root / "configs/source.pose.json", filtered)
    case["source_pose_sha256"] = sha(root / "configs/source.pose.json")
    case["source_pose_status"] = "ACTUAL_SOURCE_FULL_FRAME_CPU_POSE_BOUND"
    protocol["person_selection"] = {
        "kind": "source-specified spatial selector",
        "selected_bbox_center_x_fraction": bounds,
        "selection": "retain original largest/IoU selected person if in bounds; else None",
        "status": "SOURCE_BOUND",
        "evidence": str(evidence), "evidence_sha256": sha(evidence),
        "content_boundary_filter": False,
    }
    protocol["preparation_status"] = "SOURCE_BOUND_PARENT_MATERIALIZATION_PENDING"
    write(root / "configs/protocol.json", protocol)
    science = read(root / "configs/scientific_contract.json")
    science["cases"] = protocol["cases"]
    write(root / "configs/scientific_contract.json", science)
    transport = root / "extensions/H3AutomaticWindowRouter/transport.py"
    write(transport, re.sub(r"^PROTOCOL_SHA=.*$", f"PROTOCOL_SHA={sha(root/'configs/protocol.json')!r}",
                           transport.read_text(), flags=re.M))
    inheritance = read(root / "audit/INHERITANCE.json")
    inheritance["metadata_lifecycle_adaptations"]["extensions/H3AutomaticWindowRouter/transport.py"]["sha256"] = sha(transport)
    write(root / "audit/INHERITANCE.json", inheritance)
    write(root / "audit/SOURCE_POSE_BINDING.json", {
        "source_video_sha256": case["video_sha256"], "input_pose_sha256": sha(pose),
        "raw_pose_sha256": sha(root / "configs/source.raw.pose.json"),
        "selected_pose_sha256": case["source_pose_sha256"], "sampled_frames": case["geometry"]["frames"],
        "valid_frames": case["valid_frame_count"], "bounds": bounds, "rejected_frames": rejected,
        "evidence_file": str(evidence), "evidence_sha256": sha(evidence),
        "original_confidence_only_policy": True, "content_boundary_filter": False,
    })
    subprocess.run([sys.executable, str(root / "scripts/preflight.py")], check=True)
    subprocess.run([sys.executable, str(root / "scripts/execution_gate.py"), "seal"], check=True)
    return {"source_id": sid, "protocol_sha256": sha(root / "configs/protocol.json"),
            "seal_sha256": sha(root / "deploy_manifest.json")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=("short_0358", "long_0039", "long_0059"))
    parser.add_argument("--pose", required=True)
    parser.add_argument("--bounds", nargs=2, required=True, type=float)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    print(json.dumps(bind(args.case, args.pose, args.bounds, args.evidence), indent=2))
