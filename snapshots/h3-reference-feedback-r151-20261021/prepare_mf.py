"""Reuse the successful host9 MF lifecycle; bind only actual R151 output files."""
from pathlib import Path
import argparse
import ast
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE / "mf"
PRIOR = HERE.parent / "h3-ive-caption-scrubs-mf-host9-20261020"
R149 = HERE.parent / "h3-guidance-schedule-eval-r149-20261020/mf_preparation/batches"
CASES = ("short_0252", "short_0358", "05_real_megumi_v")
REMOTE = "/home/researcher/h3_runs/reference_feedback_mf_r151_20261021"
NUMERIC = R149 / "short_0252/runtime/ive"
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())


def save(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def link(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        os.link(src, dst)
    assert sha(src) == sha(dst)


def setup():
    assert not (ROOT / "SEAL.json").exists(), "Do not change a sealed MF batch"
    if (ROOT / "PREPARED.json").exists():
        return
    for directory in ("scripts", "audit", "configs", "runtime", "results", "state", "cases"):
        (ROOT / directory).mkdir(parents=True, exist_ok=True)
    for p in (PRIOR / "scripts").glob("*.py"):
        shutil.copy2(p, ROOT / "scripts" / p.name)
    shutil.copy2(PRIOR / "audit/final_release.py", ROOT / "audit/final_release.py")
    collector = (PRIOR / "audit/collect.py").read_text()
    collector = collector.replace(
        "REMOTE='/home/researcher/h3_runs/ive_caption_scrubs_mf_host9_20261020'",
        "REMOTE=json.loads((R/'configs/RUNTIME.json').read_text())['remote_root']")
    collector = collector.replace("requested_targets=2", "requested_targets=6")
    collector = collector.replace(
        "['rsync','-a','--exclude','collect.py'",
        "['rsync','-a','-e','ssh -o ProxyCommand=none','--exclude','RESOURCE_OBSERVATIONS.json','--exclude','*.jsonl','--exclude','*.log','--exclude','collect.py'")
    (ROOT / "audit/collect.py").write_text(collector)
    rt = read(PRIOR / "configs/RUNTIME.json")
    rt.update(remote_root=REMOTE, peer_roots=[
        "/home/researcher/h3_runs/guidance_schedule_r150_host9_20261021/cases/" + x
        for x in ("short_0085", "short_0274", "musk05", "firefly06", "sam07")])
    save(ROOT / "configs/RUNTIME.json", rt)
    shutil.copy2(R149 / "short_0252/configs/ive_NUMERIC.json", ROOT / "configs/ive_NUMERIC.json")
    (ROOT / "runtime/ive").symlink_to(NUMERIC, target_is_directory=True)
    save(ROOT / "configs/PLAN.json", {"groups": list(CASES),
         "jobs": [{"case": sid, "role": arm} for sid in CASES
                  for arm in ("reverse_only", "combined")]})
    peer = ROOT / "scripts/peer_support.py"
    text = peer.read_text().replace(
        "assert root.parent in allowed, 'peer root outside managed runs'",
        "assert str(root) in read(ROOT/'configs/RUNTIME.json')['peer_roots'], 'peer root outside explicit R150 list'")
    text = text.replace("from common import read,save", "from common import ROOT,read,save")
    # Ignore a previous peer generation that has exited, including a reused PID.
    text = text.replace(
        "assert actual == owner['identity'] and actual['uid'] == os.getuid() == 1016",
        "if actual != owner['identity']: continue\n        assert actual['uid'] == os.getuid() == 1016")
    peer.write_text(text)
    common = ROOT / "scripts/common.py"
    text = common.read_text().replace(
        "for rel,h in read(ROOT/'SEAL.json')['files'].items():assert sha(ROOT/rel)==h,'sealed file changed '+rel",
        "for rel,h in read(ROOT/'SEAL.json')['files'].items():assert sha(ROOT/rel)==h,'sealed file changed '+rel\n"
        " for rel,h in read(ROOT/'configs/ive_NUMERIC.json')['files'].items():assert sha(ROOT/'runtime/ive'/rel)==h,'official numerical source changed '+rel")
    common.write_text(text)
    final = ROOT / "audit/final_release.py"
    text = final.read_text().replace("len(states) == 3 and len(results) == 2",
                                     "len(states) == 6 and len(results) == 6")
    text = text.replace("'completed_generated_scores':2", "'completed_generated_scores':6")
    final.write_text(text)
    cpu = ROOT / "scripts/cpu_verify.py"
    text = cpu.read_text().replace("'frames':105,'roles':['native']",
                                   "'cases':read(ROOT/'configs/PLAN.json')['groups'],'new_trackers':6,'source_trackers':0")
    cpu.write_text(text)
    for sid in CASES:
        src = R149 / sid / "cases" / sid
        dst = ROOT / "cases" / sid
        for rel in ("source_full.mp4", "source_score.mp4", "tracks/source/REPORT.json", "tracks/source/tracks.npz"):
            link(src / rel, dst / rel)
        inputs = read(src / "INPUTS.json")
        inputs.update(schema="r151-official-mf-inputs-v1", targets=[])
        assert sha(dst / "source_full.mp4") == inputs["source_full_sha256"]
        assert sha(dst / "source_score.mp4") == inputs["source_score_sha256"]
        assert sha(dst / "tracks/source/REPORT.json") == inputs["source_cache"]["report_sha256"]
        assert sha(dst / "tracks/source/tracks.npz") == inputs["source_cache"]["tracks_sha256"]
        save(dst / "INPUTS.json", inputs)
    save(ROOT / "PREPARED.json", {"status": "PENDING_ACTUAL_SIX_OUTPUTS_AND_RELEASES",
         "lifecycle_parent": str(PRIOR), "numerical_parent": str(NUMERIC),
         "official_numerics_unchanged": True, "GPU_started": False,
         "source_cache_reused": list(CASES), "expected_new_trackers": 6,
         "host9_CPU_import_verified": {"torch": "2.5.1+cu121", "numpy": "1.26.4",
                                      "scipy": "1.15.3", "CUDA_initialized": False}})


def score_helper():
    # Execute the exact already-used lossless crop/time helper, with its imports.
    source = HERE.parent / "h3-timing-phase-combined-eval-r148-20261020/mf_preparation/audit/prepare_queue.py"
    code = source.read_text()
    node = next(n for n in ast.parse(code).body if isinstance(n, ast.FunctionDef) and n.name == "score_view")
    fragment = "\n".join(code.splitlines()[node.lineno - 1:node.end_lineno])
    sys.path.insert(0, str(NUMERIC / "metric_runtime"))
    import ive_mf_adapter as adapter
    import subprocess
    namespace = dict(subprocess=subprocess, FFMPEG="/opt/homebrew/bin/ffmpeg",
                     FFPROBE="/opt/homebrew/bin/ffprobe", frame_hashes=adapter.frame_hashes,
                     media_info=adapter.media_info, validate_time_view=adapter.validate_time_view)
    exec(compile(fragment, str(source), "exec"), namespace)
    return namespace["score_view"], {"file": str(source), "sha256": sha(source)}


def add_case(sid):
    case = HERE / "cases" / sid
    rows = read(case / "configs/scientific_contract.json")["cases"]
    inputs = read(ROOT / "cases" / sid / "INPUTS.json")
    helper, helper_binding = score_helper()
    for row in rows:
        arm, run = row["arm"], row["run_id"]
        receipt = read(case / "actual" / run / "COLLECTED.json")
        gate_path = Path(receipt["gate"])
        gate = read(gate_path)
        assert gate["passed"] and gate["run_id"] == run
        assert gate["producer_seal_sha256"] == sha(case / "deploy_manifest.json")
        for rel, digest in gate["binding_artifacts"].items():
            assert sha(case / rel) == digest
        assert sha(receipt["video"]) == gate["video"]["sha256"]
        dst = ROOT / "cases" / sid / arm
        dst.mkdir(exist_ok=True)
        link(Path(receipt["video"]), dst / "full.mp4")
        geometry = {"valid_frames": row["valid_frame_count"], "crop_xywh": row["evaluation_crop_xywh"]}
        pixels = helper(dst / "full.mp4", dst / "score.mp4", geometry)
        target = {"role": arm, "full_file": arm + "/full.mp4", "full_sha256": sha(dst / "full.mp4"),
                  "score_file": arm + "/score.mp4", "score_sha256": sha(dst / "score.mp4"),
                  "score_frame_md5": pixels, "evaluation_indices": row["evaluation_indices"],
                  "inventory_bindings": [{"id": run, "field": arm}],
                  "new_generation_only": True, "producer_gate_sha256": sha(gate_path),
                  "score_view_helper": helper_binding}
        existing = next((x for x in inputs["targets"] if x["role"] == arm), None)
        if existing is not None:
            assert existing == target
        else:
            inputs["targets"].append(target)
        link(gate_path, ROOT / "configs/evidence" / sid / (arm + "_GATE.json"))
    save(ROOT / "cases" / sid / "INPUTS.json", inputs)


def seal():
    releases = []
    for sid in CASES:
        case = HERE / "cases" / sid
        attempt = next((case / "actual").glob("root_r151*"))
        release, complete = attempt / "ROOT_EXIT_RECEIPT.json", attempt / "COMPLETE.json"
        r, c = read(release), read(complete)
        assert r["passed"] and r["process_absent"] and r["CUDA_allocation_absent"]
        assert c["passed"] and c["remaining"] == [] and c["service_owner"] == r["owner"]
        inputs = read(ROOT / "cases" / sid / "INPUTS.json")
        assert [x["role"] for x in inputs["targets"]] == ["reverse_only", "combined"]
        for p in (release, complete):
            link(p, ROOT / "configs/evidence" / sid / p.name)
        releases.append({"source_id": sid, "release_sha256": sha(release), "complete_sha256": sha(complete)})
    save(ROOT / "configs/PRODUCER_RELEASES.json", {"passed": True, "cases": releases})
    files = {}
    for directory in ("scripts", "configs", "cases", "audit"):
        for p in (ROOT / directory).rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                files[str(p.relative_to(ROOT))] = sha(p)
    save(ROOT / "SEAL.json", {"schema": "r151-official-mf-six-targets-v1",
                             "files": files, "created_unix": time.time()})
    print("SEALED", sha(ROOT / "SEAL.json"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=CASES)
    parser.add_argument("--seal", action="store_true")
    args = parser.parse_args()
    setup()
    if args.case:
        add_case(args.case)
    if args.seal:
        seal()
    print(ROOT)
