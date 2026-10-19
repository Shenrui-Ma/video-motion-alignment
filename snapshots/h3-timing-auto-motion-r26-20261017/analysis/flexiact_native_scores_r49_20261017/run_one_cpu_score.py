"""Hold the shared Mac consumer lock for one remote CPU score."""
import argparse
import fcntl
import json
from pathlib import Path
import shlex
import subprocess
import sys

from bind_native_release import ACTIONS

ROOT = Path(__file__).resolve().parent
LOCK = Path("/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=ACTIONS, required=True)
    args = parser.parse_args()
    with LOCK.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "busy", "reason": "Mac CPU consumer lock"}))
            return 75
        command = ["/home/researcher/miniconda3/envs/comfyui/bin/python",
                   "/data5/researcher/h3_runs/flexiact_native_scores_r49_20261017/score_native_locked.py",
                   "--action", args.action]
        result = subprocess.run(["ssh", "-J", "H3_SERVER_B", "-o", "ConnectTimeout=15",
                                 "H3_SERVER_A", shlex.join(command)], text=True, capture_output=True, timeout=210)
        if result.returncode != 75:
            folder = ROOT / "cpu_score_invocations"
            folder.mkdir(exist_ok=True)
            with (folder / (args.action + ".json")).open("x") as stream:
                json.dump({"action": args.action, "returncode": result.returncode,
                           "stdout": result.stdout, "stderr": result.stderr,
                           "mac_cpu_lock": str(LOCK)}, stream, indent=2)
                stream.write("\n")
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
