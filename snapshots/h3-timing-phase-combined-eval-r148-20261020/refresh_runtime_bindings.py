"""Bind sealed producer contracts and optionally a successful output path; no remote actions."""
import argparse
import json
from pathlib import Path, PurePosixPath
from prepare_comparison import ROOT, bound, read, require


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case")
    p.add_argument("--gate", type=Path, help="Successful gate used only to bind the actual output filename")
    a = p.parse_args()
    require(not a.gate or a.case, "--gate requires --case")
    for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]:
        sid = c["source_id"]
        if a.case and sid != a.case:
            continue
        producer = Path(c["R148"]["producer_case"])
        seal_path = producer / "deploy_manifest.json"
        require(seal_path.exists(), "Producer is not sealed: " + sid)
        seal = read(seal_path)
        for rel, info in seal["files"].items():
            require(bound(producer / rel)["sha256"] == info["sha256"], "Sealed file changed: " + rel)
        contract_path = producer / "configs/scientific_contract.json"
        contract = read(contract_path)
        spec = contract["cases"][0]
        require(spec["run_id"] == c["R148"]["run_id"] and spec["source_id"] == sid
                and spec["seed"] == c["seed"], "Scientific case identity differs")
        require(spec["prompt"] == c["prompt"] and spec["prompt_sha256"] == c["prompt_sha256"]
                and spec["video_sha256"] == c["media"]["source"]["sha256"]
                and contract["parent_noise_sha256"] == c["historical_initial_noise"]["sha256"],
                "Prompt/source/noise differs")
        graph = read(producer / "configs/graphs" / (spec["run_id"] + ".json"))
        old = c["historical_runs"]["fixed"]["router_node_50"]["inputs"]
        current = graph["50"]["inputs"]
        parameter_keys = ("mode", "alpha", "radius", "time_offset", "start_frame", "end_frame",
                          "step_start", "step_end", "block_start", "block_end")
        require(all(current[k] == old[k] for k in parameter_keys), "Historical fixed parameters differ")
        runtime = read(producer / "configs/runtime.json")
        b = {"schema": "r148-evaluation-runtime-binding-v1", "status": "SEALED_AWAITING_OUTPUT",
             "source_id": sid, "role": "fixed_phase", "run_id": spec["run_id"],
             "historical_prompt_sha256": c["prompt_sha256"],
             "historical_noise_sha256": c["historical_initial_noise"]["sha256"],
             "historical_fixed_graph_sha256": c["historical_runs"]["fixed"]["graph"]["sha256"],
             "producer_seal": bound(seal_path), "producer_contract": bound(contract_path),
             "verified_sealed_files": len(seal["files"]), "remote_root": runtime["remote_root"],
             "gate_schema": "r148-fixed-phase-runtime-gate-v1",
             "complete_schema": "r148-fixed-phase-completion-v1",
             "receipt_files": {"gate": f"analysis/postrun/{sid}/COMBINED_RUNTIME_GATE.json",
                               "complete": "COMPLETE.json", "release": "ROOT_EXIT_RECEIPT.json"},
             "output_relative_file": None, "output_prefix": spec["run_id"],
             "expected_run_fields": {"NFE": 20, "Euler_updates": 20, "routed_blocks": 450,
                                     "original_rope_table_blocks": 1000},
             "actual_fixed_parameters": {k: current[k] for k in parameter_keys}}
        if a.gate:
            g = read(a.gate)
            require(g.get("passed") is True and g.get("schema") == b["gate_schema"]
                    and g.get("source_id") == sid
                    and g.get("producer_seal_sha256") == b["producer_seal"]["sha256"],
                    "Cannot bind an unsuccessful or unrelated gate")
            run = g["runs"]["fixed_phase"]
            require(run["run_id"] == b["run_id"], "Actual output run differs")
            path = PurePosixPath(run["video"]["file"])
            base = PurePosixPath(b["remote_root"])
            require(".." not in path.parts and path.is_relative_to(base / "output")
                    and path.name.startswith(b["run_id"] + "_"), "Unrelated output path")
            b.update(status="READY", output_relative_file=str(path.relative_to(base)),
                     actual_output_gate=bound(a.gate))
        out = ROOT / "runtime" / (sid + ".json")
        if out.exists():
            history = ROOT / "runtime/history"
            history.mkdir(exist_ok=True)
            digest = bound(out)["sha256"]
            archive = history / (sid + "_" + digest + ".json")
            if not archive.exists():
                archive.write_bytes(out.read_bytes())
        out.write_text(json.dumps(b, ensure_ascii=False, indent=2) + "\n")
        print(sid, b["status"], b["producer_seal"]["sha256"])


if __name__ == "__main__":
    main()
