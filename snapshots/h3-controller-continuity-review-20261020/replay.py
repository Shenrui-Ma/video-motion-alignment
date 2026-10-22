"""Compare decisions on one recorded trajectory; does not simulate new video."""
import argparse
import hashlib
import json
from pathlib import Path
from continuity_policy import Policy, baseline

p = argparse.ArgumentParser()
p.add_argument("evidence", type=Path)
p.add_argument("output", type=Path)
a = p.parse_args()
x = json.loads(a.evidence.read_text())
old, new = baseline.Policy(), Policy()
results = []
for step in x["steps"]:
    index, rows = step["index"], step["rows"]
    before = old.update(index, rows)
    for key in ("groups", "selected", "physical_intervals", "active", "reason"):
        assert before[key] == step["decision"][key], (index, key)
    after = new.update(index, rows)
    results.append({"index": index, "actual_active": before["active"],
                    "candidate_active_on_recorded_state": after["active"],
                    "actual_selected": before["selected"],
                    "candidate_selected_on_recorded_state": after["selected"],
                    "changed": before["selected"] != after["selected"]})
result = {
    "evidence": str(a.evidence.resolve()),
    "evidence_sha256": hashlib.sha256(a.evidence.read_bytes()).hexdigest(),
    "actual_policy_exact_reproduction": True,
    "completed_steps": x["completed_steps"],
    "actual_ON": [r["index"] for r in results if r["actual_active"]],
    "candidate_ON_on_recorded_states": [r["index"] for r in results
                                       if r["candidate_active_on_recorded_state"]],
    "scope": "Decision replay on the actual R133 trajectory. A changed decision would alter subsequent video states in a new run.",
    "results": results,
}
a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: result[k] for k in ("completed_steps", "actual_ON",
      "candidate_ON_on_recorded_states", "actual_policy_exact_reproduction")}))
