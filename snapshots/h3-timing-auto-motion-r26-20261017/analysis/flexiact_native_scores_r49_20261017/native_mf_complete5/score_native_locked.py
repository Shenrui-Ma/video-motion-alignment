"""Run one frozen CPU score under the shared server consumer lock."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from bind_native_release import ACTIONS, FREEZE_SHA, require, sha

METRIC_ROOT = Path("/data5/researcher/h3_runs/flexiact_official_metric_20261017")
HERE = Path(__file__).resolve().parent
LOCK = Path("/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock")
ONLINE_ROOTS = [Path("/data5/researcher/h3_runs") / name for name in (
    "timing_auto_source28289_r45_20261017", "timing_signed_source6980766_r53_20261017")]


def online_pending():
    return any((step / "request.json").is_file() and (step / "native.json").is_file()
               and not (step / "pose_complete.json").exists() and not (step / "response.json").exists()
               for root in ONLINE_ROOTS for step in (root / "audit/observations").glob("step*"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=ACTIONS, required=True)
    args = parser.parse_args()
    if online_pending():
        print(json.dumps({"status": "busy", "reason": "online pose priority"}))
        return 75
    with LOCK.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "busy", "reason": "server CPU consumer lock"}))
            return 75
        if online_pending():
            print(json.dumps({"status": "busy", "reason": "online pose priority"}))
            return 75
        require(sha(METRIC_ROOT / "RUNTIME_FREEZE.json") == FREEZE_SHA, "Evaluator freeze differs")
        freeze = json.loads((METRIC_ROOT / "RUNTIME_FREEZE.json").read_text())
        for name, value in freeze["files"].items():
            require(sha(METRIC_ROOT / name) == (value["sha256"] if isinstance(value, dict) else value),
                    "Frozen artifact differs: " + name)
        destination = HERE / "scores/native" / args.action
        receipt = HERE / "receipts" / (args.action + "_score_invocation.json")
        require(not destination.exists() and not receipt.exists(), "Score attempt already exists; review before retry")
        receipt.parent.mkdir(exist_ok=True)
        command = [sys.executable, str(METRIC_ROOT / "score_pair.py"),
                   "--reference", str(METRIC_ROOT / "outputs/reference" / args.action),
                   "--edited", str(HERE / "tracks/native" / args.action), "--output", str(destination)]
        started = time.monotonic()
        env = dict(os.environ, CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2",
                   OPENBLAS_NUM_THREADS="2", TMPDIR=str(HERE / "temp"))
        (HERE / "temp").mkdir(exist_ok=True)
        completed = subprocess.run(command, env=env, capture_output=True, text=True, timeout=180)
        record = {"action": args.action, "command": command, "returncode": completed.returncode,
                  "stdout": completed.stdout, "stderr": completed.stderr,
                  "wall_seconds": time.monotonic() - started, "server_cpu_lock": str(LOCK),
                  "runtime_freeze_sha256": FREEZE_SHA, "cuda_visible_devices": ""}
        if (destination / "SCORE.json").is_file():
            record["score_sha256"] = sha(destination / "SCORE.json")
            record["score"] = json.loads((destination / "SCORE.json").read_text())
        with receipt.open("x") as stream:
            json.dump(record, stream, indent=2, allow_nan=False)
            stream.write("\n")
        print(json.dumps(record, allow_nan=False))
        return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
