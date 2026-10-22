"""Strict NVML rows with one evidence-bound, nonselected device quarantine."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

QUARANTINED_UUID = "GPU-REDACTED"


def policy(root, runtime, requested_uuid=None):
    root = Path(root)
    value = json.loads((root / "configs/gpu_quarantine.json").read_text())
    if (value["schema"] != "r144-explicit-device-quarantine-v1"
            or value["gpu_uuid"] != QUARANTINED_UUID
            or value["allow_exclusion_only"] != {"pid": "[N/A]", "used_memory": "[N/A]"}):
        raise ValueError("unexpected quarantine policy")
    evidence = root / "configs/GPU_QUARANTINE_HEALTH.json"
    if (value["health_evidence"] != str(evidence.relative_to(root))
            or hashlib.sha256(evidence.read_bytes()).hexdigest() != value["health_evidence_sha256"]):
        raise ValueError("quarantine evidence changed")
    health = json.loads(evidence.read_text())["assessment"]["gpu4"]
    if health["uuid"] != QUARANTINED_UUID or health["GPU_Recovery_Action"] != "Reset":
        raise ValueError("quarantine lacks driver reset-required evidence")
    forbidden = {
        runtime["gpu_uuid"], runtime["decoder_gpu_uuid"],
        runtime["preserved_user_service_gpu"], requested_uuid,
    }
    if QUARANTINED_UUID in forbidden:
        raise ValueError("quarantined GPU may not be selected or preserved")
    return value


def parse_compute(raw, quarantine):
    rows, unavailable = [], []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 3:
            raise ValueError("unexpected compute row shape")
        gpu, pid, memory = parts
        if gpu == quarantine["gpu_uuid"] and pid == memory == "[N/A]":
            unavailable.append({"gpu_uuid": gpu, "raw": line, "availability": "unknown",
                                "excluded_from_task_capacity": True, "release_confirmed": False})
            continue
        if not gpu.startswith("GPU-") or not pid.isdecimal() or int(pid) <= 0:
            raise ValueError("unexpected compute GPU/PID: " + line)
        if not memory.isdecimal():
            raise ValueError("unexpected compute memory: " + line)
        rows.append({"gpu_uuid": gpu, "pid": int(pid), "used_memory_mib": memory})
    return rows, unavailable


def parse_and_record(root, runtime, raw, requested_uuid=None):
    root = Path(root)
    quarantine = policy(root, runtime, requested_uuid)
    rows, unavailable = parse_compute(raw, quarantine)
    snapshot = {"observed_unix": time.time(), "compute_raw": raw,
                "quarantined_unavailable": unavailable,
                "health_evidence_sha256": quarantine["health_evidence_sha256"],
                "quarantined_device_release_confirmed": False}
    if unavailable:
        audit = root / "audit"
        audit.mkdir(exist_ok=True)
        payload = (json.dumps(snapshot, indent=2) + "\n").encode()
        # The first raw anomaly remains immutable; latest is atomically replaced.
        try:
            with (audit / "GPU_QUARANTINE_FIRST.json").open("xb") as handle:
                handle.write(payload)
        except FileExistsError:
            pass
        fd, temporary = tempfile.mkstemp(prefix=".gpu-quarantine-", dir=audit)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
            os.replace(temporary, audit / "GPU_QUARANTINE_LATEST.json")
        finally:
            Path(temporary).unlink(missing_ok=True)
    return rows, snapshot
