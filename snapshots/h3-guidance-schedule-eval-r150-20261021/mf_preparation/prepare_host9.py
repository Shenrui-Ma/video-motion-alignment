"""Build a released R150 case for the previously verified host9 MF runner."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import sys

ROOT = Path(__file__).resolve().parent
EVAL = ROOT.parent
HOST9 = EVAL.parent / "h3-reference-feedback-r151-20261021/mf"
PRIOR = EVAL.parent / "h3-ive-position-edit-mf-host9-r137-20261020"
ARMS = ("early", "late", "split", "global_weak")
sys.path.insert(0, str(ROOT))
import prepare_batch as inputs_builder


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def copy(source, target, link=False):
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        os.link(source, target) if link else shutil.copyfile(source, target)
    assert sha(source) == sha(target), str(target)


def prepare(sid, peer_roots):
    assert (EVAL / "actual" / sid / "BATCH_RELEASE.json").is_file()
    assert all((EVAL / "mf_inputs" / sid / arm / "INPUTS.json").is_file() for arm in ARMS)
    # This existing path revalidates the actual media, per-arm gates, composite
    # release, pixel hashes, frame domain and cached source tracks.
    inputs_builder.packager.prepare(sid, False)
    source = ROOT / "batches" / sid
    target = ROOT / "host9_batches" / sid
    assert not (target / "SEAL.json").exists(), "Do not overwrite a sealed batch"
    inputs = read(source / "cases" / sid / "INPUTS.json")
    assert [x["role"] for x in inputs["targets"]] == list(ARMS)
    assert inputs["source_cache"] and inputs["valid_frames"] == inputs["evaluation_frames"]
    for folder in ("cases", "configs/evidence"):
        for path in (source / folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                copy(path, target / path.relative_to(source), link=True)
    batch = EVAL / "actual" / sid / "BATCH_RELEASE.json"
    for name, item in inputs_builder.finalize_batch.batch_evidence_records(read(batch)).items():
        copy(item["file"], target / "configs/evidence" / sid / (name + ".json"))
    copy(source / "configs/ive_NUMERIC.json", target / "configs/ive_NUMERIC.json")
    scripts = {}
    for path in sorted((HOST9 / "scripts").glob("*.py")):
        if path.name == "cpu_verify.py":
            continue
        copy(path, target / "scripts" / path.name)
        scripts[path.name] = {"file": str(path), "sha256": sha(path)}
        ast.parse(path.read_text())
    # Both actual tracker and score adapters remain byte-identical to the
    # successful host9 parent. Administrative common/peer support is from R151.
    for name in ("track.py", "score.py", "run_batch.py", "capacity.py", "capacity_v1.py"):
        assert sha(HOST9 / "scripts" / name) == sha(PRIOR / "scripts" / name), name
    copy(PRIOR / "audit/final_release.py", target / "audit/final_release.py")
    collector = (PRIOR / "audit/collect.py").read_text()
    collector = collector.replace(
        "REMOTE='/home/researcher/h3_runs/ive_position_edit_mf_r137_20261020'",
        "REMOTE=json.loads((R/'configs/RUNTIME.json').read_text())['remote_root']")
    collector = collector.replace(
        "['rsync','-a','--exclude','collect.py'",
        "['rsync','-a','-e','ssh -o ProxyCommand=none','--exclude','RESOURCE_OBSERVATIONS.json','--exclude','*.jsonl','--exclude','*.log','--exclude','collect.py'")
    (target / "audit/collect.py").write_text(collector)
    verifier = (source / "audit/verify_inputs.py").read_text()
    verifier = verifier.replace(
        "weight=R/'runtime/ive/weights/baseline_offline.pth'",
        "weight=Path(read(R/'configs/RUNTIME.json')['checkpoint'])")
    (target / "audit/verify_inputs.py").write_text(verifier)
    runtime = read(HOST9 / "configs/RUNTIME.json")
    runtime.update(remote_root="/home/researcher/h3_runs/guidance_schedule_mf_r150_host9_20261021/" + sid,
                   peer_roots=peer_roots)
    assert all(p.startswith("/home/researcher/h3_runs/guidance_schedule_r150_host9_20261021/cases/")
               and ".." not in Path(p).parts for p in peer_roots)
    write(target / "configs/RUNTIME.json", runtime)
    write(target / "configs/PLAN.json", {
        "groups": [sid], "jobs": [{"case": sid, "role": arm} for arm in ARMS],
        "unique_targets": 4, "source_cache_count": 1, "new_source_trackers": 0})
    local_runtime = (source / "runtime/ive").resolve()
    (target / "runtime").mkdir(exist_ok=True)
    if not (target / "runtime/ive").exists():
        (target / "runtime/ive").symlink_to(local_runtime, target_is_directory=True)
    reuse = {"runtime/ive": "/home/researcher/h3_runs/ive_r119_mf_host9_20261020/runtime/ive"}
    for arm in ARMS:
        gate = read(EVAL / "actual" / sid / arm / "GATE.json")
        binding = read(source / "configs/evidence" / sid / arm / "binding.json")
        if binding["host"] == "H3_SERVER_A":
            reuse[f"cases/{sid}/{arm}/full.mp4"] = gate["video"]["file"]
    write(target / "audit/REMOTE_REUSE_PLAN.json", reuse)
    (target / "audit/materialize_existing.py").write_text('''"""Attach only pre-existing, exact-hash data; no network or model load."""
import hashlib,json,os
from pathlib import Path
R=Path(__file__).resolve().parents[1]
assert os.environ.get("CUDA_VISIBLE_DEVICES")==""
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
seal=read(R/"SEAL.json")["files"]
for rel,source in read(R/"audit/REMOTE_REUSE_PLAN.json").items():
 p,s=R/rel,Path(source)
 assert s.exists(),str(s)
 if rel=="runtime/ive":
  assert s.is_dir()
 else:
  assert s.is_file() and sha(s)==seal[rel],str(s)
 p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():p.symlink_to(s,target_is_directory=s.is_dir())
 if rel=="runtime/ive":
  assert p.resolve()==s.resolve()
 else:assert sha(p)==seal[rel]
print("Existing runtime/media hashes verified; no model loaded.")
''')
    write(target / "ADMIN_DIFF.json", {
        "scripts": scripts, "numerical_source": str(local_runtime),
        "official_numerics_unchanged": True,
        "lifecycle": {"file": str(PRIOR / "SEAL.json"), "sha256": sha(PRIOR / "SEAL.json")},
        "changed": ["R150 four actual targets and verified cached source",
                    "host9 paths and explicit current peer roots",
                    "compact collector excludes raw resource logs"],
        "prerequisite": "R151 MF exact final release before any launch; fresh admission remains mandatory",
        "GPU_started": False})
    copy(batch, target / "configs/BATCH_RELEASE.json")
    upload_script = """#!/bin/sh
