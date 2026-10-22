"""Bounded CPU collection after the already-authorized split boundary."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

BASE = Path(__file__).resolve().parent
MANIFEST = json.loads((BASE / "MIGRATION_MANIFEST.json").read_text())
SOURCE = MANIFEST["segments"]["host9_prefix"]
ROOT = SOURCE["remote_root"]
HOST = SOURCE["host"]
PREP = ROOT + "/audit/migration_preparation"
OUT = BASE / "source_release"
OUT.mkdir(exist_ok=True)
COMMAND = (
    "python3 " + PREP + "/partial_release.py collect --manifest "
    + PREP + "/MIGRATION_MANIFEST.json"
)
SPLIT_GATE = (
    ROOT + "/analysis/postrun/05_real_megumi_v/"
    + SOURCE["run_ids"][-1] + "_GATE.json"
)
FAILURE = ROOT + "/audit/" + SOURCE["attempt"] + "/FAILURE.json"
deadline = time.monotonic() + 7200
last_status = None


def run_remote(command):
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", HOST, command],
        capture_output=True, text=True, timeout=40,
    )


while time.monotonic() < deadline:
    try:
        ready = run_remote("test -f " + SPLIT_GATE + " && test -f " + FAILURE)
        if ready.returncode:
            status = "waiting_for_split_gate_and_planned_controller_exit"
        else:
            dry = run_remote(COMMAND)
            if dry.returncode:
                status = "waiting_for_exact_generation_release"
                (OUT / "last_wait_diagnostic.txt").write_text(dry.stderr[-4000:])
            else:
                value = json.loads(dry.stdout)
                assert value["passed"] and value["process_generation_absent"]
                assert value["CUDA_allocation_absent"]
                receipt_path = (
                    ROOT + "/audit/partial_release_global_weak_migration/PARTIAL_RELEASE.json"
                )
                exists = run_remote("test -f " + receipt_path)
                completed = run_remote(
                    "cat " + receipt_path if exists.returncode == 0 else COMMAND + " --execute"
                )
                completed.check_returncode()
                receipt = json.loads(completed.stdout)
                for key in ("migration_manifest_sha256", "jobs", "remaining", "service_owner"):
                    assert receipt[key] == value[key]
                assert receipt["passed"] is True
                paths = {
                    "PARTIAL_RELEASE.json": receipt_path
                }
                for field in (
                    "cleanup", "root_failure", "capacity_monitor_exit", "boundary_request"
                ):
                    paths[field + ".json"] = receipt[field]["file"]
                files = {}
                for name, remote in paths.items():
                    subprocess.run(
                        ["scp", "-q", HOST + ":" + remote, str(OUT / name)],
                        check=True, capture_output=True, text=True, timeout=40,
                    )
                    files[name] = {
                        "remote": remote,
                        "sha256": hashlib.sha256((OUT / name).read_bytes()).hexdigest(),
                    }
                summary = {
                    "passed": True, "created_unix": time.time(),
                    "jobs": receipt["jobs"], "remaining": receipt["remaining"],
                    "service_pid": receipt["service_owner"]["pid"], "files": files,
                }
                (OUT / "COLLECTED.json").write_text(json.dumps(summary, indent=2) + "\n")
                print(json.dumps(summary), flush=True)
                break
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as error:
        status = "collection_observation_error"
        (OUT / "last_wait_diagnostic.txt").write_text(repr(error))
    if status != last_status:
        print(json.dumps({"unix": time.time(), "status": status}), flush=True)
        last_status = status
    time.sleep(45)
else:
    raise TimeoutError("bounded partial-release collection expired")
