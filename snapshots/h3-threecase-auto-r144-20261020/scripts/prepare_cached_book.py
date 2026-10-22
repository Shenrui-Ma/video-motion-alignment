"""Original R122 cached tensors with explicit cross-host historical signature audit."""
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
original = ROOT / "cases/long_0039"
drink = ROOT / "cases/short_0358_cached_conditions"
root = ROOT / "cases/long_0039_cached_conditions"
if root.exists():
    raise FileExistsError(root)
shutil.copytree(original, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def change(path, old, new):
    text = path.read_text()
    if old not in text:
        raise ValueError("missing exact adaptation anchor: " + str(path))
    path.write_text(text.replace(old, new))


old_remote = read(root / "configs/runtime.json")["remote_root"]
remote = old_remote + "_cached_conditions"
for folder in ("scripts", "extensions", "configs", "analysis/postrun"):
    for path in (root / folder).rglob("*"):
        if path.is_file() and path.suffix in (".json", ".py"):
            write(path, path.read_text().replace(old_remote, remote))

for name in ("root_run_online.py", "lease_watchdog.py", "capacity_trial.py", "own_nvml.py",
             "execution_gate.py", "cgroup_memory.py", "working_set_capacity.py",
             "cpu_runtime_smoke.py", "service.py", "launch_remote.py", "preflight.py"):
    shutil.copyfile(drink / "scripts" / name, root / "scripts" / name)
for name in ("test_capacity_integration.py", "test_capacity_trial.py", "test_own_nvml.py",
             "R133_ACTUAL_PARENT_CHAIN.json", "R133_ACTUAL_SERVICE.json"):
    shutil.copyfile(drink / "tests" / name, root / "tests" / name)
shutil.copytree(drink / "extensions/H3CachedCondition", root / "extensions/H3CachedCondition",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
shutil.copyfile(drink / "analysis/postrun/verify_online.py", root / "analysis/postrun/verify_online.py")
change(root / "analysis/postrun/verify_online.py", "valid_frames=105", "valid_frames=106")

runtime = read(drink / "configs/runtime.json")
runtime.update(remote_root=remote, port=8645)
write(root / "configs/runtime.json", runtime)
write(root / "configs/cgroup_policy.json", read(drink / "configs/cgroup_policy.json"))
admission = read(drink / "configs/admission.json")
admission.update(permitted_compute_processes=[], root_live_review_required=True, ready_for_launch=False)
write(root / "configs/admission.json", admission)
write(root / "configs/admission_template.json", read(drink / "configs/admission_template.json"))
write(root / "configs/PARENT_CLOSURE.json", {"ready": False, "status": "MATERIALIZATION_PENDING"})
protocol = read(root / "configs/protocol.json")
protocol["capacity_trial"] = read(drink / "configs/protocol.json")["capacity_trial"]
protocol["resources"].update(read(drink / "configs/protocol.json")["resources"])
protocol["conditioning_execution"] = {
    "mode": "exact_original_clean_condition_cache", "text_encoder_calls": 0,
    "reference_encoder_calls": 0, "same_original_AV_noise": True,
    "policy_unchanged": True, "origin": "R122 original host9 tensors; direct SHA-verified transfer",
}
mirror = "/data4/researcher/h3_runs/threecase_auto_r144_20261020/original_condition_cache/long_0039"
case = protocol["cases"][0]
case["historical_original_root"] = case["parent_root"]
case["parent_root"] = mirror
case["historical_prefix_comparison"] = "cross_host_signature_audit"
protocol["prefix"]["comparison"] = "record original historical signatures through firstON; report cross-host differences without changing automatic decisions"
write(root / "configs/protocol.json", protocol)
science = read(root / "configs/scientific_contract.json")
science["cases"] = protocol["cases"]
write(root / "configs/scientific_contract.json", science)

binding = read(ROOT / "input_audit/long_0039_BINDING.json")
receipt = read(ROOT / "audit/BOOK_ORIGINAL_CONDITION_DIRECT_TRANSFER.json")
records = {row["relative"]: row for row in receipt["files"]}
selected = [row for row in binding["condition_tensor_files"] if len(row["tensor_signature"]["shape"]) != 4]
assert len(selected) == 4
roles = ("reference_vae_latent", "conditioning_embedding", "conditioning_tags", "conditioning_position")
tensors = []
for role, row in zip(roles, selected):
    relative = str(Path(row["file"]).relative_to(binding["producer_remote"]))
    assert records[relative]["sha256"] == row["sha256"]
    tensors.append(dict(row, role=role, original_file=row["file"], file=mirror + "/" + relative,
                        bytes=records[relative]["bytes"]))
shared = "r122_long_0039_shared"
condition_relative = "audit/" + shared + "_conditioning.json"
manifest = {
    "schema": "r144-original-clean-condition-cache-v1", "source_id": "long_0039",
    "seed": binding["seed"], "source_video_sha256": binding["source"]["sha256"],
    "prompt_sha256": binding["prompt_sha256"], "geometry": case["geometry"],
    "parent_root": mirror, "historical_original_root": binding["producer_remote"],
    "shared_run_id": shared, "conditioning": {
        "file": mirror + "/" + condition_relative,
        "sha256": records[condition_relative]["sha256"],
    }, "tensors": tensors,
    "published_tensor_paths": [str(Path(row["file"]).relative_to(mirror + "/audit")) for row in tensors],
    "RGB_archive_policy": "Original source/prepared RGB remain on host9; no RGB load/copy in cached execution",
    "direct_transfer_receipt_sha256": sha(ROOT / "audit/BOOK_ORIGINAL_CONDITION_DIRECT_TRANSFER.json"),
    "CPU_compatibility_sources": read(root / "configs/parent_core_hashes.json"),
}
write(root / "configs/CONDITION_CACHE.json", manifest)
shutil.copyfile(ROOT / "audit/BOOK_ORIGINAL_CONDITION_DIRECT_TRANSFER.json",
                root / "configs/ORIGINAL_CONDITION_TRANSFER.json")
graph_path = root / "configs/graphs" / (case["run_id"] + ".json")
graph = read(graph_path)
before = read(original / "configs/graphs" / graph_path.name)
graph["5"] = {"class_type": "H3CachedReferenceConditioning",
              "inputs": {"cache_manifest": remote + "/configs/CONDITION_CACHE.json",
                         "audit_dir": remote + "/audit", "run_id": case["run_id"]}}
for key in ("2", "22", "23"):
    del graph[key]
write(graph_path, graph)
change(root / "scripts/r86_contract.py", " return g\n",
       """ g['5']={'class_type':'H3CachedReferenceConditioning','inputs':{'cache_manifest':str(remote/'configs/CONDITION_CACHE.json'),'audit_dir':str(remote/'audit'),'run_id':RUN}}
 for key in ('2','22','23'):del g[key]
 return g
""")
change(root / "extensions/H3CachedCondition/__init__.py",
       'origin, target = parent / relative, root / relative',
       '''if str(relative) not in manifest["published_tensor_paths"]:
                    return  # RGB remains at its original host; numerical metadata is retained.
                origin, target = parent / relative, root / relative''')
change(root / "scripts/preflight.py",
       "proof['positive_tree_equal'] and proof['target_tree_equal']",
       "proof['tensor_shape_dtype_values_exact'] and proof['packed_layout_exact']")

transport = root / "extensions/H3AutomaticWindowRouter/transport.py"
text = transport.read_text()
for name, value in (("MAIN_UUID", runtime["gpu_uuid"]), ("DECODER_UUID", runtime["decoder_gpu_uuid"]),
                    ("PROTOCOL_SHA", sha(root / "configs/protocol.json"))):
    text = re.sub(r"^" + name + r"=.*$", name + "=" + repr(value), text, flags=re.M)
write(transport, text)
write(root / "audit/CACHE_GRAPH_DIFF.json", {
    "original_graph_sha256": sha(original / "configs/graphs" / graph_path.name),
    "cached_graph_sha256": sha(graph_path), "removed_nodes": {k: before[k] for k in ("2", "22", "23")},
    "node_5": {"before": before["5"], "after": graph["5"]},
    "DiT_sigma_sampler_noise_router_unchanged": True,
    "original_host9_four_condition_tensors": True,
    "historical_prefix_scope": "signed historical captures; cross-host difference is recorded, not an intervention decision",
})
print(json.dumps({"root": str(root), "remote_root": remote, "next": "install cross-host audit and materialize original cache"}))
