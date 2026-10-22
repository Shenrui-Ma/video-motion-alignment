"""One completed video per MF package; producer lifetime remains separate."""
import argparse
import ast
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, read, write, bound, require, verify_record, case_and_schedule
from ingest import validate
from finalize_batch import verify_batch_record
from prepare_dance_inputs import source_inputs, views, CASES as DANCES
from prepare_dance_batch import copy, PARENT, AUDIT_SCRIPTS
import prepare_batch

MF = ROOT / "mf_preparation"


def validate_completed_target(case, role):
    sid = case["source_id"]
    presentation = ROOT / "review" / sid / role / "PRESENTATION.json"
    proof = read(presentation)["validated_execution"]
    _, _, schedule = case_and_schedule(sid, role)
    validate(case, schedule, proof["video"]["file"], proof["gate"]["file"],
             proof["binding"]["file"])
    require(read(proof["gate"]["file"]) == proof["run_record"],
            "Presentation does not bind the actual job")
    batch = ROOT / "actual" / sid / "BATCH_RELEASE.json"
    if batch.exists():
        verify_batch_record(batch, case, read(proof["binding"]["file"]), proof["run_record"])
    return proof["video"], proof["run_id"], {
        "presentation": bound(presentation), "gate": proof["gate"],
        "binding": proof["binding"], "video": proof["video"],
        "generation_batch_release": bound(batch) if batch.exists() else None,
        "generation_batch_release_pending": not batch.exists()}


def reuse_created_source(sid, inputs, dest):
    cache_file = MF / "source_caches" / sid / "SOURCE_CACHE.json"
    if not cache_file.exists():
        return
    cache = read(cache_file)
    for key in ("inputs", "report", "tracks", "MF_release"):
        verify_record(cache[key])
    old, report = read(cache["inputs"]["file"]), read(cache["report"]["file"])
    release = read(cache["MF_release"]["file"])
    require(release["passed"] and release["exact_processes_absent"]
            and release["exact_CUDA_allocations_absent"], "Source tracker not released")
    for key in ("source_full_sha256", "source_score_sha256", "source_frame_md5",
                "valid_frames", "evaluation_frames", "evaluation_fps",
                "crop_xywh", "selection_sha256", "canonical_id"):
        require(old[key] == inputs[key], "Previously tracked source domain differs: " + key)
    require(report["passed"] and report["tracks_sha256"] == cache["tracks"]["sha256"]
            and report["decoded_frame_md5"] == inputs["source_frame_md5"],
            "Source track report differs")
    for key, name in (("report", "REPORT.json"), ("tracks", "tracks.npz")):
        copy(cache[key]["file"], dest / "tracks/source" / name, hardlink=True)
    inputs["source_cache"] = {"report_sha256": cache["report"]["sha256"],
                             "tracks_sha256": cache["tracks"]["sha256"]}


