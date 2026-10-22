"""CPU-only R149 batch manifests over the already verified R148 MF runtime."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import sys

ROOT = Path(__file__).resolve().parent
EVAL = ROOT.parent
sys.path.insert(0, str(EVAL))
from common import PREVIOUS, bound, read, write, require, verify_record
from finalize_batch import verify_batch_record, batch_evidence_records
from ingest import validate_job

BASE = PREVIOUS / "mf_preparation"
REMOTE_BASE = read(BASE / "configs/RUNTIME.json")["remote_root"]
REMOTE = "/data4/researcher/h3_runs/guidance_schedule_mf_r149_20261020"
ARMS = ("early", "late", "split", "global_weak")
AUDIT_REUSE = ("collect.py", "final_release.py", "materialize_existing.py", "verify_inputs.py")


def same_copy(source, dest, hardlink=False):
    source, dest = Path(source), Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        if hardlink:
            os.link(source, dest)
        else:
            shutil.copyfile(source, dest)
    require(bound(source)["sha256"] == bound(dest)["sha256"], "Existing destination differs: " + str(dest))


def attach_source(case, package, reuse):
    sid, g, cache = case["source_id"], case["geometry"], case["MF_source_cache"]
    old = read(cache["historical_inputs"]["file"])
    require(old["source_full_sha256"] == case["media"]["source"]["sha256"] and
            old["valid_frames"] == old["evaluation_frames"] == g["valid_frames"] and
            old["evaluation_fps"] == g["fps"] and old["crop_xywh"] == g["crop_xywh"],
            "Historical MF source domain differs")
    source_dir = Path(cache["historical_inputs"]["file"]).parent
    for filename, key in (("source_full.mp4", "source_full_sha256"),
                          ("source_score.mp4", "source_score_sha256")):
        require(bound(source_dir / filename)["sha256"] == old[key], "Historical source media changed")
        relative = f"cases/{sid}/{filename}"
        same_copy(source_dir / filename, package / relative, hardlink=True)
        reuse[relative] = REMOTE_BASE + f"/cases/{sid}/{filename}"
    for key, filename in (("report", "REPORT.json"), ("tracks", "tracks.npz")):
        verify_record(cache[key])
        relative = f"cases/{sid}/tracks/source/{filename}"
        same_copy(cache[key]["file"], package / relative, hardlink=True)
        reuse[relative] = cache["remote_report" if key == "report" else "remote_tracks"]
    report = read(cache["report"]["file"])
    require(report["passed"] and report["effective_frame_count"] == g["valid_frames"] and
            report["decoded_frame_md5"] == old["source_frame_md5"] and
            report["selection_sha256"] == old["selection_sha256"] and
            report["checkpoint_sha256"] == cache["checkpoint_sha256"] and
            report["official_commit"] == cache["official_commit"], "Source track cache identity differs")
    result = {k: v for k, v in old.items() if k != "targets"}
    result.update(schema="r149-official-mf-inputs-v1",
        source_cache={"report_sha256": cache["report"]["sha256"], "tracks_sha256": cache["tracks"]["sha256"]},
        targets=[])
    if sid == "05_real_megumi_v":
        result["dataset_scope"] = "Custom Sam task; uses the unchanged IVEBench official MF implementation."
    return result


def reuse_tools(package):
    files = {}
    base_seal = read(BASE / "SEAL.json")["files"]
    for source in sorted((BASE / "scripts").glob("*.py")):
        rel = str(source.relative_to(BASE))
        require(bound(source)["sha256"] == base_seal[rel], "Historical execution source changed")
        same_copy(source, package / rel)
        files[rel] = bound(source)["sha256"]
    for name in AUDIT_REUSE:
        source, rel = BASE / "audit" / name, "audit/" + name
        require(bound(source)["sha256"] == base_seal[rel], "Historical audit source changed")
        if name == "final_release.py":
            # The task-specific release assertions are unchanged. Only the host-wide
            # summary becomes unknown when non-target GPUs cannot be queried.
            adapter = ROOT / "admin/final_release.py"
            dest = package / rel
            require(not dest.exists() or bound(dest)["sha256"] in
                    (bound(source)["sha256"], bound(adapter)["sha256"]),
                    "Unexpected final release adapter")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(adapter.read_bytes())
            continue
        same_copy(source, package / rel)
        files[rel] = bound(source)["sha256"]
    same_copy(BASE / "configs/ive_NUMERIC.json", package / "configs/ive_NUMERIC.json")
    runtime = package / "runtime"
    if not runtime.exists():
        runtime.symlink_to(BASE / "runtime", target_is_directory=True)
    require(runtime.resolve() == (BASE / "runtime").resolve(), "Unexpected local numerical runtime")
    return files


def make_upload_script(package, remote):
    # CPU deployment only; its two explicit shell operations attach existing data and check it.
    content = """#!/bin/sh
