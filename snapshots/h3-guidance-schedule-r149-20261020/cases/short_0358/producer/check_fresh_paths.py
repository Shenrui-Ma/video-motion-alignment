"""Read-only check of exclusive per-run paths before root-authorized first launch."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from r132_contract import registry, require

_, order = registry(ROOT)
paths = ["processes/service.json", "processes/controller.json", "processes/supervisor.json",
         "processes/cuda_gate_ready.json", "processes/cuda_gate_go.json",
         "audit/ROOT_PRELAUNCH_REVIEW.json", "audit/ROOT_SCREEN_APPROVAL.json",
         "logs/controller_state.json", "logs/batch_verify.log"]
for run in order:
    paths += [f"audit/router/{run}.json", f"audit/x0/{run}",
              f"audit/{run}_conditioning.json", f"audit/{run}_noise.json",
              f"audit/CACHED_CONDITION_RUNTIME_{run}.json",
              f"logs/{run}_job.json", f"logs/{run}_history.json", f"logs/{run}_verify.log",
              f"analysis/postrun/short_0358/{run}_GATE.json"]
present = [p for p in paths if (ROOT / p).exists()]
require(not present, "initialization evidence already exists; preserve and archive before retry: " + repr(present))
print(json.dumps({"passed": True, "exclusive_paths_checked": len(paths), "present": present}))
