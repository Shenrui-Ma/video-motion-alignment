"""Read-only design validation. This package intentionally has no GPU launcher."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = {"early": (0, 9), "late": (11, 20)}
RUNS = [f"r143_long_0039_seed2026101701_{arm}" for arm in STAGES]


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def expected_graph(root, arm):
    """Only identifiers, output/audit paths and the stage interval may differ."""
    start, end = STAGES[arm]
    root = Path(root)
    remote = Path(read(root / "configs/runtime.json")["remote_root"])
    graph = copy.deepcopy(read(root / "design/R122_ACTUAL/forced_graph.json"))
    for node, key, suffix in [
        ("5", "audit_dir", "audit"), ("6", "audit_dir", "audit"),
        ("50", "audit_dir", "audit/router"), ("51", "source_audit_dir", "audit"),
        ("52", "output_dir", "audit/x0"),
    ]:
        graph[node]["inputs"][key] = str(remote / suffix)
    run = f"r143_long_0039_seed2026101701_{arm}"
    graph["5"]["inputs"]["run_id"] = "r143_long_0039_shared"
    graph["51"]["inputs"]["source_run_id"] = "r143_long_0039_shared"
    for node in ("6", "50", "51", "52"):
        graph[node]["inputs"]["run_id"] = run
    graph["6"]["inputs"]["pair_id"] = "r143_long_0039_seed2026101701"
    graph["14"]["inputs"]["filename_prefix"] = run
    graph["50"]["inputs"].update(step_start=start, step_end=end)
    return graph


def same_generation(saved, current):
    """Numeric PID reuse must never identify a new process as the predecessor."""
    return (current is not None and current["uid"] == saved["uid"]
            and str(current["start_ticks"]) == str(saved["start_ticks"]))


def check(root=ROOT):
    root = Path(root)
    jobs = read(root / "configs/jobs.json")
    bindings = read(root / "configs/parent_bindings.json")
    require(read(root / "configs/admission.json")["ready_for_launch"] is False,
            "design package must stay unadmitted")
    require(read(root / "configs/queue.json") == {"jobs": RUNS, "finalize": True},
            "only the two registered jobs are allowed")
    require(len(jobs["jobs"]) == 2 and jobs["new_native_jobs"] == 0,
            "no extra Native or additional job")
    for arm, row in zip(STAGES, jobs["jobs"]):
        start, end = STAGES[arm]
        expected = {
            "run_id": f"r143_long_0039_seed2026101701_{arm}", "arm": arm,
            "steps_half_open": [start, end],
            "prediction_indices_zero_based": list(range(start, end)),
            "guided_predictions": 9, "routed_blocks": 450,
            "total_predictions": 20, "Euler_updates": 20,
        }
        require(row == expected, "stage registry changed")
        require(read(root / "configs/graphs" / (row["run_id"] + ".json"))
                == expected_graph(root, arm), "graph changes exceed stage/run/path scope")
    for name, digest in bindings["parent_records"].items():
        require(sha(root / "design/R122_ACTUAL" / name) == digest,
                "actual parent record changed: " + name)
    gate = read(root / "design/R122_ACTUAL/PAIR_RUNTIME_GATE.json")
    require(gate["passed"] is True and all(gate["checks"].values()),
            "actual R122 pair gate was not passed")
    for name, digest in bindings["frozen_kernel_sha256"].items():
        require(sha(root / "source_snapshot/router" / name) == digest,
                "frozen numerical source changed")
    runtime = read(root / "configs/runtime.json")
    for key in ("host", "gpu_uuid", "core", "python", "dependencies", "models",
                "kj_nodes", "reserve_vram", "memory_mode", "expected_gpu_index"):
        require(runtime[key] == gate["runtime_profile"][key],
                "same-host numerical runtime changed: " + key)
    require(jobs["reuse"] == {
        "native": gate["runs"]["native"]["video"],
        "middle_6_14": gate["runs"]["forced"]["video"],
    }, "reused actual videos changed")
    prompt = (root / "configs/prompts/long_0039.txt").read_text()
    require(prompt == expected_graph(root, "early")["5"]["inputs"]["prompt"],
            "actual R122 prompt changed")
    return {
        "passed": True, "jobs": RUNS, "new_Native": 0, "NFE_per_job": 20,
        "guided_predictions_per_job": 9, "routed_blocks_per_job": 450,
        "GPU_started": False, "launchable": False,
        "status": "CPU design frozen; runner integration deferred by root",
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