def prepare(sid, role):
    require(not (ROOT / "scores" / sid / (role + ".json")).exists(),
            "Target was already scored")
    _, case, _ = case_and_schedule(sid, role)
    require(role in case.get("expected_output_roles", ("early", "late", "split", "global_weak"))
            or (sid == "musk05" and role == "native"), "Unregistered target role")
    historical = sid == "musk05" and role == "native"
    if historical:
        # This exact restoration proof was produced before any new Musk generation.
        evidence_file = ROOT / "mf_inputs/musk05/native/EVIDENCE.json"
        evidence = read(evidence_file)
        for key in ("historical_manifest", "condition_recovery"):
            verify_record(evidence[key])
        recovery = read(evidence["condition_recovery"]["file"])
        require(recovery["passed"] and recovery["same_historical_embedding"] is True
                and recovery["requires_shared_cache_native"] is False
                and recovery["original_embedding_signature"] == recovery["actual_embedding_signature"],
                "Historical Musk Native conditioning differs")
        video = case["media"]["native"]
        verify_record(video)
        run_id = Path(video["file"]).stem
        evidence = dict(evidence, video=video, historical_media=True,
                        generation_batch_release_pending=True, generation_batch_release=None)
    else:
        video, run_id, evidence = validate_completed_target(case, role)
    key = sid + "__" + role
    package = MF / "host60_batches" / key
    require(not package.exists(), "Preserve already prepared/scored stream package")
    dest = package / "cases" / sid
    if sid in DANCES:
        inputs = source_inputs(case, dest)
        reuse_created_source(sid, inputs, dest)
    else:
        inputs = prepare_batch.packager.attach_source(case, package, {})
    views.link(video["file"], dest / role / "full.mp4")
    pixels = views.score_view(dest / role / "full.mp4", dest / role / "score.mp4", case["geometry"])
    inputs["targets"] = [{
        "role": role, "full_file": role + "/full.mp4", "full_sha256": video["sha256"],
        "score_file": role + "/score.mp4",
        "score_sha256": bound(dest / role / "score.mp4")["sha256"],
        "score_frame_md5": pixels, "evaluation_indices": list(range(case["geometry"]["valid_frames"])),
        "inventory_bindings": [{"id": run_id, "field": role}], "historical_media": historical}]
    write(dest / "INPUTS.json", inputs)
    write(package / "configs/GENERATION_INPUTS_VERIFIED.json", {
        "schema": "r150-completed-video-stream-input-v1", "passed": True,
        "case": sid, "role": role, "video": video, "run_id": run_id,
        "geometry": case["geometry"], "proof": evidence,
        "generation_batch_release_pending": evidence["generation_batch_release_pending"],
        "scope": "Completed validated video; this does not assert that its producer batch exited"})
    parent = read(PARENT / "SEAL.json")
    scripts = [p for p in parent["files"] if p.startswith("scripts/")]
    scripts += ["audit/" + x for x in AUDIT_SCRIPTS] + ["configs/ive_NUMERIC.json"]
    for rel in scripts:
        require(bound(PARENT / rel)["sha256"] == parent["files"][rel], "Parent changed: " + rel)
        copy(PARENT / rel, package / rel)
    runner = package / "scripts/run_batch.py"
    old = "assert read(ROOT/'configs/BATCH_RELEASE.json')['passed']"
    new = "assert read(ROOT/'configs/GENERATION_INPUTS_VERIFIED.json')['passed']"
    text = runner.read_text()
    require(text.count(old) == 1, "Unexpected administrative admission")
    runner.write_text(text.replace(old, new))
    ast.parse(runner.read_text())
    roles = ([] if inputs["source_cache"] else ["source"]) + [role]
    write(package / "configs/PLAN.json", {
        "groups": [sid], "jobs": [{"case": sid, "role": r} for r in roles],
        "unique_targets": 1, "source_cache_count": int(bool(inputs["source_cache"])),
        "new_source_trackers": int(not inputs["source_cache"])})
    runtime = read(PARENT / "configs/RUNTIME.json")
    runtime["remote_root"] = str(Path(runtime["remote_root"]).parent / key)
    write(package / "configs/RUNTIME.json", runtime)
    write(package / "audit/REMOTE_REUSE_PLAN.json", read(PARENT / "audit/REMOTE_REUSE_PLAN.json"))
    (package / "runtime").mkdir()
    (package / "runtime/ive").symlink_to((PARENT / "runtime/ive").resolve(), target_is_directory=True)
    files = {str(p.relative_to(package)): bound(p)["sha256"]
             for top in ("scripts", "configs", "cases", "audit")
             for p in (package / top).rglob("*") if p.is_file()}
    write(package / "SEAL.json", {"schema": "r150-host60-single-completed-video-mf-v1",
          "final_inputs_bound": True, "files": files, "new_target_trackers": 1,
          "new_source_trackers": int(not inputs["source_cache"]),
          "parent_seal": bound(PARENT / "SEAL.json")})
    write(package / "ADMIN_DIFF.json", {
        "parent": bound(PARENT / "SEAL.json"), "completed_video_stream": True,
        "runner_replacement": {"from": old, "to": new},
        "reason": "Root authorized scoring each completed video while its independent producer continues",
        "unchanged_numeric_scripts": {n: parent["files"]["scripts/" + n] for n in ("track.py", "score.py")},
        "generation_batch_release_pending": evidence["generation_batch_release_pending"],
        "GPU_started": False})
    write(package / "ROOT_REVIEW_TEMPLATE.json", {
        "passed": False, "CPU_upload_authorized": False, "GPU_execution_authorized": False,
        "seal_sha256": bound(package / "SEAL.json")["sha256"], "gpu": runtime["gpu_uuid"],
        "execution_scope": "host60_single_tracker_only", "minimum_gpu_free_mib": 20480,
        "maximum_own_cards": 1, "prerequisite_release": None})
    print(key, bound(package / "SEAL.json")["sha256"], "jobs", len(roles))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--role", required=True)
    a = p.parse_args()
    prepare(a.case, a.role)
