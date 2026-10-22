"""CPU-only exact four-condition mirror; old RGB/Native tensors stay on host9."""
import json
import os
from pathlib import Path
import shutil
import sys
import time

from r86_contract import ROOT, read, sha, require, registry
from execution_gate import atomic


def materialize():
    registry()
    case = read(ROOT / "configs/protocol.json")["cases"][0]
    require(str(ROOT) == read(ROOT / "configs/runtime.json")["remote_root"], "target-only materialization")
    require(not read(ROOT / "configs/PARENT_CLOSURE.json").get("ready"), "already materialized")
    parent = Path(case["parent_root"])
    binding = read(ROOT / "configs/HISTORICAL_BINDING.json")
    native = binding["native"]
    gate = read(ROOT / "configs/PARENT_PAIR_GATE.json")
    require(gate["passed"] is True and all(gate["checks"].values()), "original paired run was not verified")
    transfer = read(ROOT / "configs/ORIGINAL_CONDITION_TRANSFER.json")
    require(transfer["passed"] and transfer["destination_root"] == str(parent), "direct transfer unbound")
    inventory = {}
    for record in transfer["files"]:
        relative = record["relative"]
        path = parent / relative
        require(path.is_file() and not path.is_symlink() and sha(path) == record["sha256"], "mirrored file differs")
        if relative in native["binding_artifacts"]:
            require(record["sha256"] == native["binding_artifacts"][relative], "original metadata differs")
        inventory[relative] = {"sha256": record["sha256"], "bytes": path.stat().st_size}
    cache = read(ROOT / "configs/CONDITION_CACHE.json")
    require(len(cache["tensors"]) == 4, "four model condition tensors required")
    for row in cache["tensors"]:
        relative = str(Path(row["file"]).relative_to(parent))
        require(inventory[relative]["sha256"] == row["sha256"], "original model condition file differs")
    run = case["parent_run"]
    require(read(parent / "logs" / (run + "_history.json"))["prompt"][2] ==
            read(ROOT / "configs/PARENT_GRAPH.json"), "original actual graph differs")
    require(read(parent / "audit/x0" / run / "manifest.json") ==
            read(ROOT / "configs/PARENT_CAPTURES.json"), "original capture metadata differs")
    prepared = ROOT / "prepared_parent"
    require(not list(prepared.iterdir()), "partial parent materialization exists")
    for suffix in ("conditioning", "noise"):
        shutil.copyfile(parent / "audit" / (run + "_" + suffix + ".json"), prepared / (suffix + ".json"))
    noise = read(prepared / "noise.json")
    original = Path(noise["cache_file"])
    relative = str(original.relative_to(case["historical_original_root"]))
    cached_noise = Path("/data4/researcher/h3_runs/timing_ive_reference_origin_r132_20261020/parent_artifacts/r122_long_0039_seed2026101701_noise.pt")
    expected_sha = native["binding_artifacts"][relative]
    require(sha(cached_noise) == expected_sha, "reused original AV noise differs")
    mirrored_noise = parent / relative
    if not mirrored_noise.exists():
        os.link(cached_noise, mirrored_noise)
    require(sha(mirrored_noise) == expected_sha, "mirrored noise differs")
    inventory[relative] = {"sha256": expected_sha, "bytes": mirrored_noise.stat().st_size}
    sys.path.insert(0, str(ROOT / "extensions"))
    import torch
    from H3X0Readout.core import tensor_signature
    torch.set_num_threads(4)
    saved = torch.load(mirrored_noise, map_location="cpu", weights_only=True)
    require(saved["signature"] == noise["signature"], "original noise metadata differs")
    signatures = [{k: v for k, v in tensor_signature(x).items() if k != "bytes"} for x in saved["tensors"]]
    require(signatures == noise["actual_noise_streams"], "original initial AV values differ")
    output_noise = ROOT / "audit" / original.name
    require(not output_noise.exists(), "new noise destination already exists")
    os.link(mirrored_noise, output_noise)
    atomic(prepared / "FILE_INVENTORY.json", inventory)
    required = ["prepared_parent/conditioning.json", "prepared_parent/noise.json",
                "prepared_parent/FILE_INVENTORY.json", "configs/PARENT_CAPTURES.json",
                "configs/PARENT_PAIR_GATE.json", case["source_pose_path"]]
    closure = {
        "schema": "r86-actual-parent-closure-v1", "ready": True, "status": "READY",
        "cases": {case["source_id"]: {"ready": True, "parent_run": run,
                  "required_actual_files": required,
                  "actual_file_sha256": {p: sha(ROOT / p) for p in required}}},
        "created_unix": time.time(), "GPU_launch_authorized": False,
        "exact_payload_scope": "four original model condition tensors and original AV noise",
        "historical_prefix_scope": "original signed capture metadata; cross-host signature comparison",
        "RGB_and_old_Native_tensor_entities_transferred": False,
    }
    atomic(ROOT / "configs/PARENT_CLOSURE.json", closure)
    bindings = read(ROOT / "configs/observer_external_bindings.json")
    seal = read(ROOT / "deploy_manifest.json")
    bindings["local_files"] = {p: v["sha256"] for p, v in seal["files"].items()
                               if p.startswith(("scripts/", "extensions/", "configs/"))}
    bindings["local_files"]["configs/PARENT_CLOSURE.json"] = sha(ROOT / "configs/PARENT_CLOSURE.json")
    atomic(ROOT / "configs/observer_bindings.json", bindings)
    require(not torch.cuda.is_initialized(), "CPU materialization initialized CUDA")
    atomic(ROOT / "audit/PARENT_MATERIALIZED.json", {
        "passed": True, "closure_sha256": sha(ROOT / "configs/PARENT_CLOSURE.json"),
        "bindings_sha256": sha(ROOT / "configs/observer_bindings.json"),
        "four_original_condition_files": True, "actual_original_AV_noise_exact": True,
        "torch_cuda_initialized": False,
    })
    return closure


if __name__ == "__main__":
    print(json.dumps(materialize(), indent=2))
