"""Root-authorized one-shot launch after actual Sam release; no waiting or sampling tests."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cgroup_memory
import service

SEAL = "dd45b20fe8ac78892b59244574c120783cdebfcbaa9a0fbf92d834868aa87cf3"
SAM = Path("/data4/researcher/h3_runs/guidance_schedule_r149_global_weak_host41_20261020/cases/05_real_megumi_v")
SAM_ATTEMPT = SAM / "audit/root_r149_sam_global_host41_attempt1"
ATTEMPT = "root_r149_drink_recovery_host41_attempt1"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


require(sys.argv[1:] == ["--execute"], "explicit execution flag required")
require(ROOT == Path(service.RUNTIME["remote_root"]), "actual target root required")
require(sha(ROOT / "deploy_manifest.json") == SEAL, "approved producer seal differs")
for relative, evidence in read(ROOT / "deploy_manifest.json")["files"].items():
    require(sha(ROOT / relative) == evidence["sha256"], "sealed file changed: " + relative)
complete_path, exit_path = SAM_ATTEMPT / "COMPLETE.json", SAM_ATTEMPT / "ROOT_EXIT_RECEIPT.json"
complete, released = read(complete_path), read(exit_path)
require(complete["passed"] and complete["GPU_released"] and complete["remaining"] == [], "Sam incomplete")
require(released["passed"] and released["process_absent"] and released["CUDA_allocation_absent"],
        "Sam exact release unavailable")
require(released["owner"]["pid"] == 88263 and complete["service_owner"] == released["owner"],
        "Sam service identity differs")
require(service.current_identity(88263) is None and service.current_identity(88243) is None,
        "Sam service or root wrapper remains live")
own_video = []
for p in Path("/proc").iterdir():
    if not p.name.isdecimal():
        continue
    pid = int(p.name)
    if service.proc_uid(pid) != os.getuid():
        continue
    actual = service.current_identity(pid)
    if actual and ("/scripts/service_entry.py" in actual["cmdline"] or "ComfyUI/main.py" in actual["cmdline"]):
        own_video.append({"pid": pid, "identity": actual})
require(not own_video, "another own video service is live")
rows = service.compute_processes()
require(not any(service.proc_uid(row["pid"]) == os.getuid() for row in rows),
        "another own GPU task remains")
row = subprocess.run(["nvidia-smi", "-i", "6", "--query-gpu=index,uuid,memory.free,memory.used,utilization.gpu",
                      "--format=csv,noheader,nounits"], text=True, capture_output=True, check=True, timeout=15).stdout.strip()
parts = [s.strip() for s in row.split(",")]
require(parts[0] == "6" and parts[1] == service.GPU and int(parts[2]) >= 40960, "GPU6 free memory insufficient")
health = subprocess.run(["nvidia-smi", "-i", "6", "-q", "-d", "PERFORMANCE,POWER,TEMPERATURE"],
                        text=True, capture_output=True, check=True, timeout=20).stdout
require("requires reset" not in health.lower(), "GPU6 requires reset")
capacity = cgroup_memory.check(ROOT)
require(capacity["admitted"], "fresh cgroup admission failed")
sock = socket.socket()
try:
    require(sock.connect_ex(("127.0.0.1", 8644)) != 0, "port 8644 occupied")
finally:
    sock.close()
subprocess.run(["python3", str(ROOT / "producer/check_fresh_paths.py")], cwd=ROOT, check=True)
require(not (ROOT / "audit" / ATTEMPT).exists(), "attempt already exists")
fresh = {"observed_unix": time.time(), "gpu_row": row, "gpu_health": health,
         "capacity": capacity, "own_video": own_video, "compute_rows": rows,
         "sam_complete": {"file": str(complete_path), "sha256": sha(complete_path)},
         "sam_release": {"file": str(exit_path), "sha256": sha(exit_path)}}
service.write_json(ROOT / "audit/FRESH_START_CHECK.json", fresh)
review = {
    "approved": True, "producer_seal_sha256": SEAL, "predecessor_release_verified": True,
    "predecessor_release_evidence": fresh["sam_release"],
    "predecessor_complete_evidence": fresh["sam_complete"],
    "fresh_gpu": row, "fresh_capacity": capacity,
    "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
    "host41_max_own_video_processes": 1,
    "source_gpu5_release": "Exact processes exited; CUDA allocation remains unknown due to requires reset",
    "authorization": "REDACTED_CREDENTIAL",
    "unix": time.time(),
}
service.write_json(ROOT / "audit/ROOT_PRELAUNCH_REVIEW.json", review)
command = ["python3", "-u", str(ROOT / "audit/root_run_batch.py"), "--execute", "--attempt", ATTEMPT]
with (ROOT / "logs/root_launch_recovery_attempt1.log").open("xb", buffering=0) as log:
    child = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                             start_new_session=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
identity = service.bind_child(child, command)
receipt = {"pid": child.pid, "identity": identity, "command": command,
           "attempt": ATTEMPT, "producer_seal_sha256": SEAL,
           "review_sha256": sha(ROOT / "audit/ROOT_PRELAUNCH_REVIEW.json"), "unix": time.time()}
service.write_json(ROOT / "audit/RECOVERY_ATTEMPT1_LAUNCH.json", receipt)
print(json.dumps(receipt))
