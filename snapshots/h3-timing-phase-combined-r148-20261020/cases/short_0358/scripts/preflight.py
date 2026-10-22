"""R148 CPU input/code checks and production seal checks."""
import argparse
import json
from pathlib import Path
from r132_contract import ROOT, read, sha, require, registry, validate_job


def runtime_smoke_matches(root, smoke):
    root=Path(root)
    if smoke['runtime_sha256']==sha(root/'configs/runtime.json'):return True
    binding=read(root/'configs/runtime_device_rebind.json')
    import hashlib
    before=json.loads(binding['previous_runtime_json']);after=read(root/'configs/runtime.json')
    changed={k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
    return (changed=={'expected_gpu_index'} and after['expected_gpu_index']==after['gpu_index']
        and hashlib.sha256(binding['previous_runtime_json'].encode()).hexdigest()==smoke['runtime_sha256']
        and binding['previous_smoke_sha256']==sha(root/'audit/RUNTIME_IMPORT_SMOKE.json')
        and binding['current_runtime_sha256']==sha(root/'configs/runtime.json'))

def check(root=ROOT, live=False):
    root = Path(root); science = read(root / "configs/scientific_contract.json")
    jobs, order = registry(root); runtime = read(root / "configs/runtime.json")
    require(science["NFE_per_job"] == science["callback_count"] == 20 and science["online_observer"] is False, "forward/observer contract changed")
    for run in order: validate_job(run, root)
    for path, row in read(root / "configs/runtime_kernel_hashes.json").items():
        require(sha(root / path) == row["current_sha256"] == row["parent_sha256"] and row["byte_equal"], "existing numerical core changed: " + path)
    require(runtime["reserve_vram"] == 8 and runtime["memory_mode"] == "normal", "runtime memory profile differs")
    if live:
        smoke=read(root/'audit/RUNTIME_IMPORT_SMOKE.json')
        require(smoke['passed'] and smoke['cuda_initialized'] is False and runtime_smoke_matches(root,smoke) and smoke['cached_module_sha256']==sha(root/'extensions/H3CachedCondition/__init__.py'),'actual CPU cache/import smoke pending')
        require(root.resolve() == Path(runtime["remote_root"]), "actual remote root required")
        from check_storage import check as check_storage
        from execution_gate import atomic, approval
        atomic(root / "audit/STORAGE_STARTUP.json", check_storage(root)); approval(root)
        require(read(root / "configs/admission.json")["ready_for_launch"] is True, "live admission pending")
        for path, row in read(root / "deploy_manifest.json")["files"].items():
            require(sha(root / path) == row["sha256"], "sealed file changed: " + path)
        for path, digest in read(root / "configs/parent_core_hashes.json").items():
            require(sha(Path(runtime["core"]) / path) == digest, "actual Comfy core differs")
    return {"passed": True, "jobs": order, "NFE": 20, "intervention_steps": list(range(6,15)),
            "intervention_blocks": list(range(50)), "temporal_router": "fixed_same_bin_plus_reference_origin_phase", "launch_admitted": live}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--live", action="store_true")
    print(json.dumps(check(live=parser.parse_args().live), indent=2))
