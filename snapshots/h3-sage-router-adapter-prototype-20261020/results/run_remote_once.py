"""Read-only preflight + one bounded child; sent to target python3 via SSH stdin."""

import hashlib
import json
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/data4/researcher/h3_runs/sage_router_adapter_microcheck_20261020")
GPU = "GPU-REDACTED"
PROTECTED = 1646285
EXPECTED_CORE = "e475182fc55d6a683499e1eb4d8886fc06e050ed938d8563b090773eede2a99e"


def now():
    return datetime.now(timezone.utc).isoformat()


def identity(pid):
    path = Path("/proc") / str(pid)
    if not path.exists():
        return None
    cmd = (path / "cmdline").read_bytes()
    stat = (path / "stat").read_text().rsplit(")", 1)[1].split()
    return {
        "pid": pid, "uid": path.stat().st_uid, "startticks": int(stat[19]),
        "cmdline_sha256": hashlib.sha256(cmd).hexdigest(),
    }


def gpu_state():
    output = subprocess.check_output([
        "nvidia-smi", "-i", GPU,
        "--query-gpu=uuid,memory.free,memory.used,utilization.gpu,temperature.gpu",
        "--format=csv,noheader,nounits",
    ], text=True).strip().split(", ")
    process_output = subprocess.check_output([
        "nvidia-smi", "--query-compute-apps=gpu_uuid,pid,used_memory",
        "--format=csv,noheader,nounits",
    ], text=True)
    processes = []
    for line in process_output.splitlines():
        device, pid, memory = line.split(", ")
        processes.append({
            "gpu_uuid": device, "pid": int(pid), "used_memory_mib": memory,
            "identity": identity(int(pid)),
        })
    return {
        "at": now(), "uuid": output[0], "free_mib": int(output[1]),
        "used_mib": int(output[2]), "utilization_percent": int(output[3]),
        "temperature_c": int(output[4]), "processes": processes,
    }


with (ROOT / "attempt.lock").open("x") as handle:
    handle.write(now() + "\n")
before = gpu_state()
protected_before = identity(PROTECTED)
health = subprocess.check_output([
    "nvidia-smi", "-q", "-i", GPU, "-d", "ECC,PAGE_RETIREMENT,ROW_REMAPPER",
], text=True)
core = Path("/data3/researcher/h3_runs/closure_tutorials_53592/01-anime/runtime_deps/sageattention/core.py")
assert hashlib.sha256(core.read_bytes()).hexdigest() == EXPECTED_CORE
assert before["uuid"] == GPU and before["free_mib"] >= 8192
assert before["temperature_c"] < 80
assert "Remapping Failure Occurred                     : No" in health
assert "Uncorrectable Error                            : 0" in health
assert not any(p["gpu_uuid"] == GPU for p in before["processes"])
assert not any(
    p["identity"] and p["identity"]["uid"] == os.getuid() and p["pid"] != PROTECTED
    for p in before["processes"]
)
assert protected_before and protected_before["uid"] == os.getuid()
for name, digest in json.loads((ROOT / "uploaded_manifest.json").read_text()).items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
command = [
    "/data3/researcher/ComfyUI/.venv/bin/python", str(ROOT / "validate_gpu.py"),
    "--run-gpu", "--device", "cuda:0", "--dtype", "both",
    "--expected-core-sha256", EXPECTED_CORE,
    "--output", str(ROOT / "results" / "gpu-validation-001.json"),
]
env = dict(
    os.environ, CUDA_VISIBLE_DEVICES=GPU, PYTHONDONTWRITEBYTECODE="1",
    PYTHONPATH="/data3/researcher/h3_runs/closure_tutorials_53592/01-anime/runtime_deps",
)
control = {
    "started_at": now(), "timeout_seconds": 180, "gpu_uuid": GPU,
    "command": command, "preflight": before, "health": health,
    "protected_before": protected_before, "timed_out": False,
}
control_path = ROOT / "results" / "process-control.json"
start = time.monotonic()
with (ROOT / "results" / "stdout.log").open("x") as log:
    child = subprocess.Popen(command, env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    bound = identity(child.pid)
    assert bound and bound["uid"] == os.getuid()
    control["child_identity"] = bound
    control_path.write_text(json.dumps(control, indent=2) + "\n")
    print(json.dumps({"event": "started", "identity": bound, "at": now()}), flush=True)
    try:
        control["exit_code"] = child.wait(timeout=180)
    except subprocess.TimeoutExpired:
        control["timed_out"] = True
        assert identity(child.pid) == bound
        os.kill(child.pid, signal.SIGTERM)
        try:
            control["exit_code"] = child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            assert identity(child.pid) == bound
            os.kill(child.pid, signal.SIGKILL)
            control["exit_code"] = child.wait(timeout=5)
control["child_elapsed_seconds"] = time.monotonic() - start
control["child_identity_after"] = identity(child.pid)
states = []
for _ in range(10):
    state = gpu_state()
    states.append(state)
    if (not any(p["gpu_uuid"] == GPU for p in state["processes"])
            and state["used_mib"] <= before["used_mib"] + 128):
        break
    time.sleep(2)
control["postflight"] = states
control["cuda_released"] = (
    control["child_identity_after"] is None
    and not any(p["gpu_uuid"] == GPU for p in states[-1]["processes"])
    and states[-1]["used_mib"] <= before["used_mib"] + 128
)
control["protected_after"] = identity(PROTECTED)
control["protected_identity_unchanged"] = control["protected_after"] == protected_before
control["finished_at"] = now()
control_path.write_text(json.dumps(control, indent=2) + "\n")
print(json.dumps({
    "event": "finished", "exit_code": control["exit_code"],
    "timed_out": control["timed_out"], "elapsed_seconds": control["child_elapsed_seconds"],
    "cuda_released": control["cuda_released"],
    "protected_identity_unchanged": control["protected_identity_unchanged"],
    "final_gpu_used_mib": states[-1]["used_mib"],
}), flush=True)
