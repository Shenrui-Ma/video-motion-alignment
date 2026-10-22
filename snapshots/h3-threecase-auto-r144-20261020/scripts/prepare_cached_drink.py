"""Prepare an independent exact-cache variant; preserve failed original attempt."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from prepare_cases import ROOT, read, write, sha, replace

source = ROOT / "cases/short_0358"
root = ROOT / "cases/short_0358_cached_conditions"
if root.exists():
    raise ValueError("cached variant already exists")
shutil.copytree(source, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
old_remote = read(source / "configs/runtime.json")["remote_root"]
remote = old_remote + "_cached_conditions"
for folder in ("scripts", "extensions", "configs", "analysis/postrun"):
    for path in (root / folder).rglob("*"):
        if path.is_file() and path.suffix in (".py", ".json"):
            text = path.read_text()
            if old_remote in text:
                write(path, text.replace(old_remote, remote))
for name in ("admission.json", "PARENT_CLOSURE.json"):
    if name == "PARENT_CLOSURE.json":
        write(root / "configs" / name, {"ready": False, "status": "MATERIALIZATION_PENDING"})
    else:
        obj = read(root / "configs" / name)
        obj.update(permitted_compute_processes=[], root_live_review_required=True, ready_for_launch=False)
        write(root / "configs" / name, obj)
protocol = read(root / "configs/protocol.json")
protocol["conditioning_execution"] = {
    "mode": "exact_original_clean_condition_cache",
    "text_encoder_calls": 0, "reference_encoder_calls": 0,
    "policy_unchanged": True, "same_original_AV_noise": True,
    "reason": "Avoid repeated Qwen/reference encoding while preserving exact original model inputs",
}
write(root / "configs/protocol.json", protocol)
b = read(ROOT / "input_audit/short_0358_BINDING.json")
cache_map = read(ROOT / "input_audit/HOST41_CONDITION_CACHE_MAP.json")
shared_id = read(source / "configs/PARENT_GRAPH.json")["51"]["inputs"]["source_run_id"]
shared_rel = f"audit/{shared_id}_conditioning.json"
manifest = {
    "schema": "r144-original-clean-condition-cache-v1", "source_id": "short_0358",
    "seed": b["seed"], "source_video_sha256": b["source"]["sha256"], "prompt_sha256": b["prompt_sha256"],
    "geometry": protocol["cases"][0]["geometry"], "parent_root": b["producer_remote"],
    "shared_run_id": shared_id,
    "conditioning": {"file": b["producer_remote"] + "/" + shared_rel,
                     "sha256": b["runs"]["native"]["binding_artifacts"][shared_rel]},
    "tensors": [{key: row[key] for key in ("role", "file", "sha256", "tensor_signature", "bytes")}
                for row in cache_map["conditions"] if row["source_id"] == "short_0358"],
    "CPU_compatibility_sources": read(source / "configs/parent_core_hashes.json"),
}
write(root / "configs/CONDITION_CACHE.json", manifest)
(root / "extensions/H3CachedCondition").mkdir()
shutil.copyfile(ROOT / "templates/H3CachedCondition.py", root / "extensions/H3CachedCondition/__init__.py")
gpath = root / "configs/graphs" / (protocol["cases"][0]["run_id"] + ".json")
graph = read(gpath)
old_graph = read(source / "configs/graphs" / gpath.name)
graph["5"] = {"class_type": "H3CachedReferenceConditioning",
              "inputs": {"cache_manifest": remote + "/configs/CONDITION_CACHE.json",
                         "audit_dir": remote + "/audit", "run_id": protocol["cases"][0]["run_id"]}}
for key in ("2", "22", "23"):
    del graph[key]
write(gpath, graph)
contract = root / "scripts/r86_contract.py"
replace(contract, " return g\n", """ g['5']={'class_type':'H3CachedReferenceConditioning','inputs':{'cache_manifest':str(remote/'configs/CONDITION_CACHE.json'),'audit_dir':str(remote/'audit'),'run_id':RUN}}
 for key in ('2','22','23'):del g[key]
 return g
""")
replace(root / "scripts/launch_remote.py", "'H3AutomaticWindowRouter')", "'H3AutomaticWindowRouter','H3CachedCondition')")
replace(root / "scripts/service.py", "'H3AutomaticWindowRouter',", "'H3AutomaticWindowRouter', 'H3CachedCondition',")
transport = root / "extensions/H3AutomaticWindowRouter/transport.py"
write(transport, re.sub(r"^PROTOCOL_SHA=.*$", f"PROTOCOL_SHA={sha(root/'configs/protocol.json')!r}",
                       transport.read_text(), flags=re.M))
inheritance = read(root / "audit/INHERITANCE.json")
for folder in ("scripts", "extensions", "analysis/postrun"):
    for path in (root / folder).rglob("*.py"):
        rel = str(path.relative_to(root))
        old = source / rel
        if old.exists() and sha(path) != sha(old):
            inheritance["unchanged_numerics"].pop(rel, None)
            inheritance["metadata_lifecycle_adaptations"][rel] = {
                "parent_sha256": sha(old), "sha256": sha(path), "change": "exact condition cache variant"}
write(root / "audit/INHERITANCE.json", inheritance)
write(root / "audit/CACHE_GRAPH_DIFF.json", {
    "original_graph_sha256": sha(source / "configs/graphs" / gpath.name),
    "cached_graph_sha256": sha(gpath),
    "removed_nodes": {k: old_graph[k] for k in ("2", "22", "23")},
    "replaced_node_5": {"before": old_graph["5"], "after": graph["5"]},
    "path_updates_only_other_nodes": ["6", "14", "50", "51", "52"],
    "DiT_sigma_sampler_noise_router_unchanged": True,
    "original_attempt_preserved": True,
})
subprocess.run([sys.executable, str(root / "scripts/preflight.py")], check=True)
subprocess.run([sys.executable, str(root / "scripts/execution_gate.py"), "seal"], check=True)
print(json.dumps({"root": str(root), "remote_root": remote, "seal_sha256": sha(root / "deploy_manifest.json")}, indent=2))
