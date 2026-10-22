"""Administrative boundary tool; never signals a process or modifies a sealed file."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request
import uuid


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def atomic(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def validate_boundary(manifest, owner, actual, job, queue, global_exists, approval):
    source = manifest["segments"]["host9_prefix"]
    require(owner == source["service_owner"] and actual == owner["identity"],
            "source service generation differs")
    require(not global_exists, "global_weak has already been initialized")
    split = source["run_ids"][-1]
    require(job["name"] == split and job["service_pid"] == owner["pid"] and
            job["service_identity"] == owner["identity"] and job.get("prompt_id"),
            "split has not been accepted by this exact service")
    require(any(row[1] == job["prompt_id"] for row in queue["queue_running"]),
            "split must be running before future admission withdrawal")
    require(not queue["queue_pending"], "unexpected pending job")
    require(approval.get("root_approved") is True, "future admission already withdrawn")


def validate_partial(manifest, owner, gates, cleanup, failure, request, monitor):
    source = manifest["segments"]["host9_prefix"]
    require(owner == source["service_owner"], "partial owner changed")
    require(set(gates) == set(source["run_ids"]), "three prefix gates required")
    for role, run in zip(source["roles"], source["run_ids"]):
        gate = gates[run]
        require(gate["passed"] is True and gate["service_owner"] == owner and
                gate["producer_seal_sha256"] == source["producer_seal_sha256"] and
                gate["run_id"] == run and gate["role"] == role and
                gate["NFE"] == gate["Euler_updates"] == 20 and
                gate["routed_blocks"] == 450 and gate["alpha"] == 1 and
                gate["phase_displacement"] == 0 and gate["physical_query_window"] == [50, 65] and
                gate["noise_sha256"] == manifest["science"]["noise_file_sha256"],
                "prefix job evidence differs")
    require(cleanup["service_record"] == owner and cleanup["pid"] == owner["pid"] and
            cleanup["process_absent"] and cleanup["own_compute_absent"] and
            cleanup["child_compute_absent"], "exact source cleanup not certified")
    require("root admission pending" in failure["error"] and
            failure["unix"] >= request["created_unix"],
            "source did not stop through the planned future admission boundary")
    require(monitor["exit_code"] == 0 and monitor["exact_generation_absent"],
            "source capacity monitor did not exit normally")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["withdraw", "collect"])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    manifest = read(args.manifest)
    manifest_sha = sha(args.manifest)
    require(sha(__file__) == manifest["partial_release_tool_sha256"],
            "partial-release tool differs from the reviewed manifest")
    source = manifest["segments"]["host9_prefix"]
    root = Path(source["remote_root"])
    require(Path("/proc/sys/kernel/random/boot_id").read_text().strip() == source["boot_id"],
            "source boot changed")
    require(sha(root / "deploy_manifest.json") == source["producer_seal_sha256"],
            "source producer seal changed")
    sys.path.insert(0, str(root / "scripts"))
    import service
    require(service.RUN == root, "wrong source service module")
    owner = read(root / "processes/service.json")
    require(owner == source["service_owner"], "source owner changed")
    folder = root / "audit/partial_release_global_weak_migration"
    global_run = manifest["segments"]["host41_global"]["run_ids"][0]
    global_paths = [
        root / "logs" / (global_run + "_job.json"),
        root / "audit/router" / (global_run + ".json"),
        root / "analysis/postrun/05_real_megumi_v" / (global_run + "_GATE.json"),
    ]
    require(not any(path.exists() for path in global_paths),
            "global_weak has already been initialized")
    if args.action == "withdraw":
        approval_path = root / "audit/ROOT_SCREEN_APPROVAL.json"
        before = approval_path.read_bytes()
        approval = json.loads(before)
        job = read(root / "logs" / (source["run_ids"][-1] + "_job.json"))
        queue = service.queue_at(owner["port"])
        validate_boundary(manifest, owner, service.current_identity(owner["pid"]),
                          job, queue, False, approval)
        request = {
            "schema": "r149-planned-boundary-withdrawal-v1",
            "migration_manifest_sha256": manifest_sha, "service_owner": owner,
            "current_run": job["name"], "prompt_id": job["prompt_id"],
            "queue_at_withdrawal": queue, "approval_before_sha256": hashlib.sha256(before).hexdigest(),
            "remaining": [global_run], "created_unix": time.time(),
        }
        if args.execute:
            folder.mkdir(exist_ok=False)
            (folder / "APPROVAL_BEFORE.json").write_bytes(before)
            service.assert_owned(owner)
            require(approval_path.read_bytes() == before and
                    not any(path.exists() for path in global_paths),
                    "boundary changed before withdrawal")
            atomic(folder / "BOUNDARY_REQUEST.json", request)
            approval.update(root_approved=False, planned_boundary=request)
            atomic(approval_path, approval)
            atomic(folder / "WITHDRAWAL_APPLIED.json", {
                **request, "approval_after_sha256": sha(approval_path),
                "current_sampling_untouched": True, "signals_sent": 0})
        print(json.dumps({"ready": True, "executed": args.execute, **request}))
        return

    request = read(folder / "BOUNDARY_REQUEST.json")
    require(request["migration_manifest_sha256"] == manifest_sha,
            "boundary manifest differs")
    paths = {run: root / "analysis/postrun/05_real_megumi_v" / (run + "_GATE.json")
             for run in source["run_ids"]}
    gates = {run: read(path) for run, path in paths.items()}
    cleanup_path = root / "processes/cleanup.json"
    failure_path = root / "audit" / source["attempt"] / "FAILURE.json"
    monitor_path = root / "audit" / source["attempt"] / "CAPACITY_MONITOR_EXIT.json"
    cleanup, failure, monitor = map(read, (cleanup_path, failure_path, monitor_path))
    validate_partial(manifest, owner, gates, cleanup, failure, request, monitor)
    records = {"root_wrapper": source["root_wrapper"]}
    for name in ["service", "controller", "supervisor", "watchdog",
                 "capacity_watchdog", "capacity_monitor"]:
        path = root / "processes" / (name + ".json")
        if path.exists():
            records[name] = read(path)
    generations = {}
    for role, record in records.items():
        actual = service.current_identity(record["pid"])
        require(actual != record["identity"], "registered generation remains live: " + role)
        generations[role] = {"pid": record["pid"], "expected_identity": record["identity"],
                             "actual_identity": actual, "generation_absent": True}
    cuda = service.compute_processes()
    actual_owner = service.current_identity(owner["pid"])
    require(actual_owner != owner["identity"], "source generation resumed")
    # A reused PID is a new generation; this tool never signals either generation.
    require(actual_owner is not None or not any(row["pid"] == owner["pid"] for row in cuda),
            "original absent PID still appears in CUDA telemetry")
    artifact = lambda path: {"file": str(path), "sha256": sha(path), "record": read(path)}
    result = {
        "schema": "r149-schedule-partial-release-v1", "passed": True,
        "source_id": manifest["source_id"], "segment_id": "host9_prefix",
        "jobs": source["run_ids"], "remaining": [global_run], "service_owner": owner,
        "producer_seal_sha256": source["producer_seal_sha256"],
        "migration_manifest_sha256": manifest_sha,
        "job_gates": {run: {"file": str(path), "sha256": sha(path)}
                      for run, path in paths.items()},
        "cleanup": artifact(cleanup_path), "root_failure": artifact(failure_path),
        "capacity_monitor_exit": artifact(monitor_path),
        "boundary_request": artifact(folder / "BOUNDARY_REQUEST.json"),
        "registered_generations": generations, "process_generation_absent": True,
        "CUDA_allocation_absent": True, "original_four_arm_COMPLETE": False,
        "created_unix": time.time(),
    }
    if args.execute:
        path = folder / "PARTIAL_RELEASE.json"
        require(not path.exists(), "partial release already exists")
        atomic(path, result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
