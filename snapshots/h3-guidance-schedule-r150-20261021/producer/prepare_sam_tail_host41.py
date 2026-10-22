"""Move only the unstarted Sam tail to GPU0; preserve the running prefix."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import time

P = Path(__file__).resolve().parents[1]
BASE = P / "sam_parallel_host9"
SOURCE = P / "cases/sam07"
PREFIX = P / "host9/cases/sam07"
OLD_TAIL = BASE / "cases/sam07"
DEST = P / "sam_tail_host41"
T = DEST / "cases/sam07"
REMOTE = "/data4/researcher/h3_runs/guidance_schedule_r150_sam_tail_host41_20261021/cases/sam07"


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


assert not T.exists()
old = read(SOURCE / "deploy_manifest.json")
for rel, item in old["files"].items():
    assert sha(SOURCE / rel) == item["sha256"], rel
    path = T / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE / rel, path)
for rel in ("producer", "logs", "processes", "input", "output", "temp", "user",
            "custom_nodes", "audit/router", "audit/x0"):
    (T / rel).mkdir(parents=True, exist_ok=True)
rt = read(T / "configs/runtime.json")
old_root = rt["remote_root"]
rt.update(remote_root=REMOTE, port=8658,
          profile_scope="Sam07 split/global tail after Firefly release; matching-cache Native approved on host9")
write(T / "configs/runtime.json", rt)
for path in (T / "configs/graphs").glob("*.json"):
    path.write_text(path.read_text().replace(old_root, REMOTE))

roles = ["split", "global_weak"]
science = read(T / "configs/scientific_contract.json")
runs = [c["run_id"] for c in science["cases"] if c["arm"] in roles]
segment_id = "sam07_tail_host41_gpu0"
base_manifest = read(BASE / "MIGRATION_MANIFEST.json")
base_deploy = read(BASE / "MIGRATION_DEPLOYMENT.json")
prefix = base_deploy["segments"]["prefix"]
assert sha(PREFIX / "deploy_manifest.json") == prefix["producer_seal_sha256"]
write(DEST / "BASE_MIGRATION_MANIFEST.json", base_manifest)
write(DEST / "BASE_MIGRATION_DEPLOYMENT.json", base_deploy)
tail = {
    "segment_id": segment_id, "host": rt["host"], "remote_root": REMOTE,
    "roles": roles, "run_ids": runs, "gpu_index": 0,
    "aggregate_gate": "analysis/postrun/sam07/SCHEDULE_RUNTIME_GATE.json",
    "aggregate_schema": "r149-fixed-schedule-segment-gate-v1",
    "COMPLETE_schema": "r149-schedule-segment-completion-v1",
}
manifest = {
    "schema": "r150-planned-parallel-tail-rebinding-v1", "source_id": "sam07",
    "created_unix": time.time(),
    "base_migration_manifest_sha256": sha(BASE / "MIGRATION_MANIFEST.json"),
    "base_migration_deployment_sha256": sha(BASE / "MIGRATION_DEPLOYMENT.json"),
    "prefix_bound_manifest_sha256": sha(BASE / "MIGRATION_MANIFEST.json"),
    "prefix_producer_seal_sha256": prefix["producer_seal_sha256"],
    "segments": {"prefix": base_manifest["segments"]["prefix"], "tail": tail},
    "all_roles": base_manifest["all_roles"], "all_run_ids": base_manifest["all_run_ids"],
    "replaces_unstarted_tail": base_deploy["segments"]["tail"],
    "science": {
        **base_manifest["science"],
        "tail_scientific_contract_sha256": sha(T / "configs/scientific_contract.json"),
        "tail_condition_cache_sha256": sha(T / "configs/CONDITION_CACHE.json"),
        "tail_graph_sha256": {c["arm"]: sha(T / "configs/graphs" / (c["run_id"] + ".json"))
                             for c in science["cases"]},
        "tensor_sha256": [r["sha256"] for r in read(T / "configs/CONDITION_CACHE.json")["tensors"]],
    },
    "tail_admission": {
        "Firefly_actual_COMPLETE_and_exact_release": True,
        "matching_cache_native_visual_pass_required": True,
        "prefix_may_still_be_running_on_host9": True,
        "host41_own_video_max": 1, "tail_once_only": True,
    },
    "completion": "Original prefix four roles plus this tail two roles, each with its actual release.",
}
write(DEST / "MIGRATION_MANIFEST.json", manifest)
write(T / "configs/MIGRATION_MANIFEST.json", manifest)
write(T / "configs/execution_segment.json", {
    "schema": "r149-execution-segment-v1", "segment_id": segment_id,
    "allowed_runs": runs, "allowed_roles": roles,
    "all_other_registered_runs_external": True,
})
write(T / "configs/queue.json", {"jobs": runs, "finalize": True})

# The checked registry/verifier already express the same two roles.
for rel in ("scripts/r132_contract.py", "analysis/postrun/verify_schedule.py"):
    text = (OLD_TAIL / rel).read_text().replace("sam07_tail_gpu2", segment_id)
    (T / rel).write_text(text)
path = T / "audit/root_run_batch.py"
text = path.read_text()
needle = "{'schema':'r149-schedule-completion-v1','passed':True,"
assert text.count(needle) == 1
text = text.replace(needle, "{'schema':'r149-schedule-segment-completion-v1','segment_id':" +
                    repr(segment_id) + ",'migration_manifest_sha256':sha(ROOT/'configs/MIGRATION_MANIFEST.json'),'passed':True,")
path.write_text(text)
shutil.copy2(OLD_TAIL / "tests/test_schedule.py", T / "tests/test_schedule.py")
shutil.copy2(OLD_TAIL / "scripts/native_review_gate.py", T / "scripts/native_review_gate.py")
for name in ("check_fresh_paths.py", "watch_queue.py"):
    shutil.copy2(PREFIX / "producer" / name, T / "producer" / name)

# Host paths differ; all actual conditioning/noise tensors and model code match.
a = read(PREFIX / "configs/CONDITION_CACHE.json")
b = read(T / "configs/CONDITION_CACHE.json")
assert [r["sha256"] for r in a["tensors"]] == [r["sha256"] for r in b["tensors"]]
assert a["conditioning"]["sha256"] == b["conditioning"]["sha256"]
ps = read(PREFIX / "configs/scientific_contract.json")
for key in set(science) - {"parent_noise_file", "execution_runtime"}:
    assert science[key] == ps[key], key
for rel, digest in read(T / "configs/numerical_reuse.json").items():
    assert sha(T / rel) == sha(PREFIX / rel) == digest, rel
subprocess.run(["python3", "scripts/execution_gate.py", "seal"], cwd=T, check=True)
deployment = {
    "schema": "r150-planned-parallel-tail-rebinding-deployment-v1",
    "source_id": "sam07", "created_unix": time.time(),
    "migration_manifest_sha256": sha(DEST / "MIGRATION_MANIFEST.json"),
    "segments": {
        "prefix": prefix,
        "tail": {**tail, "producer_seal_sha256": sha(T / "deploy_manifest.json")},
    },
}
write(DEST / "MIGRATION_DEPLOYMENT.json", deployment)
print(json.dumps(deployment, indent=2))
