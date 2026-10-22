"""Configure the existing source-tracker path without any generated target."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, bound, read, require, verify_record, write, case_and_schedule
from prepare_dance_batch import copy, PARENT, AUDIT_SCRIPTS

MF = ROOT / "mf_preparation"


def prepare(sid):
    require(sid in ("firefly06", "sam07"), "Only the two frozen first-time sources")
    require(not (MF / "source_caches" / sid / "SOURCE_CACHE.json").exists(),
            "Source was already tracked")
    _, case, _ = case_and_schedule(sid, "native")
    source = ROOT / "mf_inputs" / sid
    inputs = read(source / "DANCE_INPUTS.json")
    require(inputs["targets"] == [] and inputs["source_cache"] is None,
            "Source-only preparation requires the frozen source domain")
    verify_record(case["media"]["source"])
    require(inputs["source_full_sha256"] == case["media"]["source"]["sha256"]
            and inputs["valid_frames"] == inputs["evaluation_frames"] == 141
            and inputs["evaluation_fps"] == 24
            and inputs["crop_xywh"] == case["geometry"]["crop_xywh"],
            "Source geometry changed")
    key = sid + "__source"
    package = MF / "host60_batches" / key
    require(not package.exists(), "Preserve the existing source batch")
    dest = package / "cases" / sid
    for name, digest in (("source_full.mp4", inputs["source_full_sha256"]),
                         ("source_score.mp4", inputs["source_score_sha256"]),
                         ("SOURCE_SELECTION.json", inputs["selection_sha256"])):
        require(bound(source / name)["sha256"] == digest, "Frozen input changed: " + name)
        copy(source / name, dest / name, hardlink=True)
    write(dest / "INPUTS.json", inputs)
    write(package / "configs/SOURCE_INPUTS_VERIFIED.json", {
        "schema": "r150-frozen-reference-only-mf-input-v1", "passed": True,
        "case": sid, "source": case["media"]["source"], "geometry": case["geometry"],
        "frozen_inputs": bound(source / "DANCE_INPUTS.json"),
        "scope": "Reference tracker only; no generated output or target score"})
    parent = read(PARENT / "SEAL.json")
    files = [p for p in parent["files"] if p.startswith("scripts/")]
    files += ["audit/" + p for p in AUDIT_SCRIPTS] + ["configs/ive_NUMERIC.json"]
    for rel in files:
        require(bound(PARENT / rel)["sha256"] == parent["files"][rel], "Parent changed")
        copy(PARENT / rel, package / rel)
    runner = package / "scripts/run_batch.py"
    old = "assert read(ROOT/'configs/BATCH_RELEASE.json')['passed']"
    new = "assert read(ROOT/'configs/SOURCE_INPUTS_VERIFIED.json')['passed']"
    text = runner.read_text()
    require(text.count(old) == 1, "Unexpected runner input gate")
    runner.write_text(text.replace(old, new))
    write(package / "configs/PLAN.json", {
        "groups": [sid], "jobs": [{"case": sid, "role": "source"}],
        "unique_targets": 0, "source_cache_count": 0, "new_source_trackers": 1})
    runtime = read(PARENT / "configs/RUNTIME.json")
    runtime["remote_root"] = str(Path(runtime["remote_root"]).parent / key)
    write(package / "configs/RUNTIME.json", runtime)
    write(package / "audit/REMOTE_REUSE_PLAN.json", read(PARENT / "audit/REMOTE_REUSE_PLAN.json"))
    (package / "runtime").mkdir()
    (package / "runtime/ive").symlink_to((PARENT / "runtime/ive").resolve(), target_is_directory=True)
    sealed = {str(p.relative_to(package)): bound(p)["sha256"]
              for top in ("scripts", "configs", "cases", "audit")
              for p in (package / top).rglob("*") if p.is_file()}
    write(package / "SEAL.json", {
        "schema": "r150-host60-reference-only-mf-v1", "final_inputs_bound": True,
        "files": sealed, "new_target_trackers": 0, "new_source_trackers": 1,
        "parent_seal": bound(PARENT / "SEAL.json")})
    write(package / "ADMIN_DIFF.json", {
        "parent": bound(PARENT / "SEAL.json"), "source_only": True,
        "runner_replacement": {"from": old, "to": new},
        "reason": "Root authorized the two frozen reference trackers before new Native outputs",
        "unchanged_numeric_scripts": {n: parent["files"]["scripts/" + n]
                                      for n in ("track.py", "score.py")}, "GPU_started": False})
    write(package / "ROOT_REVIEW_TEMPLATE.json", {
        "passed": False, "CPU_upload_authorized": False, "GPU_execution_authorized": False,
        "seal_sha256": bound(package / "SEAL.json")["sha256"], "gpu": runtime["gpu_uuid"],
        "execution_scope": "host60_single_tracker_only", "minimum_gpu_free_mib": 20480,
        "maximum_own_cards": 1, "prerequisite_release": None})
    print(key, bound(package / "SEAL.json")["sha256"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=("firefly06", "sam07"))
    prepare(parser.parse_args().case)