set -eu
MF_PACKAGE=__LOCAL__
MF_REMOTE=__REMOTE__
python3 - "$MF_PACKAGE" <<'CHECK'
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1]);h=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
s=json.loads((p/'SEAL.json').read_text());r=json.loads((p/'ROOT_REVIEW.json').read_text())
assert r['passed'] and r.get('CPU_upload_authorized',r.get('GPU_execution_authorized',False))
assert r['seal_sha256']==h(p/'SEAL.json')
for rel,digest in s['files'].items():assert h(p/rel)==digest,rel
files=(p/'audit/DEPLOY_FILES.txt').read_text().splitlines()
assert len(files)==len(set(files))
assert all(not Path(x).is_absolute() and '..' not in Path(x).parts and not x.startswith('runtime/') for x in files)
print({'upload_files':len(files)+1,'upload_bytes':sum((p/f).stat().st_size for f in files)+(p/'ROOT_REVIEW.json').stat().st_size})
CHECK
ssh -o ProxyCommand=none H3_SERVER_A "mkdir -p '$MF_REMOTE'"
rsync -a -e 'ssh -o ProxyCommand=none' --files-from="$MF_PACKAGE/audit/DEPLOY_FILES.txt" "$MF_PACKAGE/" "H3_SERVER_A:$MF_REMOTE/"
rsync -a -e 'ssh -o ProxyCommand=none' "$MF_PACKAGE/ROOT_REVIEW.json" "H3_SERVER_A:$MF_REMOTE/ROOT_REVIEW.json"
ssh -o ProxyCommand=none H3_SERVER_A "cd '$MF_REMOTE' && CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/researcher/miniconda3/envs/comfyui/bin/python audit/materialize_existing.py && CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/researcher/miniconda3/envs/comfyui/bin/python audit/verify_inputs.py"
"""
    (target / "audit/UPLOAD_AFTER_REVIEW.sh").write_text(
        upload_script.replace("__LOCAL__", shlex.quote(str(target))).replace(
            "__REMOTE__", shlex.quote(runtime["remote_root"])))
    files = {}
    for top in ("scripts", "configs", "cases", "audit"):
        for path in (target / top).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                if path.suffix == ".py":
                    ast.parse(path.read_text())
                files[str(path.relative_to(target))] = sha(path)
    write(target / "SEAL.json", {
        "schema": "r150-host9-official-mf-four-targets-v1", "final_inputs_bound": True,
        "files": files, "new_target_trackers": 4, "new_source_trackers": 0,
        "batch_release_sha256": sha(batch)})
    upload = sorted(x for x in files if x not in reuse) + ["SEAL.json", "ADMIN_DIFF.json"]
    (target / "audit/DEPLOY_FILES.txt").write_text("\n".join(upload) + "\n")
    write(target / "CPU_PREPARATION.json", {
        "passed": True, "actual_outputs": 4, "cached_sources": 1, "new_source_trackers": 0,
        "seal_sha256": sha(target / "SEAL.json"),
        "upload_bytes_before_additional_remote_reuse": sum((target / x).stat().st_size for x in upload),
        "target_CPU_validation_pending": True, "GPU_started": False})
    print(json.dumps({"package": str(target), "seal_sha256": sha(target / "SEAL.json")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=tuple(inputs_builder.PINS["source_media"]))
    parser.add_argument("--peer-root", action="append", default=[])
    args = parser.parse_args()
    prepare(args.case, args.peer_root)
