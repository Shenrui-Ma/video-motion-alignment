"""Continue the five unsubmitted conditions after the Native review idle stop."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import time

P = Path(__file__).resolve().parents[1]
S = P / "cases/firefly06"
H = P / "firefly_recovery_host41"
T = H / "cases/firefly06"
OLD = "/data4/researcher/h3_runs/guidance_schedule_r150_20261021/cases/firefly06"
NEW = "/data4/researcher/h3_runs/guidance_schedule_r150_firefly_recovery_host41_20261021/cases/firefly06"
SEAL = "d2f7ce33c8ca98c52f9f9d0b80205777b49cc23bee88cb337ed2f94a73111d6a"
ATTEMPT = "root_r150_firefly06_host41_attempt1"
SEGMENT = "firefly06_five_after_native"


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


assert sha(S / "deploy_manifest.json") == SEAL and not T.exists()
for rel, item in read(S / "deploy_manifest.json")["files"].items():
    assert sha(S / rel) == item["sha256"], rel
    dest = T / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(S / rel, dest)
for rel in ("producer", "logs", "processes", "input", "output", "temp", "user",
            "custom_nodes", "audit/router", "audit/x0"):
    (T / rel).mkdir(parents=True, exist_ok=True)
runtime = read(T / "configs/runtime.json")
runtime.update(remote_root=NEW, port=8660,
               profile_scope="Five unsubmitted Firefly conditions; completed Native retained")
write(T / "configs/runtime.json", runtime)
science = read(T / "configs/scientific_contract.json")
runs = science["case_order"]
selected = runs[1:]
roles = ["fixed", "early", "late", "split", "global_weak"]
assert [c["arm"] for c in science["cases"]] == ["native"] + roles
for path in (T / "configs/graphs").glob("*.json"):
    path.write_text(path.read_text().replace(OLD, NEW))
text = (T / "scripts/r132_contract.py").read_text()
text = text.replace('RUN_ID = science()["case_order"][0]',
                    'RUN_ID = read(ROOT / "configs/execution_segment.json")["allowed_runs"][0]')
text = text.replace("def registry(root=ROOT):", "def full_registry(root=ROOT):")
text = text.replace('    require(read(root / "configs/queue.json") == {"jobs": order, "finalize": True}, "queue changed")\n', "")
template = (P / "sam_parallel_host9/cases/sam07/scripts/r132_contract.py").read_text()
registry = template.split("def registry(root=ROOT):", 1)[1].split("\ndef validate_job(", 1)[0]
registry = registry.replace("('split', 'global_weak')", repr(tuple(roles)))
registry = registry.replace("len(selected) == 2", "len(selected) == 5")
registry = registry.replace("sam07_tail_gpu2", SEGMENT)
text = text.replace("\ndef validate_job(", "\ndef registry(root=ROOT):" + registry + "\ndef validate_job(")
(T / "scripts/r132_contract.py").write_text(text)
write(T / "configs/execution_segment.json", {
    "schema": "r149-execution-segment-v1", "segment_id": SEGMENT,
    "allowed_runs": selected, "allowed_roles": roles,
    "all_other_registered_runs_external": True,
})
write(T / "configs/queue.json", {"jobs": selected, "finalize": True})
path = T / "audit/root_run_batch.py"
text = path.read_text().replace(
    "{'schema':'r149-schedule-completion-v1','passed':True,",
    "{'schema':'r149-schedule-segment-completion-v1','segment_id':" + repr(SEGMENT) +
    ",'migration_manifest_sha256':sha(ROOT/'configs/MIGRATION_MANIFEST.json'),'passed':True,")
path.write_text(text)
path = T / "analysis/postrun/verify_schedule.py"
text = path.read_text().replace(
    '{"schema": "r149-fixed-schedule-runtime-gate-v1", "passed": True,',
    '{"schema": "r149-fixed-schedule-segment-gate-v1", "segment_id": ' + repr(SEGMENT) +
    ', "migration_manifest_sha256": sha(ROOT / "configs/MIGRATION_MANIFEST.json"), "passed": True,')
path.write_text(text)
path = T / "tests/test_schedule.py"
text = path.read_text().replace("len(jobs), 6", "len(jobs), 5")
text = text.replace("['native', 'fixed', 'early', 'late', 'split', 'global_weak']", repr(roles))
text = text.replace("run_queue.subprocess.run.call_count, 7", "run_queue.subprocess.run.call_count, 6")
path.write_text(text)

query = '''
from pathlib import Path
import hashlib,json,sys,time
r=Path(OLD);sys.path.insert(0,str(r/"scripts"));import service
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
owner=read(r/"processes/service.json");wrapper=read(r/"audit/ATTEMPT1_LAUNCH.json")
assert service.current_identity(owner["pid"]) is None
assert service.current_identity(wrapper["pid"]) is None
assert not any(x["pid"]==owner["pid"] for x in service.compute_processes())
cleanup=read(r/"processes/cleanup.json")
assert cleanup["process_absent"] and cleanup["own_compute_absent"]
stop=read(r/"audit/watchdog_runtime_v2/STOP_REASON.json")
assert stop["reason"]=="bounded_idle_review_expired"
for run in RUNS[1:]:
 for rel in ["logs/"+run+"_job.json","audit/router/"+run+".json"]:
  assert not(r/rel).exists(),rel
rels=["deploy_manifest.json","processes/service.json","processes/cleanup.json",
      "audit/ATTEMPT1_LAUNCH.json","audit/"+ATTEMPT+"/FAILURE.json",
      "audit/watchdog_runtime_v2/STOP_REASON.json","audit/NATIVE_VISUAL_REVIEW_REQUEST.json",
      "audit/NATIVE_VISUAL_REVIEW.json",
      "analysis/postrun/firefly06/"+RUNS[0]+"_GATE.json"]
files={rel:{"path":str(r/rel),"sha256":sha(r/rel),"content":read(r/rel)} for rel in rels}
print(json.dumps({"observed_unix":time.time(),"owner":owner,"wrapper":wrapper,"files":files,
                 "exact_generations_absent":True,"CUDA_allocation_absent":True}))
'''
code = "\n".join(k + "=" + repr(v) for k, v in
                 {"OLD": OLD, "ATTEMPT": ATTEMPT, "RUNS": runs}.items()) + "\n" + query
result = subprocess.run(["ssh", "H3_SERVER_B", "python3 -"],
                        input=code, text=True, capture_output=True, check=True)
evidence = json.loads(result.stdout)
write(H / "SOURCE_EVIDENCE.json", evidence)
native = evidence["files"]["analysis/postrun/firefly06/" + runs[0] + "_GATE.json"]["content"]
assert native["passed"] and native["producer_seal_sha256"] == SEAL
review = evidence["files"]["audit/NATIVE_VISUAL_REVIEW.json"]["content"]
assert review["passed"] and review["task_completed"]
manifest = {
    "schema": "r150-completed-native-recovery-v1", "source_id": "firefly06",
    "stop_kind": "administrative_idle_review_expired", "created_unix": time.time(),
    "segments": {
        "prefix": {"host": runtime["host"], "remote_root": OLD, "attempt": ATTEMPT,
                   "roles": ["native"], "run_ids": runs[:1], "producer_seal_sha256": SEAL,
                   "service_owner": evidence["owner"]},
        "recovery": {"host": runtime["host"], "remote_root": NEW, "roles": roles,
                     "run_ids": selected, "segment_id": SEGMENT,
                     "aggregate_gate": "analysis/postrun/firefly06/SCHEDULE_RUNTIME_GATE.json",
                     "aggregate_schema": "r149-fixed-schedule-segment-gate-v1",
                     "COMPLETE_schema": "r149-schedule-segment-completion-v1"},
    },
    "science": {
        "scientific_contract_sha256": sha(S / "configs/scientific_contract.json"),
        "condition_cache_sha256": sha(S / "configs/CONDITION_CACHE.json"),
        "noise_file_sha256": science["parent_noise_sha256"],
        "source_graph_sha256": {c["arm"]: sha(S / "configs/graphs" / (c["run_id"] + ".json"))
                                for c in science["cases"]},
        "target_graph_sha256": {c["arm"]: sha(T / "configs/graphs" / (c["run_id"] + ".json"))
                                for c in science["cases"]},
    },
    "source_evidence": {k: {"path": v["path"], "sha256": v["sha256"]}
                        for k, v in evidence["files"].items()},
    "original_six_role_COMPLETE_absent": True,
}
write(H / "MIGRATION_MANIFEST.json", manifest)
write(T / "configs/MIGRATION_MANIFEST.json", manifest)
partial = {
    "schema": "r150-native-partial-release-v1", "passed": True, "source_id": "firefly06",
    "stop_kind": manifest["stop_kind"], "source_root": OLD, "producer_seal_sha256": SEAL,
    "migration_manifest_sha256": sha(H / "MIGRATION_MANIFEST.json"),
    "completed_roles": ["native"], "completed_runs": runs[:1],
    "remaining_runs": selected, "service_owner": evidence["owner"],
    "exact_generations_absent": True, "CUDA_allocation_absent": True,
    "native_visual_review_passed": True, "source_evidence": manifest["source_evidence"],
    "original_full_COMPLETE": False, "created_unix": evidence["observed_unix"],
}
write(H / "PREFIX_PARTIAL_RELEASE.json", partial)
write(T / "producer/PREFIX_PARTIAL_RELEASE.json", partial)
for rel in ("configs/scientific_contract.json", "configs/CONDITION_CACHE.json",
            "design/conditioning.json"):
    assert sha(S / rel) == sha(T / rel)
for rel, digest in read(T / "configs/numerical_reuse.json").items():
    assert sha(S / rel) == sha(T / rel) == digest
for name in ("check_fresh_paths.py", "watch_queue.py"):
    shutil.copy2(S / "producer" / name, T / "producer" / name)
subprocess.run(["python3", "scripts/execution_gate.py", "seal"], cwd=T, check=True)
write(H / "MIGRATION_DEPLOYMENT.json", {
    "schema": "r150-completed-native-recovery-deployment-v1", "source_id": "firefly06",
    "migration_manifest_sha256": sha(H / "MIGRATION_MANIFEST.json"),
    "prefix_partial_release_sha256": sha(H / "PREFIX_PARTIAL_RELEASE.json"),
    "segments": {"prefix": manifest["segments"]["prefix"],
                 "recovery": {**manifest["segments"]["recovery"],
                              "producer_seal_sha256": sha(T / "deploy_manifest.json")}},
})
print(json.dumps({"seal": sha(T / "deploy_manifest.json"), "roles": roles}))
