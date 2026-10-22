"""Prepare the authorized four-plus-two Sam queue partition before any Sam POST."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import time

P = Path(__file__).resolve().parents[1]
S = P / "host9/cases/sam07"
H = P / "sam_parallel_host9"
T = H / "cases/sam07"
OLD = "/home/researcher/h3_runs/guidance_schedule_r150_host9_20261021/cases/sam07"
NEW = "/home/researcher/h3_runs/guidance_schedule_r150_sam_tail_host9_20261021/cases/sam07"
EXPECTED = "ebd1cf87931a379cac0a0bbfd3c152257fec8361022813547c123604b4a166a3"


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


assert sha(S / "deploy_manifest.json") == EXPECTED
assert not T.exists()
old_manifest = read(S / "deploy_manifest.json")
archive = H / "PREPARED_SIX_ROLE_SOURCE"
for rel, value in old_manifest["files"].items():
    assert sha(S / rel) == value["sha256"], rel
    for dest in (T / rel, archive / rel):
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(S / rel, dest)
shutil.copy2(S / "deploy_manifest.json", archive / "deploy_manifest.json")
for name in ("producer", "logs", "processes", "input", "output", "temp", "user",
             "custom_nodes", "audit/router", "audit/x0"):
    (T / name).mkdir(parents=True, exist_ok=True)
science = read(S / "configs/scientific_contract.json")
roles = [c["arm"] for c in science["cases"]]
runs = science["case_order"]
assert roles == ["native", "fixed", "early", "late", "split", "global_weak"]
rt = read(T / "configs/runtime.json")
rt.update(remote_root=NEW, port=8658, gpu_index=2, expected_gpu_index=2,
          gpu_uuid="GPU-REDACTED",
          profile_scope="Sam07 split/global after matching-cache Native visual approval and Musk release")
write(T / "configs/runtime.json", rt)
for f in (T / "configs/graphs").glob("*.json"):
    f.write_text(f.read_text().replace(OLD, NEW))
segments = {
    "prefix": {"segment_id": "sam07_prefix_gpu3", "host": "H3_SERVER_A", "remote_root": OLD,
               "roles": roles[:4], "run_ids": runs[:4], "gpu_index": 3},
    "tail": {"segment_id": "sam07_tail_gpu2", "host": "H3_SERVER_A", "remote_root": NEW,
             "roles": roles[4:], "run_ids": runs[4:], "gpu_index": 2},
}
for value in segments.values():
    value.update(aggregate_gate="analysis/postrun/sam07/SCHEDULE_RUNTIME_GATE.json",
                 aggregate_schema="r149-fixed-schedule-segment-gate-v1",
                 COMPLETE_schema="r149-schedule-segment-completion-v1")
manifest = {
    "schema": "r150-planned-parallel-segments-v1", "source_id": "sam07",
    "created_unix": time.time(), "segments": segments,
    "previous_unstarted_full_seal_sha256": EXPECTED,
    "all_roles": roles, "all_run_ids": runs,
    "science": {
        "scientific_contract_sha256": sha(S / "configs/scientific_contract.json"),
        "condition_cache_sha256": sha(S / "configs/CONDITION_CACHE.json"),
        "condition_description_sha256": sha(S / "design/conditioning.json"),
        "noise_file_sha256": science["parent_noise_sha256"],
        "native_run_id": runs[0],
        "source_graph_sha256": {c["arm"]: sha(S / "configs/graphs" / (c["run_id"] + ".json"))
                                for c in science["cases"]},
        "tail_graph_sha256": {c["arm"]: sha(T / "configs/graphs" / (c["run_id"] + ".json"))
                              for c in science["cases"]},
    },
    "tail_admission": {
        "Musk_actual_COMPLETE_and_exact_release": True,
        "matching_cache_native_visual_pass_required": True,
        "prefix_may_still_be_running": True,
        "own_host9_max_GPU_cards": 2,
        "tail_once_only": True,
    },
    "completion": "Two real segment aggregates and exact releases cover six unique roles.",
}
write(H / "MIGRATION_MANIFEST.json", manifest)

for root, name in [(S, "prefix"), (T, "tail")]:
    seg = segments[name]
    write(root / "configs/MIGRATION_MANIFEST.json", manifest)
    write(root / "configs/execution_segment.json", {
        "schema": "r149-execution-segment-v1", "segment_id": seg["segment_id"],
        "allowed_runs": seg["run_ids"], "allowed_roles": seg["roles"],
        "all_other_registered_runs_external": True,
    })
    write(root / "configs/queue.json", {"jobs": seg["run_ids"], "finalize": True})
    path = root / "scripts/r132_contract.py"
    text = path.read_text()
    assert text.count("def registry(root=ROOT):") == 1
    text = text.replace('RUN_ID = science()["case_order"][0]',
                        'RUN_ID = read(ROOT / "configs/execution_segment.json")["allowed_runs"][0]')
    text = text.replace("def registry(root=ROOT):", "def full_registry(root=ROOT):")
    line = '    require(read(root / "configs/queue.json") == {"jobs": order, "finalize": True}, "queue changed")\n'
    assert text.count(line) == 1
    text = text.replace(line, "")
    insert = '''
def registry(root=ROOT):
    root = Path(root)
    jobs, order = full_registry(root)
    segment = read(root / "configs/execution_segment.json")
    selected = [r for r in order if jobs[r]["arm"] in ROLES]
    require(segment == {"schema": "r149-execution-segment-v1", "segment_id": SEGMENT,
                        "allowed_runs": selected, "allowed_roles": list(ROLES),
                        "all_other_registered_runs_external": True}, "execution segment changed")
    require(len(selected) == COUNT and [jobs[r]["arm"] for r in selected] == list(ROLES),
            "registered segment roles changed")
    require(read(root / "configs/queue.json") == {"jobs": selected, "finalize": True},
            "segment queue changed")
    return {r: jobs[r] for r in selected}, selected

'''.replace("ROLES", repr(tuple(seg["roles"]))).replace("SEGMENT", repr(seg["segment_id"])).replace("COUNT", str(len(seg["roles"])))
    text = text.replace("\ndef validate_job(run, root=ROOT):", "\n" + insert + "\ndef validate_job(run, root=ROOT):")
    compile(text, str(path), "exec")
    path.write_text(text)
    path = root / "analysis/postrun/verify_schedule.py"
    text = path.read_text()
    needle = '{"schema": "r149-fixed-schedule-runtime-gate-v1", "passed": True,'
    assert text.count(needle) == 1
    text = text.replace(needle, '{"schema": "r149-fixed-schedule-segment-gate-v1", "segment_id": ' +
                        repr(seg["segment_id"]) + ', "migration_manifest_sha256": sha(ROOT / "configs/MIGRATION_MANIFEST.json"), "passed": True,')
    path.write_text(text)
    path = root / "audit/root_run_batch.py"
    text = path.read_text()
    needle = "{'schema':'r149-schedule-completion-v1','passed':True,"
    assert text.count(needle) == 1
    text = text.replace(needle, "{'schema':'r149-schedule-segment-completion-v1','segment_id':" +
                        repr(seg["segment_id"]) + ",'migration_manifest_sha256':sha(ROOT/'configs/MIGRATION_MANIFEST.json'),'passed':True,")
    peer = NEW if name == "prefix" else OLD
    text = text.replace("explicit_peers={Path(p) for p in [",
                        "explicit_peers={Path(p) for p in [" + repr(peer) + ", ")
    path.write_text(text)
    path = root / "tests/test_schedule.py"
    text = path.read_text().replace("import service, job, run_queue,", "import native_review_gate\nimport service, job, run_queue,")
    text = text.replace("self.assertEqual(len(jobs), 6)", "self.assertEqual(len(jobs), " + str(len(seg["roles"])) + ")")
    text = text.replace("['native', 'fixed', 'early', 'late', 'split', 'global_weak'])",
                        repr(seg["roles"]) + ")")
    text = text.replace("run_queue.subprocess.run.call_count, 7",
                        "run_queue.subprocess.run.call_count, " + str(len(seg["roles"]) + 1))
    text = text.replace('(run_queue, "record_resources", {}),',
                        '(run_queue, "record_resources", {}),\n                (native_review_gate, "wait_native_review", {}),')
    path.write_text(text)
    for rel in ("configs/scientific_contract.json", "configs/CONDITION_CACHE.json",
                "design/conditioning.json"):
        assert sha(root / rel) == sha(archive / rel)
    for rel, digest in read(root / "configs/numerical_reuse.json").items():
        assert sha(root / rel) == digest
    subprocess.run(["python3", "scripts/execution_gate.py", "seal"], cwd=root, check=True)

deployment = {
    "schema": "r150-planned-parallel-deployment-v1", "source_id": "sam07",
    "migration_manifest_sha256": sha(H / "MIGRATION_MANIFEST.json"),
    "segments": {
        name: {**segments[name], "producer_seal_sha256": sha(root / "deploy_manifest.json")}
        for root, name in [(S, "prefix"), (T, "tail")]
    }, "created_unix": time.time(),
}
write(H / "MIGRATION_DEPLOYMENT.json", deployment)
print(json.dumps(deployment, indent=2))
