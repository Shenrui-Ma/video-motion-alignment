"""Prepare only the two uncompleted drinking arms in a new immutable run root."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SOURCE = BASE / "cases/short_0358"
TARGET = HERE / "cases/short_0358"
SAM = BASE / "global_weak_host41/cases/05_real_megumi_v"
HOST = "H3_SERVER_B"
OLD_REMOTE = "/data4/researcher/h3_runs/guidance_schedule_r149_20261020/cases/short_0358"
NEW_REMOTE = "/data4/researcher/h3_runs/guidance_schedule_r149_recovery_host41_20261020/cases/short_0358"
SEGMENT = "drink_split_global_host41"
OLD_SEAL = "5d9e93c131a388758f78cda23947daca08cbd5f86bd1a3cf825bc9ffc9766054"


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def replace_once(text, old, new):
    assert text.count(old) == 1, (old, text.count(old))
    return text.replace(old, new)


assert not TARGET.exists(), "fresh recovery root required"
assert sha(SOURCE / "deploy_manifest.json") == OLD_SEAL
source_seal = read(SOURCE / "deploy_manifest.json")
for rel, evidence in source_seal["files"].items():
    assert sha(SOURCE / rel) == evidence["sha256"], rel
    out = TARGET / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE / rel, out)
for d in ["producer", "processes", "logs", "input", "output", "temp", "user", "custom_nodes"]:
    (TARGET / d).mkdir(exist_ok=True)

runtime = read(TARGET / "configs/runtime.json")
runtime.update(remote_root=NEW_REMOTE, gpu_uuid="GPU-REDACTED",
               expected_gpu_index=6, gpu_index=6, port=8644,
               profile_scope="Remaining split/global_weak only; original fixed science; GPU5 hardware failure recovery")
write(TARGET / "configs/runtime.json", runtime)
quarantine = read(TARGET / "configs/gpu_quarantine.json")
quarantine["known_requires_reset"] = [
    {"index": 4, "uuid": "GPU-REDACTED"},
    {"index": 5, "uuid": "GPU-REDACTED"},
]
write(TARGET / "configs/gpu_quarantine.json", quarantine)

contract = TARGET / "scripts/r132_contract.py"
text = contract.read_text()
text = replace_once(text, "RUN_ID = science()[\"case_order\"][0]",
                    'RUN_ID = read(ROOT / "configs/execution_segment.json")["allowed_runs"][0]')
text = replace_once(text, "def registry(root=ROOT):", "def full_registry(root=ROOT):")
text = replace_once(text, '    require(read(root / "configs/queue.json") == {"jobs": order, "finalize": True}, "queue changed")\n', "")
sam_text = (SAM / "scripts/r132_contract.py").read_text()
segment_registry = sam_text.split("def registry(root=ROOT):", 1)[1].split("\ndef validate_job(", 1)[0]
segment_registry = segment_registry.replace('jobs[r]["arm"] == "global_weak"',
                                          'jobs[r]["arm"] in ("split", "global_weak")')
segment_registry = segment_registry.replace("sam_global_weak_host41", SEGMENT)
segment_registry = segment_registry.replace('"allowed_roles": ["global_weak"]',
                                          '"allowed_roles": ["split", "global_weak"]')
segment_registry = segment_registry.replace("only original global_weak is authorized in this segment",
                                          "only original split/global_weak are authorized in this segment")
segment_registry = segment_registry.replace("len(selected) == 1", "len(selected) == 2")
text = replace_once(text, "\ndef validate_job(", "\ndef registry(root=ROOT):" + segment_registry + "\ndef validate_job(")
contract.write_text(text)

science = read(TARGET / "configs/scientific_contract.json")
all_runs = science["case_order"]
selected = all_runs[2:]
write(TARGET / "configs/execution_segment.json", {
    "schema": "r149-execution-segment-v1", "segment_id": SEGMENT,
    "allowed_runs": selected, "allowed_roles": ["split", "global_weak"],
    "all_other_registered_runs_external": True,
})
write(TARGET / "configs/queue.json", {"jobs": selected, "finalize": True})
for run in all_runs:
    p = TARGET / "configs/graphs" / (run + ".json")
    p.write_text(p.read_text().replace(OLD_REMOTE, NEW_REMOTE))

# Only administrative runner/aggregate schemas are adopted; numerical modules remain byte-identical.
runner = (SAM / "audit/root_run_batch.py").read_text()
runner = runner.replace("05_real_megumi_v", "short_0358").replace("sam_global_weak_host41", SEGMENT)
(TARGET / "audit/root_run_batch.py").write_text(runner)
verifier = (SAM / "analysis/postrun/verify_schedule.py").read_text()
verifier = verifier.replace("sam_global_weak_host41", SEGMENT)
(TARGET / "analysis/postrun/verify_schedule.py").write_text(verifier)

# Read actual source process generations and immutable completed gates. No source mutation.
query = f'''
import hashlib,json,pathlib,sys,time,subprocess
r=pathlib.Path({OLD_REMOTE!r})
sys.path.insert(0,str(r/"scripts"));import service
def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
attempt="root_r149_short_0358_attempt1"
owner=read(r/"processes/service.json")
records={{"root_wrapper":read(r/"audit/ATTEMPT1_LAUNCH.json")}}
for role in ["service","controller","supervisor","watchdog","capacity_watchdog","capacity_monitor"]:
 p=r/"processes"/(role+".json")
 if p.exists():records[role]=read(p)
generations={{}}
for role,record in records.items():
 pid=record.get("pid") or record.get("wrapper_pid")
 identity=record.get("identity") or record.get("wrapper_identity")
 if pid is None:raise ValueError("missing source process identity: "+role)
 actual=service.current_identity(pid)
 if actual==identity:raise ValueError("source generation remains live: "+role)
 generations[role]={{"pid":pid,"expected_identity":identity,"actual_identity":actual,"generation_absent":True}}
rels=["deploy_manifest.json","processes/service.json","audit/ATTEMPT1_LAUNCH.json",
 "audit/"+attempt+"/FAILURE.json","audit/"+attempt+"/CLEANUP_FAILURE.json",
 "audit/"+attempt+"/GPU5_FAILURE_DIAGNOSIS.json","audit/"+attempt+"/CAPACITY_MONITOR_EXIT.json",
 "logs/r149_short_0358_seed2026101701_split_job.json",
 "audit/router/r149_short_0358_seed2026101701_split.json"]
rels += ["analysis/postrun/short_0358/"+run+"_GATE.json" for run in {all_runs[:2]!r}]
files={{rel:{{"path":str(r/rel),"sha256":digest(r/rel),"content":read(r/rel)}} for rel in rels}}
assert files["deploy_manifest.json"]["sha256"]=={OLD_SEAL!r}
diag=files["audit/"+attempt+"/GPU5_FAILURE_DIAGNOSIS.json"]["content"]
assert "GPU requires reset" in diag["gpu5_health"]["stdout"]
assert files["logs/r149_short_0358_seed2026101701_split_job.json"]["content"]["status"]=="error"
global_run={all_runs[3]!r}
assert not (r/"logs"/(global_run+"_job.json")).exists()
raw=subprocess.run(["nvidia-smi","--query-compute-apps=gpu_uuid,pid,used_memory","--format=csv,noheader,nounits"],capture_output=True,text=True,timeout=15)
assert raw.returncode==0
numeric_pids=[int(row.split(",")[1].strip()) for row in raw.stdout.splitlines() if len(row.split(","))==3 and row.split(",")[1].strip().isdecimal()]
assert owner["pid"] not in numeric_pids
print(json.dumps({{"owner":owner,"boot_id":pathlib.Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
 "generations":generations,"files":files,"cuda_raw":raw.stdout,"observed_unix":time.time()}}))
'''
result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", HOST, "python3 -"],
                        input=query, capture_output=True, text=True, check=True)
evidence = json.loads(result.stdout)
write(HERE / "SOURCE_EVIDENCE.json", evidence)
manifest = {
    "schema": "r149-hardware-recovery-migration-v1", "source_id": "short_0358",
    "stop_kind": "hardware_failure", "created_unix": time.time(),
    "segments": {
        "host41_prefix": {
            "host": HOST, "remote_root": OLD_REMOTE, "roles": ["early", "late"],
            "run_ids": all_runs[:2], "attempt": "root_r149_short_0358_attempt1",
            "producer_seal_sha256": OLD_SEAL, "service_owner": evidence["owner"],
            "boot_id": evidence["boot_id"],
        },
        "host41_recovery": {
            "host": HOST, "remote_root": NEW_REMOTE, "roles": ["split", "global_weak"],
            "run_ids": selected, "segment_id": SEGMENT,
            "actual_producer_seal_binding": "MIGRATION_DEPLOYMENT.json",
            "aggregate_gate": "analysis/postrun/short_0358/SCHEDULE_RUNTIME_GATE.json",
            "aggregate_schema": "r149-fixed-schedule-segment-gate-v1",
            "COMPLETE_schema": "r149-schedule-segment-completion-v1",
        },
    },
    "science": {
        "seed": 2026101701, "noise_file_sha256": science["parent_noise_sha256"],
        "prompt_sha256": science["cases"][0]["prompt_sha256"],
        "conditioning_sha256": science["conditioning_sha256"],
        "geometry": science["cases"][0]["geometry"], "valid_frames": 105,
        "schedules": {c["arm"]: c["steps_zero_based"] for c in science["cases"]},
        "arms": {c["arm"]: {"alpha": c["alpha"], "physical_query_window": c["physical_query_window"],
                           "phase_displacement": 0} for c in science["cases"]},
        "NFE": 20, "blocks": [0, 50],
        "core_sha256": sha(TARGET / "extensions/H3TemporalRouter/core.py"),
        "layout_sha256": sha(TARGET / "extensions/H3TemporalRouter/layout.py"),
        "source_graph_sha256": {c["arm"]: sha(SOURCE / "configs/graphs" / (c["run_id"] + ".json")) for c in science["cases"]},
        "target_graph_sha256": {c["arm"]: sha(TARGET / "configs/graphs" / (c["run_id"] + ".json")) for c in science["cases"]},
    },
    "failure": {"failed_run": all_runs[2], "completed_callbacks": 15,
                "routed_blocks_in_failed_step": 35, "replay_from_original_noise": True,
                "source_evidence": {k: {"path": v["path"], "sha256": v["sha256"]} for k, v in evidence["files"].items()}},
    "boundary": {"original_four_arm_COMPLETE_remains_absent": True,
                 "same_persistent_service_across_segments": False},
}
write(HERE / "MIGRATION_MANIFEST.json", manifest)
write(TARGET / "configs/MIGRATION_MANIFEST.json", manifest)
prefix = {
    "schema": "r149-schedule-hardware-partial-release-v1", "passed": True,
    "source_id": "short_0358", "segment_id": "host41_prefix", "stop_kind": "hardware_failure",
    "migration_manifest_sha256": sha(HERE / "MIGRATION_MANIFEST.json"),
    "source_root": OLD_REMOTE, "producer_seal_sha256": OLD_SEAL,
    "service_owner": evidence["owner"], "completed_runs": all_runs[:2],
    "completed_roles": ["early", "late"], "remaining_runs": selected,
    "gates": {run: {k: v for k, v in evidence["files"]["analysis/postrun/short_0358/" + run + "_GATE.json"].items() if k != "content"} for run in all_runs[:2]},
    "registered_generations": evidence["generations"], "process_generation_absent": True,
    "CUDA_allocation_absent": None, "release_state": "processes_exited_gpu_unqueryable",
    "gpu_health": "requires_reset", "gpu_uuid": evidence["owner"]["gpu_uuid"],
    "raw_compute_telemetry": evidence["cuda_raw"], "original_four_arm_COMPLETE": False,
    "evidence": manifest["failure"]["source_evidence"],
    "created_unix": evidence["observed_unix"],
}
write(HERE / "PREFIX_PARTIAL_RELEASE.json", prefix)
write(TARGET / "producer/PREFIX_PARTIAL_RELEASE.json", prefix)
for run in all_runs[:2]:
    g = evidence["files"]["analysis/postrun/short_0358/" + run + "_GATE.json"]["content"]
    assert g["passed"] and g["producer_seal_sha256"] == OLD_SEAL and g["service_owner"] == evidence["owner"]
for folder in ["extensions"]:
    for p in (SOURCE / folder).rglob("*.py"):
        assert sha(p) == sha(TARGET / p.relative_to(SOURCE))
for rel in ["configs/scientific_contract.json", "configs/CONDITION_CACHE.json", "design/conditioning.json"]:
    assert sha(SOURCE / rel) == sha(TARGET / rel)
for helper in ["check_fresh_paths.py", "watch_queue.py"]:
    shutil.copy2(SOURCE / "producer" / helper, TARGET / "producer" / helper)
sys.path.insert(0, str(TARGET / "scripts"))
import r132_contract
assert r132_contract.registry()[1] == selected
import execution_gate
execution_gate.seal(TARGET)
deployment = {
    "schema": "r149-hardware-recovery-deployment-v1", "source_id": "short_0358",
    "migration_manifest_sha256": sha(HERE / "MIGRATION_MANIFEST.json"),
    "prefix_partial_release_sha256": sha(HERE / "PREFIX_PARTIAL_RELEASE.json"),
    "segments": {k: {p: v for p, v in seg.items() if p in ["host", "remote_root", "roles", "run_ids", "producer_seal_sha256"]}
                 for k, seg in manifest["segments"].items()}, "created_unix": time.time(),
}
deployment["segments"]["host41_recovery"]["producer_seal_sha256"] = sha(TARGET / "deploy_manifest.json")
write(HERE / "MIGRATION_DEPLOYMENT.json", deployment)
write(TARGET / "producer/SCIENTIFIC_EQUIVALENCE.json", {
    "passed": True, "numerical_modules_byte_identical": True,
    "scientific_contract_byte_identical": True, "conditioning_byte_identical": True,
    "original_noise_reused": True, "only_completed_prefix_excluded_from_execution": True,
    "old_seal": OLD_SEAL, "new_seal": sha(TARGET / "deploy_manifest.json"),
    "actual_registry": selected, "no_GPU_launched": True,
})
print(json.dumps({"root": str(TARGET), "seal": sha(TARGET / "deploy_manifest.json"),
                  "files": len(read(TARGET / "deploy_manifest.json")["files"]), "registry": selected}))
