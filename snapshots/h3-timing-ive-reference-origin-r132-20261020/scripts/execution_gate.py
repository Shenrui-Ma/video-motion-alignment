"""Root admission for the single registered aligned-origin comparison."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from r132_contract import ROOT, RUN_ID, read, sha, registry, require


def atomic(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n"); os.replace(tmp, path)


def exclusive(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        tmp.write_text(json.dumps(value, indent=2) + "\n"); os.link(tmp, path)
    finally:
        if tmp.exists(): tmp.unlink()


def persist_gate(path, value):
    def stable(v): return {k: x for k, x in v.items() if k != "created_unix"}
    if Path(path).exists():
        old = read(path); require(stable(old) == stable(value), "existing evidence changed"); return old
    exclusive(path, value); return value


def root_review(root=ROOT):
    root = Path(root)
    review = read(root / "audit/ROOT_PRELAUNCH_REVIEW.json")
    require(review.get("approved") is True and review["producer_seal_sha256"] == sha(root / "deploy_manifest.json"), "root review missing or stale")
    return review


def predecessor_released(root=ROOT):
    import service
    root = Path(root); config = read(root / "configs/predecessor.json")
    previous = Path(config["root"])
    receipt = previous / config["receipt"]
    require(sha(receipt) == config["receipt_sha256"], "R131 release receipt changed")
    value = read(receipt)
    require(sha(previous / config['complete']) == config['complete_sha256'] and read(previous / config['complete'])['passed'] is True, 'R131 completed disposition changed')
    require(value["passed"] is True and value["process_absent"] and value["CUDA_allocation_absent"], "R131 release incomplete")
    owner = value["owner"]
    require(owner["pid"] == config["service_pid"] and str(owner["identity"]["start_ticks"]) == config["service_start_ticks"], "R131 owner changed")
    require(service.current_identity(owner["pid"]) != owner["identity"], "R131 original process remains alive")
    require(not any(r["pid"] == owner["pid"] for r in service.compute_processes()), "R131 PID still has CUDA allocation")
    return {"receipt": str(receipt), "sha256": sha(receipt), "verified": True}


def approval(root=ROOT):
    root = Path(root); a = read(root / "audit/ROOT_SCREEN_APPROVAL.json")
    runtime = read(root / "configs/runtime.json"); _, order = registry(root)
    require(a.get("schema") == "r132-native-screen-approval-v1" and a.get("root_approved") is True, "root admission pending")
    require(a["runtime_profile_sha256"] == sha(root / "configs/runtime.json") and a["main_gpu_uuid"] == runtime["gpu_uuid"], "runtime changed")
    require(a["registered_runs"] == order and a["required_free_bytes"] >= 40 * 1024**3 and a["reserve_vram_gib"] == 8, "resource scope changed")
    root_review(root)
    return a


def admitted_job(name, root=ROOT):
    approval(root)
    return name == RUN_ID and registry(root)[1] == [name]


def seal(root=ROOT):
    root = Path(root)
    require(not (root / "processes/service.json").exists(), "service already registered")
    paths = []
    for folder in ("scripts", "extensions", "configs", "design", "analysis/postrun", "tests"):
        paths.extend(p for p in (root / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != "admission.json")
    paths.extend((root / "audit/root_run_batch.py", root / "audit/INHERITANCE.json"))
    paths.extend((root / "inputs").iterdir())
    value = {"schema": "r132-single-comparison-seal-v1", "created_unix": time.time(),
             "files": {str(p.relative_to(root)): {"sha256": sha(p), "bytes": p.stat().st_size} for p in sorted(paths)}}
    atomic(root / "deploy_manifest.json", value)
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("action", choices=["seal", "approve-screen"])
    parser.add_argument("--root-admitted", action="store_true"); parser.add_argument("--free-mib", type=int, default=40960)
    args = parser.parse_args()
    if args.action == "seal":
        value = seal(); print(json.dumps({"files": len(value["files"]), "sha256": sha(ROOT / "deploy_manifest.json")}))
    else:
        require(ROOT == Path(read(ROOT / "configs/runtime.json")["remote_root"]), "actual remote root required")
        require(args.root_admitted and args.free_mib >= 40960, "40GiB resource admission required")
        review = root_review(); predecessor = predecessor_released()
        value = {"schema": "r132-native-screen-approval-v1", "root_approved": True,
                 "runtime_profile_sha256": sha(ROOT / "configs/runtime.json"), "main_gpu_uuid": read(ROOT / "configs/runtime.json")["gpu_uuid"],
                 "registered_runs": registry()[1], "required_free_bytes": args.free_mib * 1024**2,
                 "reserve_vram_gib": 8, "root_review_sha256": sha(ROOT / "audit/ROOT_PRELAUNCH_REVIEW.json"),
                 "predecessor": predecessor, "created_unix": time.time()}
        exclusive(ROOT / "audit/ROOT_SCREEN_APPROVAL.json", value); print(json.dumps(value))
