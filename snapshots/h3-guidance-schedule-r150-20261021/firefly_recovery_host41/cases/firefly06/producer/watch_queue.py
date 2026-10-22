"""Read-only 45-second monitor for this prepared four-arm queue."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import service


def read(path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {} if default is None else default


attempt = sys.argv[1]
assert Path(attempt).name == attempt
order = read(ROOT / "configs/queue.json")["jobs"]
gpu = read(ROOT / "configs/runtime.json")["gpu_index"]
seen = {}
warned = set()
for _ in range(300):
    now = time.time()
    owner = read(ROOT / "processes/service.json")
    current_identity = service.current_identity(owner["pid"]) if owner else None
    state = read(ROOT / "logs/controller_state.json")
    out = {"unix": now, "service_pid": owner.get("pid"),
           "service_live": bool(owner and current_identity == owner["identity"]),
           "controller_status": state.get("status"), "current": state.get("current")}
    changes = {}
    for run in order:
        folder = ROOT / "audit/x0" / run
        snapshots = sorted(folder.glob("x0_step*.pt"))
        router = read(ROOT / "audit/router" / (run + ".json"))
        job = read(ROOT / "logs" / (run + "_job.json"))
        timing = read(folder / "timing.json")
        steps = router.get("forward_wall_seconds", [])
        entry = {"callbacks": len(snapshots), "job": job.get("status"),
                 "routed": router.get("routed_calls"), "last_dit_seconds": steps[-1:] or None,
                 "sampler_seconds": timing.get("sampler_wall_seconds")}
        gate = ROOT / "analysis/postrun" / 'firefly06' / (run + "_GATE.json")
        if gate.exists():
            g = read(gate)
            entry["gate"] = {"file": str(gate), "sha256": hashlib.sha256(gate.read_bytes()).hexdigest(),
                             "passed": g["passed"], "video": g["video"]}
        if entry != seen.get(run):
            changes[run] = entry
            seen[run] = entry
        if job.get("status") == "pending_or_running" and len(snapshots) < 20:
            start = (snapshots[-1].stat().st_mtime if snapshots
                     else read(folder / "manifest.json").get("created_unix", now))
            stall = (run, len(snapshots))
            if now - start > 180 and stall not in warned:
                warned.add(stall)
                p = subprocess.run(["nvidia-smi", "-i", str(gpu), "-q", "-d",
                                    "PERFORMANCE,POWER,TEMPERATURE"], capture_output=True, text=True)
                out["stalled_step"] = {"run": run, "callbacks": len(snapshots), "seconds": now-start,
                                       "gpu_detail": (p.stdout+p.stderr)[-7000:]}
    out["changes"] = changes
    folder = ROOT / "audit" / attempt
    terminal = next((p for p in ("COMPLETE.json", "FAILURE.json") if (folder / p).exists()), None)
    if terminal:
        out[terminal] = {"file": str(folder / terminal), "sha256": hashlib.sha256((folder / terminal).read_bytes()).hexdigest(), "passed": read(folder / terminal).get("passed")}
    if changes or terminal or "stalled_step" in out:
        print(json.dumps(out), flush=True)
    if terminal:
        break
    time.sleep(45)
