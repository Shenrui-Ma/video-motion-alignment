"""Observe exact registered task PIDs every two seconds; never control memory."""
import json
from pathlib import Path
import time

import capacity_trial


def select_owned(rows, targets, lookup=capacity_trial.identity):
    expected = {item["pid"]: item for item in targets}
    selected = []
    for row in rows:
        target = expected.get(row["pid"])
        if target is None or not capacity_trial.same_identity(lookup(row["pid"]), target):
            continue
        memory = float(row["used_memory_mib"])
        if memory < 0:
            raise ValueError("negative NVML process memory")
        selected.append(dict(row, identity=target, used_memory_mib=memory))
    return selected


def run(root, owner, stop):
    import service
    from execution_gate import atomic
    root = Path(root)
    attempt = json.loads((root / "processes/controller.json").read_text())["attempt"]
    folder = root / "audit" / attempt
    peaks, samples = {}, 0
    with (folder / "OWN_NVML.jsonl").open("a", buffering=1) as log:
        while not stop.is_set() and capacity_trial.same_identity(capacity_trial.identity(owner["pid"]), owner):
            try:
                targets = capacity_trial.registered_targets(root, owner)
                rows = select_owned(service.compute_processes(), targets)
                samples += 1
                for row in rows:
                    key = str(row["pid"]) + ":" + str(row["identity"]["start_ticks"])
                    if key not in peaks or row["used_memory_mib"] > peaks[key]["used_memory_mib"]:
                        peaks[key] = row
                log.write(json.dumps({"unix": time.time(), "sample_available": True, "own_processes": rows}) + "\n")
                atomic(folder / "OWN_NVML_PEAKS.json", {
                    "schema": "r144-own-pid-nvml-samples-v1", "samples": samples,
                    "interval_seconds": 2, "sampled_peaks": list(peaks.values()),
                    "scope": "NVML sampled process memory, not allocator exact peak",
                    "memory_configuration_changed": False,
                })
            except Exception as error:
                log.write(json.dumps({"unix": time.time(), "sample_available": False, "error": repr(error)}) + "\n")
            stop.wait(2)