set -eu
MF_PACKAGE=__LOCAL__
MF_REMOTE=__REMOTE__
python3 - "$MF_PACKAGE" <<'CHECK'
import json,hashlib,sys
from pathlib import Path
p=Path(sys.argv[1]);h=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
s=json.loads((p/'SEAL.json').read_text());r=json.loads((p/'ROOT_REVIEW.json').read_text())
assert s['final_inputs_bound'] and r['passed'] and r.get('CPU_upload_authorized', r.get('GPU_execution_authorized', False))
assert r['seal_sha256']==h(p/'SEAL.json')
assert r['gpu']==json.loads((p/'configs/RUNTIME.json').read_text())['gpu']
for rel,want in s['files'].items(): assert h(p/rel)==want,rel
files=(p/'audit/DEPLOY_FILES.txt').read_text().splitlines()
assert len(files)==len(set(files))
assert all(not Path(x).is_absolute() and '..' not in Path(x).parts and not x.startswith('runtime/') for x in files)
print({'upload_files':len(files)+1,'upload_bytes':sum((p/f).stat().st_size for f in files)+(p/'ROOT_REVIEW.json').stat().st_size})
CHECK
ssh H3_SERVER_B "mkdir -p '$MF_REMOTE'"
rsync -a --files-from="$MF_PACKAGE/audit/DEPLOY_FILES.txt" "$MF_PACKAGE/" "H3_SERVER_B:$MF_REMOTE/"
rsync -a "$MF_PACKAGE/ROOT_REVIEW.json" "H3_SERVER_B:$MF_REMOTE/ROOT_REVIEW.json"
ssh H3_SERVER_B "cd '$MF_REMOTE' && CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /data3/researcher/ComfyUI/.venv/bin/python audit/materialize_existing.py && CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /data3/researcher/ComfyUI/.venv/bin/python audit/verify_inputs.py"
"""
    (package / "audit/UPLOAD_AFTER_REVIEW.sh").write_text(
        content.replace("__LOCAL__", shlex.quote(str(package))).replace("__REMOTE__", shlex.quote(remote)))


def prepare(sid, finalize=False, gpu=None, peer_roots=(), existing_services=None, remote_full_map=None):
    manifest = read(EVAL / "EVALUATION_MANIFEST.json")
    case = next(c for c in manifest["cases"] if c["source_id"] == sid)
    package = ROOT / "batches" / sid
    require(not (package / "SEAL.json").exists(), "Frozen batch cannot be overwritten")
    if finalize:
        require(all((EVAL / "mf_inputs" / sid / arm / "INPUTS.json").is_file() for arm in ARMS)
                and (EVAL / "actual" / sid / "BATCH_RELEASE.json").is_file(),
                "All four actual outputs and release receipts are required")
        require(gpu and gpu.startswith("GPU-") and existing_services,
                "Root-selected GPU and current service policy required")
    package.mkdir(parents=True, exist_ok=True)
    byte_exact = reuse_tools(package)
    reuse = {"runtime": REMOTE_BASE + "/runtime"}
    inputs = attach_source(case, package, reuse)
    runtime_bindings, ready, pending = [], [], []
    map_override = read(remote_full_map) if remote_full_map else {}
    for arm in ARMS:
        input_path = EVAL / "mf_inputs" / sid / arm / "INPUTS.json"
        if not input_path.exists():
            pending.append(arm)
            continue
        item = read(input_path)
        verify_record(item["presentation"])
        pres = read(item["presentation"]["file"])
        proof = pres["validated_execution"]
        for name in ("gate", "binding"):
            verify_record(proof[name])
        require(read(proof["gate"]["file"]) == proof["run_record"],
                "Stored per-job record differs from the actual gate")
        binding = read(proof["binding"]["file"])
        schedule = dict(manifest["schedules"][arm], id=arm)
        validate_job(case, schedule, binding, proof["run_record"])
        verify_record(item["batch_release"])
        verify_batch_record(item["batch_release"]["file"], case, binding, proof["run_record"])
        for record in (item["full_video"], item["score_video"], item["presentation"]):
            verify_record(record)
        require(item["role"] == arm and item["run_id"] == binding["run_id"] and
                item["full_video"]["sha256"] == proof["run_record"]["video"]["sha256"] and
                item["valid_frames"] == case["geometry"]["valid_frames"] and
                item["fps"] == case["geometry"]["fps"] and item["crop_xywh"] == case["geometry"]["crop_xywh"] and
                len(item["frame_md5"]) == item["valid_frames"] and
                item["source_cache"] == case["MF_source_cache"], "Target MF domain differs")
        for record, filename in ((item["full_video"], "full.mp4"), (item["score_video"], "score.mp4")):
            same_copy(record["file"], package / "cases" / sid / arm / filename, hardlink=True)
        # Cabin output is already on .41. Sam output is uploaded once, unless a verified
        # direct .9->.41 copy has been supplied explicitly as a map.
        relative = f"cases/{sid}/{arm}/full.mp4"
        if binding["host"] == "H3_SERVER_B":
            reuse[relative] = proof["run_record"]["video"]["file"]
        elif arm in map_override:
            entry = map_override[arm]
            require(entry["sha256"] == item["full_video"]["sha256"] and
                    entry["file"].startswith("/data4/researcher/h3_runs/") and
                    ".." not in Path(entry["file"]).parts, "Transferred full-video mapping differs")
            reuse[relative] = entry["file"]
        evidence = package / "configs/evidence" / sid / arm
        same_copy(input_path, evidence / "MF_INPUTS.json")
        for name in ("gate", "binding"):
            same_copy(proof[name]["file"], evidence / (name + ".json"))
        inputs["targets"].append({
            "role": arm, "full_file": arm + "/full.mp4", "full_sha256": item["full_video"]["sha256"],
            "score_file": arm + "/score.mp4", "score_sha256": item["score_video"]["sha256"],
            "score_frame_md5": item["frame_md5"], "evaluation_indices": list(range(item["valid_frames"])),
            "inventory_bindings": [{"id": binding["run_id"], "field": arm}],
            "new_generation_only": True})
        runtime_bindings.append(bound(proof["binding"]["file"]))
        ready.append(arm)
    plan = {"groups": [sid], "jobs": [{"case": sid, "role": arm} for arm in ARMS],
            "unique_targets": 4, "source_cache_count": 1, "new_source_trackers": 0,
            "status": "FINAL_READY" if finalize else "CPU_PREPARATION_PENDING_OUTPUTS", "pending_inputs": pending}
    write(package / f"cases/{sid}/INPUTS.json", inputs)
    write(package / "configs/PLAN.json", plan)
    remote = REMOTE + "/" + sid
    runtime = read(BASE / "configs/RUNTIME.json")
    runtime.update(remote_root=remote, gpu=gpu, peer_roots=list(peer_roots), status="ROOT_REVIEW_REQUIRED")
    write(package / "configs/RUNTIME.json", runtime)
    write(package / "audit/REMOTE_REUSE_PLAN.json", reuse)
    write(package / "ADMIN_DIFF.json", {"baseline": bound(BASE / "SEAL.json"),
        "byte_exact_execution_and_cleanup": byte_exact,
        "administrative_final_release": {"baseline": bound(BASE / "audit/final_release.py"),
                                        "adapter": bound(package / "audit/final_release.py"),
                                        "change": "Host-wide CUDA absence is null when other GPU allocations are unqueryable; bind excluded rows. Exact task PID release assertions unchanged."},
        "changed": ["R149 per-case four-target input manifests", "explicit GPU/peer/current service identity bindings",
                    "truthful host-wide unknown CUDA summary for non-target unavailable GPUs"],
        "unchanged": ["official numerical implementation", "checkpoint", "tracker settings", "MF formula",
                      "target GPU/cgroup capacity policy", "exact tracker process release"],
        "dataset_note": "Sam is a custom example scored by the same official MF implementation."})
    make_upload_script(package, remote)
    if finalize:
        require(not pending and len(inputs["targets"]) == 4, "All four actual outputs and release receipts are required")
        require(gpu and gpu.startswith("GPU-") and existing_services, "Root-selected GPU and current service policy required")
        require(len(peer_roots) <= 1 and all(p.startswith("/data4/researcher/h3_runs/") and
                ".." not in Path(p).parts for p in peer_roots), "Invalid peer binding")
        services = read(existing_services)
        require(isinstance(services["processes"], list) and
                services["max_owned_active_gpus_including_selected"] <= 2, "Current read-only service policy required")
        write(package / "configs/EXISTING_SERVICES.json", services)
        batch_path = EVAL / "actual" / sid / "BATCH_RELEASE.json"
        batch = read(batch_path)
        for name, evidence in batch_evidence_records(batch).items():
            same_copy(evidence["file"], package / "configs/evidence" / sid / (name + ".json"))
        if batch["schema"] == "r149-evaluation-composite-release-v1":
            same_copy(batch_path, package / "configs/evidence" / sid / "COMPOSITE_RELEASE.json")
        files = {}
        for top in ("scripts", "configs", "cases"):
            for path in (package / top).rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts:
                    files[str(path.relative_to(package))] = bound(path)["sha256"]
        for rel, digest in read(BASE / "SEAL.json")["files"].items():
            if rel.startswith("runtime/"):
                require(bound(package / rel)["sha256"] == digest, "Historical numerical runtime changed")
                files[rel] = digest
        for name in AUDIT_REUSE:
            files["audit/" + name] = bound(package / "audit" / name)["sha256"]
        files["ADMIN_DIFF.json"] = bound(package / "ADMIN_DIFF.json")["sha256"]
        write(package / "SEAL.json", {"schema": "r149-official-mf-case-batch-v1",
                                     "final_inputs_bound": True, "files": files})
        uploads = [rel for rel in files if not rel.startswith("runtime/") and rel not in reuse]
        uploads += ["SEAL.json", "audit/REMOTE_REUSE_PLAN.json"]
        (package / "audit/DEPLOY_FILES.txt").write_text("\n".join(uploads) + "\n")
        upload_bytes = sum((package / rel).stat().st_size for rel in uploads)
    else:
        uploads, upload_bytes = [], None
    require("torch" not in sys.modules, "CPU preparation must not import a model")
    result = {"passed": True, "source_id": sid, "batch": str(package), "remote_root": remote,
        "planned_trackers": 4, "new_source_trackers": 0, "ready": ready, "pending": pending,
        "final_inputs_bound": finalize, "GPU_started": False, "network_operations": 0,
        "byte_exact_execution_files": len(byte_exact), "source_cache": case["MF_source_cache"],
        "upload_files": len(uploads), "upload_bytes_excluding_root_review": upload_bytes,
        "reuse_entries": reuse, "actual_runtime_bindings": runtime_bindings}
    write(package / "audit/CPU_PREPARATION.json", result)
    print(json.dumps({k: result[k] for k in ("source_id", "planned_trackers", "new_source_trackers", "ready", "pending", "final_inputs_bound")}))
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--case", choices=tuple(c["source_id"] for c in read(EVAL / "EVALUATION_MANIFEST.json")["cases"]), required=True)
    p.add_argument("--finalize", action="store_true")
    p.add_argument("--gpu")
    p.add_argument("--peer-root", action="append", default=[])
    p.add_argument("--existing-services", type=Path)
    p.add_argument("--remote-full-map", type=Path)
    a = p.parse_args()
    prepare(a.case, a.finalize, a.gpu, a.peer_root, a.existing_services, a.remote_full_map)
