"""R129 CPU input/code checks and production seal checks."""
import argparse
import json
from pathlib import Path
from r129_contract import ROOT, read, sha, require, registry, validate_job


def check(root=ROOT, live=False):
    root = Path(root); science = read(root / "configs/scientific_contract.json")
    jobs, order = registry(root); runtime = read(root / "configs/runtime.json")
    require(science["NFE_per_job"] == science["callback_count"] == 20 and science["online_observer"] is False, "forward/observer contract changed")
    for run in order: validate_job(run, root)
    for path, row in read(root / "configs/runtime_kernel_hashes.json").items():
        require(sha(root / path) == row["current_sha256"] == row["parent_sha256"] and row["byte_equal"], "existing numerical core changed: " + path)
    require(runtime["reserve_vram"] == 8 and runtime["memory_mode"] == "normal", "runtime memory profile differs")
    if live:
        require(root.resolve() == Path(runtime["remote_root"]), "actual remote root required")
        from check_storage import check as check_storage
        from execution_gate import atomic, approval
        atomic(root / "audit/STORAGE_STARTUP.json", check_storage(root)); approval(root)
        require(read(root / "configs/admission.json")["ready_for_launch"] is True, "live admission pending")
        for path, row in read(root / "deploy_manifest.json")["files"].items():
            require(sha(root / path) == row["sha256"], "sealed file changed: " + path)
        for path, digest in read(root / "configs/parent_core_hashes.json").items():
            require(sha(Path(runtime["core"]) / path) == digest, "actual Comfy core differs")
    return {"passed": True, "jobs": order, "NFE": 20, "alignment_steps": list(range(20)),
            "alignment_blocks": list(range(50)), "temporal_router": "native", "launch_admitted": live}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--live", action="store_true")
    print(json.dumps(check(live=parser.parse_args().live), indent=2))
