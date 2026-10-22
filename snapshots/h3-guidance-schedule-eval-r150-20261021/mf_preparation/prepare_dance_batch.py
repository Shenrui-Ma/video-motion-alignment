"""Seal six dance targets over the successful host60 MF runtime, after release."""
import argparse
import ast
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import bound, read, require, verify_record, write, case_and_schedule
from prepare_dance_inputs import CASES, ROLES, prepare as prepare_inputs

MF = ROOT / "mf_preparation"
PARENT = MF / "host60_batches/long_0039"
AUDIT_SCRIPTS = ("collect.py", "final_release.py", "verify_inputs.py",
                 "materialize_existing.py")


def plan_for(sid, inputs):
    targets = inputs["targets"]
    require(len(targets) == len(ROLES) and
            [t["role"] for t in targets] == list(ROLES),
            "All six ordered targets must exist before sealing")
    require(inputs["valid_frames"] == inputs["evaluation_frames"] == 141
            and inputs["evaluation_fps"] == 24
            and inputs["crop_xywh"] == [0, 0, 1312, 736],
            "Dance scoring domain changed")
    reuse = bool(inputs["source_cache"])
    require(reuse == (sid == "musk05"), "Unexpected source-cache policy")
    roles = ([] if reuse else ["source"]) + list(ROLES)
    return {"groups": [sid], "jobs": [{"case": sid, "role": r} for r in roles],
            "unique_targets": len(ROLES), "source_cache_count": int(reuse),
            "new_source_trackers": int(not reuse)}


def copy(source, target, hardlink=False):
    source, target = Path(source), Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    require(not target.exists(), "Refuse to overwrite " + str(target))
    os.link(source, target) if hardlink else shutil.copyfile(source, target)
    require(bound(source)["sha256"] == bound(target)["sha256"], "Copy differs")


def prepare(sid):
    require(sid in CASES, "Unknown dance case")
    package = MF / "host60_batches" / sid
    require(not package.exists(), "Preserve the existing package")
    batch = ROOT / "actual" / sid / "BATCH_RELEASE.json"
    require(batch.is_file() and read(batch).get("passed") is True,
            "Actual generation release required")
    # This rechecks each actual gate, producer binding, composite release,
    # generated MP4, pixel domain, and historical Musk conditioning equality.
    prepare_inputs(sid)
    source = ROOT / "mf_inputs" / sid
    inputs = read(source / "DANCE_INPUTS.json")
    plan = plan_for(sid, inputs)
    _, case, _ = case_and_schedule(sid, "early")
    require(inputs["source_full_sha256"] == case["media"]["source"]["sha256"],
            "Source differs from the evaluation manifest")
    parent_seal = read(PARENT / "SEAL.json")
    scripts = [rel for rel in parent_seal["files"] if rel.startswith("scripts/")]
    scripts += ["audit/" + name for name in AUDIT_SCRIPTS]
    scripts += ["configs/ive_NUMERIC.json"]
    for rel in scripts:
        require(bound(PARENT / rel)["sha256"] == parent_seal["files"][rel],
                "Successful parent script changed: " + rel)
        copy(PARENT / rel, package / rel)
        if rel.endswith(".py"):
            ast.parse((package / rel).read_text())
    case_dest = package / "cases" / sid
    for rel in ("source_full.mp4", "source_score.mp4"):
        copy(source / rel, case_dest / rel, hardlink=True)
    if inputs["source_cache"]:
        for name in ("REPORT.json", "tracks.npz"):
            copy(source / "tracks/source" / name, case_dest / "tracks/source" / name,
                 hardlink=True)
    for item in inputs["targets"]:
        for key in ("full_file", "score_file"):
            copy(source / item[key], case_dest / item[key], hardlink=True)
        copy(source / item["role"] / "EVIDENCE.json",
             package / "configs/evidence" / item["role"] / "EVIDENCE.json")
    write(case_dest / "INPUTS.json", inputs)
    copy(source / "SOURCE_BINDING.json", package / "configs/evidence/SOURCE_BINDING.json")
    copy(batch, package / "configs/BATCH_RELEASE.json")
    write(package / "configs/PLAN.json", plan)
    runtime = read(PARENT / "configs/RUNTIME.json")
    runtime["remote_root"] = str(Path(runtime["remote_root"]).parent / sid)
    write(package / "configs/RUNTIME.json", runtime)
    reuse = read(PARENT / "audit/REMOTE_REUSE_PLAN.json")
    require(set(reuse) == {"runtime/ive"}, "Unexpected parent reuse mapping")
    write(package / "audit/REMOTE_REUSE_PLAN.json", reuse)
    (package / "runtime").mkdir()
    (package / "runtime/ive").symlink_to((PARENT / "runtime/ive").resolve(),
                                       target_is_directory=True)
    files = {str(p.relative_to(package)): bound(p)["sha256"]
             for top in ("scripts", "configs", "cases", "audit")
             for p in (package / top).rglob("*") if p.is_file()}
    write(package / "SEAL.json", {
        "schema": "r150-host60-dance-six-targets-v1", "final_inputs_bound": True,
        "files": files, "new_target_trackers": len(ROLES),
        "new_source_trackers": plan["new_source_trackers"],
        "parent_seal": bound(PARENT / "SEAL.json"),
        "batch_release_sha256": bound(batch)["sha256"]})
    write(package / "ADMIN_DIFF.json", {
        "parent": bound(PARENT / "SEAL.json"), "case": sid,
        "changed": ["Six completed dance target inputs",
                    "One source tracker first, only where no verified source cache exists",
                    "Case-specific remote root and actual generation release"],
        "scripts_byte_identical": {rel: parent_seal["files"][rel] for rel in scripts},
        "official_numerics_unchanged": True, "GPU_started": False})
    write(package / "ROOT_REVIEW_TEMPLATE.json", {
        "passed": False, "CPU_upload_authorized": False,
        "GPU_execution_authorized": False,
        "seal_sha256": bound(package / "SEAL.json")["sha256"],
        "gpu": runtime["gpu_uuid"], "execution_scope": "host60_single_tracker_only",
        "minimum_gpu_free_mib": 20480, "maximum_own_cards": 1,
        "prerequisite_release": None})
    write(package / "CPU_PREPARATION.json", {
        "passed": True, "targets": len(ROLES),
        "new_source_trackers": plan["new_source_trackers"],
        "total_trackers": len(plan["jobs"]),
        "generation_release": bound(batch), "seal": bound(package / "SEAL.json"),
        "target_CPU_validation_pending": True, "GPU_started": False})
    print(json.dumps({"package": str(package), "seal": bound(package / "SEAL.json"),
                      "trackers": len(plan["jobs"])}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=CASES)
    prepare(parser.parse_args().case)
