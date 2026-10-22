"""Read actual online audit records; never derive decisions from final video."""
import argparse
import json
from pathlib import Path
import sys


def summarize(root):
    root = Path(root)
    sys.path[:0] = [str(root / "extensions"), str(root / "scripts")]
    from H3AutomaticWindowRouter.automatic_window_policy import candidate
    protocol = json.loads((root / "configs/protocol.json").read_text())
    case = protocol["cases"][0]
    path = root / "audit/counterfactual" / (case["run_id"] + ".json")
    if not path.exists():
        return {"run_id": case["run_id"], "status": "NOT_STARTED", "steps": []}
    audit = json.loads(path.read_text())
    counter = audit["counterfactual"]
    measurements = {m["physical_index"]: m for m in counter["measurements"]}
    rows = []
    for step in counter["steps"]:
        index = step["physical_index"]
        decision = step["decision"]
        observed = measurements[index]["observer"]["windows"]
        eligible = [value for value in (candidate(row, .5) for row in observed) if value is not None]
        routed = [audit["routed_by_forward"][nfe] for nfe in step["nfe_indices"]]
        rows.append({
            "physical_index": index, "denoising_step_one_based": index + 1,
            "state": "ON" if decision["chosen_full"] else ("UNKNOWN" if decision["all_unknown"] else "OFF"),
            "eligible_candidate_count": len(eligible),
            "candidate_group_count": decision["candidate_groups"],
            "reliable_rows": decision["reliable_rows"], "total_rows": decision["total_rows"],
            "selected_physical_windows_inclusive": decision["physical_intervals"],
            "detected_candidates": [{"window": c["window"], "feature": c["feature"],
                                     "lags": c["lags"], "min_gain": c["min_gain"],
                                     "absolute_gain": c["absolute_gain"]} for c in eligible],
            "selected": decision["selected"], "latent_bins": decision["latent_bins"],
            "actual_routed_calls": sum(routed), "routed_calls_by_actual_nfe": routed,
            "reason": decision["reason"],
            "stop_reason": None if decision["chosen_full"] else decision["reason"],
            "nfe_indices": step["nfe_indices"], "chosen_branch": step["selected_branch"],
        })
    return {"run_id": case["run_id"], "source_id": case["source_id"], "policy": "original_R133_visible_only",
            "fixed_schedule": False, "centered_gate": False, "content_boundary_filter": False,
            "status": audit["status"], "steps": rows, "completed_updates": len(rows),
            "actual_NFE": audit["completed_forward_calls"], "actual_routed_calls": audit["routed_calls"],
            "full_physical_indices": counter["full_physical_indices"],
            "planned_Euler_updates": 20, "expected_complete_NFE": "20+actual_ON"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    result = summarize(args.case_root)
    data = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        path = Path(args.output)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(data)
        temporary.replace(path)
    else:
        print(data)
