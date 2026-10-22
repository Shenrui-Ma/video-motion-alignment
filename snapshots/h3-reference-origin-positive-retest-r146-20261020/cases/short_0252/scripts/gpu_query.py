"""Exclude only two explicitly quarantined unavailable device rows."""
import json
from pathlib import Path

QUARANTINED = frozenset({
    "GPU-REDACTED",
    "GPU-REDACTED",
})


def parse_compute(raw, selected_uuid):
    if selected_uuid in QUARANTINED:
        raise ValueError("quarantined device cannot run this task")
    rows, excluded = [], []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = [x.strip() for x in line.split(",")]
        if len(parts) != 3:
            raise ValueError("invalid compute row: " + line)
        gpu, pid, memory = parts
        if gpu in QUARANTINED and pid == memory == "[N/A]":
            excluded.append({"gpu_uuid": gpu, "raw": line, "release_confirmed": False})
            continue
        if not gpu.startswith("GPU-") or not pid.isdecimal() or int(pid) <= 0 or not memory.isdecimal():
            raise ValueError("unavailable non-quarantined compute row: " + line)
        rows.append({"gpu_uuid": gpu, "pid": int(pid), "used_memory_mib": int(memory)})
    return rows, excluded


def parse_and_record(root, selected_uuid, raw):
    rows, excluded = parse_compute(raw, selected_uuid)
    p = Path(root) / "audit/GPU_QUARANTINE_LATEST.json"
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps({"raw": raw, "excluded": excluded,
                            "selected_uuid": selected_uuid}, indent=2) + "\n")
    return rows
