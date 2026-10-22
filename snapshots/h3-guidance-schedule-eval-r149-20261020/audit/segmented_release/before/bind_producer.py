"""Bind an already frozen producer without changing or launching it."""
import argparse
from pathlib import Path
from common import ROOT, bound, read, write, require, prompt_sha, expected_router


def runtime_binding(runtime, source_id):
    remote = Path(runtime["remote_root"])
    require(remote.is_absolute() and ".." not in remote.parts and
            remote.parts[-2:] == ("cases", source_id), "Runtime root belongs to another case")
    prefixes = {
        "H3_SERVER_B": "/data4/researcher/h3_runs/",
        "H3_SERVER_A": "/home/researcher/h3_runs/",
    }
    require(runtime.get("host") in prefixes and
            str(remote).startswith(prefixes[runtime["host"]]), "Host and remote root differ")
    return {"host": runtime["host"], "remote_root": str(remote),
            "gpu_index": runtime["gpu_index"], "gpu_uuid": runtime["gpu_uuid"],
            "port": runtime["port"]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--producer", type=Path, required=True)
    p.add_argument("--seal-sha256", required=True)
    p.add_argument("--archive-old", action="store_true",
                   help="Preserve each prior READY binding by its seal before the approved update.")
    a = p.parse_args()
    manifest = read(ROOT / "EVALUATION_MANIFEST.json")
    case = next(c for c in manifest["cases"] if c["source_id"] == a.case)
    seal = bound(a.producer / "deploy_manifest.json")
    require(seal["sha256"] == a.seal_sha256, "Producer seal differs")
    sealed = read(seal["file"])["files"]
    contract_path = a.producer / "configs/scientific_contract.json"
    verifier_path = a.producer / "analysis/postrun/verify_schedule.py"
    runtime_path = a.producer / "configs/runtime.json"
    for path in (contract_path, verifier_path, runtime_path):
        require(bound(path)["sha256"] == sealed[str(path.relative_to(a.producer))]["sha256"],
                "Unsealed producer field: " + str(path))
    actual_runtime = runtime_binding(read(runtime_path), a.case)
    contract = read(contract_path)
    require(contract["schema"] == "r149-fixed-schedule-only-v1" and
            contract["phase_displacement"] == 0 and contract["NFE_per_job"] == 20 and
            contract["online_observer"] is False and
            contract["parent_noise_sha256"] == case["historical_initial_noise"]["sha256"],
            "Producer scope differs")
    for arm, schedule in manifest["schedules"].items():
        expected_run = f"r149_{a.case}_seed{case['seed']}_{arm}"
        row = next(row for row in contract["cases"] if row["arm"] == arm)
        require(row["run_id"] == expected_run and row["source_id"] == a.case and
                row["seed"] == case["seed"] and row["steps_zero_based"] == schedule["steps_0based"] and
                row["phase_displacement"] == 0 and row["prompt"] == case["prompt"] and
                prompt_sha(row["prompt"]) == case["prompt_sha256"] and
                row["video_sha256"] == case["media"]["source"]["sha256"], "Case controls differ")
        g = case["geometry"]
        require(row["geometry"] == {"width": g["width"], "height": g["height"],
                "frames": g["sampled_frames"], "fps": g["fps"]} and
                row["valid_frame_count"] == g["valid_frames"] and
                row["evaluation_crop_xywh"] == g["crop_xywh"], "Frame domain differs")
        graph_path = a.producer / "configs/graphs" / (expected_run + ".json")
        require(bound(graph_path)["sha256"] == sealed[str(graph_path.relative_to(a.producer))]["sha256"],
                "Actual graph is not sealed")
        inputs = read(graph_path)["50"]["inputs"]
        expected = expected_router(case, dict(schedule, id=arm))
        require(all(inputs.get(k) == v for k, v in expected.items()) and
                inputs["schedule"] == arm, "Original same-bin router controls differ")
        path = ROOT / "runtime" / a.case / (arm + ".json")
        new = {"status": "READY", "source_id": a.case, "schedule": arm, "role": arm,
            "run_id": expected_run, "phase_offset": 0, "steps_0based": schedule["steps_0based"],
            "historical_prompt_sha256": case["prompt_sha256"],
            "historical_noise_sha256": case["historical_initial_noise"]["sha256"],
            "historical_fixed_graph_sha256": case["historical_runs"]["fixed"]["graph"]["sha256"],
            "producer_seal": seal, "producer_verifier": bound(verifier_path),
            "scientific_contract": bound(contract_path), "graph": bound(graph_path),
            "producer_runtime": bound(runtime_path), **actual_runtime,
            "gate_relative_file": f"analysis/postrun/{a.case}/{expected_run}_GATE.json",
            "batch_gate_relative_file": f"analysis/postrun/{a.case}/SCHEDULE_RUNTIME_GATE.json"}
        if path.exists() and read(path).get("status") == "READY":
            old = read(path)
            if old != new:
                require(a.archive_old, "Already bound; use --archive-old for an approved runtime update")
                archive = ROOT / "audit/binding_history" / a.case / old["producer_seal"]["sha256"] / path.name
                archive.parent.mkdir(parents=True, exist_ok=True)
                if archive.exists():
                    require(archive.read_bytes() == path.read_bytes(), "Conflicting old binding archive")
                else:
                    archive.write_bytes(path.read_bytes())
        write(path, new)
    print(f"Bound {a.case}: {len(manifest['schedules'])} arms; no launch.")


if __name__ == "__main__":
    main()
