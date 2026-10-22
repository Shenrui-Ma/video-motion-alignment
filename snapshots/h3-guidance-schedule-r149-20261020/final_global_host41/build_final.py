"""Single remaining arm; exact independent 8189 service allowance, no numerical changes."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SOURCE = BASE / "recovery_host41/cases/short_0358"
TARGET = HERE / "cases/short_0358"
OLD = "/data4/researcher/h3_runs/guidance_schedule_r149_recovery_host41_20261020/cases/short_0358"
NEW = "/data4/researcher/h3_runs/guidance_schedule_r149_final_global_host41_20261020/cases/short_0358"
HOST = "H3_SERVER_B"
SEGMENT = "drink_final_global_host41"
PRIOR_SEAL = "dd45b20fe8ac78892b59244574c120783cdebfcbaa9a0fbf92d834868aa87cf3"
SPLIT = "r149_short_0358_seed2026101701_split"
GLOBAL = "r149_short_0358_seed2026101701_global_weak"


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n")


assert not TARGET.exists()
assert sha(SOURCE / "deploy_manifest.json") == PRIOR_SEAL
for rel, item in read(SOURCE / "deploy_manifest.json")["files"].items():
    assert sha(SOURCE / rel) == item["sha256"]
    p = TARGET / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE / rel, p)
for folder in ["producer", "logs", "processes", "input", "output", "temp", "user", "custom_nodes"]:
    (TARGET / folder).mkdir(exist_ok=True)
runtime = read(TARGET / "configs/runtime.json")
runtime.update(remote_root=NEW, port=8645, profile_scope="Only remaining original global_weak; independent 8189 exact peer")
write(TARGET / "configs/runtime.json", runtime)
for p in (TARGET / "configs/graphs").glob("*.json"):
    p.write_text(p.read_text().replace(OLD, NEW))
for rel in ["scripts/r132_contract.py", "analysis/postrun/verify_schedule.py", "audit/root_run_batch.py"]:
    p = TARGET / rel
    s = p.read_text().replace("drink_split_global_host41", SEGMENT)
    if rel.endswith("r132_contract.py"):
        s = s.replace('jobs[r]["arm"] in ("split", "global_weak")', 'jobs[r]["arm"] == "global_weak"')
        s = s.replace('"allowed_roles": ["split", "global_weak"]', '"allowed_roles": ["global_weak"]')
        s = s.replace("only original split/global_weak", "only original global_weak")
        s = s.replace("len(selected) == 2", "len(selected) == 1")
    p.write_text(s)
write(TARGET / "configs/execution_segment.json", {
    "schema": "r149-execution-segment-v1", "segment_id": SEGMENT,
    "allowed_runs": [GLOBAL], "allowed_roles": ["global_weak"], "all_other_registered_runs_external": True})
write(TARGET / "configs/queue.json", {"jobs": [GLOBAL], "finalize": True})
p = TARGET / "tests/test_schedule.py"
s = p.read_text().replace("len(jobs), 2", "len(jobs), 1").replace('["split", "global_weak"])', '["global_weak"])')
s = s.replace("run_queue.subprocess.run.call_count, 3", "run_queue.subprocess.run.call_count, 2")
p.write_text(s)
p = TARGET / "tests/test_short0358_recipe.py"
s = p.read_text().replace('["split", "global_weak"])', '["global_weak"])').replace("only original split/global_weak", "only original global_weak")
p.write_text(s)

query = f'''
import pathlib,json,hashlib,sys,time,urllib.request
r=pathlib.Path({OLD!r});sys.path.insert(0,str(r/"scripts"));import service
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
owner=read(r/"processes/service.json");attempt="root_r149_drink_recovery_host41_attempt1"
records={{"root_wrapper":read(r/"audit/RECOVERY_ATTEMPT1_LAUNCH.json")}}
for role in ["service","controller","supervisor","watchdog","capacity_watchdog","capacity_monitor"]:
 p=r/"processes"/(role+".json")
 if p.exists():records[role]=read(p)
generations={{}}
for role,x in records.items():
 actual=service.current_identity(x["pid"]);assert actual!=x["identity"],role
 generations[role]={{"pid":x["pid"],"expected_identity":x["identity"],"actual_identity":actual,"generation_absent":True}}
rels=["deploy_manifest.json","processes/service.json","processes/cleanup.json",
 "audit/RECOVERY_ATTEMPT1_LAUNCH.json","audit/"+attempt+"/FAILURE.json",
 "audit/"+attempt+"/CAPACITY_MONITOR_EXIT.json","analysis/postrun/short_0358/"+{SPLIT!r}+"_GATE.json"]
files={{rel:{{"path":str(r/rel),"sha256":sha(r/rel),"content":read(r/rel)}} for rel in rels}}
assert files["deploy_manifest.json"]["sha256"]=={PRIOR_SEAL!r}
cleanup=files["processes/cleanup.json"]["content"]
assert cleanup["service_record"]==owner and cleanup["process_absent"] and cleanup["own_compute_absent"] and cleanup["child_compute_absent"]
assert "Unexpected own compute identity 117572" in files["audit/"+attempt+"/FAILURE.json"]["content"]["error"]
g=files["analysis/postrun/short_0358/"+{SPLIT!r}+"_GATE.json"]["content"]
assert g["passed"] and g["service_owner"]==owner and g["producer_seal_sha256"]=={PRIOR_SEAL!r}
assert not (r/"logs"/({GLOBAL!r}+"_job.json")).exists()
peer=service.external_identity(117572)
assert peer["uid"]==1004 and peer["start_ticks"]=="1301065" and peer["cmdline_sha256"]=="6e8c72fb39a4316ec9c918bc009c864ec61ae221550e6d3932aa9c806dc1acda"
assert str(pathlib.Path("/proc/117572/cwd").resolve())=="/data3/researcher/ComfyUI"
rows=service.compute_processes();assert not any(x["pid"]==owner["pid"] for x in rows)
assert any(x["pid"]==117572 and x["gpu_uuid"]=="GPU-REDACTED" for x in rows)
with urllib.request.urlopen("http://127.0.0.1:8189/queue",timeout=10) as f:q=json.load(f)
print(json.dumps({{"owner":owner,"generations":generations,"files":files,"observed_unix":time.time(),
 "boot_id":pathlib.Path("/proc/sys/kernel/random/boot_id").read_text().strip(),"peer":peer,
 "peer_cwd":"/data3/researcher/ComfyUI","queue_counts":{{k:len(v) for k,v in q.items()}}}}))
'''
evidence = json.loads(subprocess.run(["ssh", "-o", "BatchMode=yes", HOST, "python3 -"],
                                    input=query, text=True, capture_output=True, check=True).stdout)
write(HERE / "SPLIT_SOURCE_EVIDENCE.json", evidence)
peer = {"boot_id": evidence["boot_id"], "pid": 117572, "identity": evidence["peer"],
        "gpu_uuid": "GPU-REDACTED", "port": 8189,
        "source_cwd": evidence["peer_cwd"], "read_only_queue_counts": evidence["queue_counts"],
        "scope": "Protected independent user ComfyUI; do not signal or change configuration"}
write(TARGET / "configs/readonly_peer.json", peer)
parent_manifest = read(BASE / "recovery_host41/MIGRATION_MANIFEST.json")
manifest = {
    "schema": "r149-three-segment-recovery-migration-v1", "source_id": "short_0358",
    "created_unix": time.time(), "segment_order": ["host41_prefix", "host41_split", "host41_global"],
    "segments": {
        "host41_prefix": parent_manifest["segments"]["host41_prefix"],
        "host41_split": {"host": HOST, "remote_root": OLD, "roles": ["split"], "run_ids": [SPLIT],
                         "producer_seal_sha256": PRIOR_SEAL, "service_owner": evidence["owner"],
                         "attempt": "root_r149_drink_recovery_host41_attempt1"},
        "host41_global": {"host": HOST, "remote_root": NEW, "roles": ["global_weak"],
                          "run_ids": [GLOBAL], "segment_id": SEGMENT,
                          "actual_producer_seal_binding": "MIGRATION_DEPLOYMENT.json",
                          "aggregate_gate": "analysis/postrun/short_0358/SCHEDULE_RUNTIME_GATE.json",
                          "aggregate_schema": "r149-fixed-schedule-segment-gate-v1",
                          "COMPLETE_schema": "r149-schedule-segment-completion-v1"},
    },
    "prior_hardware_recovery": {
        "manifest_file": str(BASE / "recovery_host41/MIGRATION_MANIFEST.json"),
        "manifest_sha256": sha(BASE / "recovery_host41/MIGRATION_MANIFEST.json"),
        "prefix_release_file": str(BASE / "recovery_host41/PREFIX_PARTIAL_RELEASE.json"),
        "prefix_release_sha256": sha(BASE / "recovery_host41/PREFIX_PARTIAL_RELEASE.json"),
        "source_evidence_file": str(BASE / "recovery_host41/SOURCE_EVIDENCE.json"),
        "source_evidence_sha256": sha(BASE / "recovery_host41/SOURCE_EVIDENCE.json"),
    },
    "science": parent_manifest["science"],
    "boundary": {"stop_kind": "independent_peer_admission", "original_four_arm_COMPLETE_remains_absent": True,
                 "recovery_two_arm_COMPLETE_remains_absent": True, "same_persistent_service_across_segments": False},
    "readonly_peer": peer,
}
manifest["science"]["target_graph_sha256"] = {
    c["arm"]: sha(TARGET / "configs/graphs" / (c["run_id"] + ".json"))
    for c in read(TARGET / "configs/scientific_contract.json")["cases"]}
write(HERE / "MIGRATION_MANIFEST.json", manifest)
write(TARGET / "configs/MIGRATION_MANIFEST.json", manifest)
partial = {
    "schema": "r149-schedule-admission-partial-release-v1", "passed": True, "source_id": "short_0358",
    "segment_id": "host41_split", "stop_kind": "independent_peer_admission",
    "migration_manifest_sha256": sha(HERE / "MIGRATION_MANIFEST.json"), "source_root": OLD,
    "service_owner": evidence["owner"], "producer_seal_sha256": PRIOR_SEAL,
    "completed_runs": [SPLIT], "completed_roles": ["split"], "remaining_runs": [GLOBAL],
    "registered_generations": evidence["generations"], "process_generation_absent": True,
    "CUDA_allocation_absent": True, "release_state": "processes_and_cuda_released",
    "evidence": {k: {"path": v["path"], "sha256": v["sha256"]} for k, v in evidence["files"].items()},
    "original_segment_COMPLETE": False, "created_unix": evidence["observed_unix"],
}
write(HERE / "SPLIT_PARTIAL_RELEASE.json", partial)
write(TARGET / "producer/SPLIT_PARTIAL_RELEASE.json", partial)
for rel in ["check_fresh_paths.py", "watch_queue.py"]:
    shutil.copy2(SOURCE / "producer" / rel, TARGET / "producer" / rel)
for p in (SOURCE / "extensions").rglob("*.py"):
    assert sha(p) == sha(TARGET / p.relative_to(SOURCE))
assert sha(TARGET / "configs/scientific_contract.json") == sha(SOURCE / "configs/scientific_contract.json")
sys.path.insert(0, str(TARGET / "scripts"))
import r132_contract
import execution_gate
assert r132_contract.registry()[1] == [GLOBAL]
execution_gate.seal(TARGET)
seal = sha(TARGET / "deploy_manifest.json")
deployment = {
    "schema": "r149-three-segment-recovery-deployment-v1", "source_id": "short_0358",
    "migration_manifest_sha256": sha(HERE / "MIGRATION_MANIFEST.json"),
    "split_partial_release_sha256": sha(HERE / "SPLIT_PARTIAL_RELEASE.json"),
    "segments": {k: {x: y for x, y in v.items() if x in ["host", "remote_root", "roles", "run_ids", "producer_seal_sha256"]}
                 for k, v in manifest["segments"].items()}, "created_unix": time.time()}
deployment["segments"]["host41_global"]["producer_seal_sha256"] = seal
write(HERE / "MIGRATION_DEPLOYMENT.json", deployment)
write(TARGET / "producer/SCIENTIFIC_EQUIVALENCE.json", {
    "passed": True, "numerical_modules_byte_identical": True, "scientific_contract_byte_identical": True,
    "conditioning_and_noise_unchanged": True, "registry": [GLOBAL],
    "previous_seal": PRIOR_SEAL, "new_seal": seal, "no_GPU_launched": True})
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as archive:
    for p in sorted(TARGET.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and "inputs" not in p.relative_to(TARGET).parts:
            archive.add(p, arcname=str(p.relative_to(TARGET)))
cmd = "python3 -c 'import pathlib,sys,tarfile; p=pathlib.Path(\"" + NEW + "\"); p.mkdir(parents=True,exist_ok=False); tarfile.open(fileobj=sys.stdin.buffer,mode=\"r|gz\").extractall(p,filter=\"data\")'"
subprocess.run(["ssh", "-o", "BatchMode=yes", HOST, cmd], input=buf.getvalue(), check=True)
print(json.dumps({"root": str(TARGET), "remote_root": NEW, "seal": seal,
                  "manifest": sha(HERE / "MIGRATION_MANIFEST.json"),
                  "deployment": sha(HERE / "MIGRATION_DEPLOYMENT.json"),
                  "partial": sha(HERE / "SPLIT_PARTIAL_RELEASE.json")}))
