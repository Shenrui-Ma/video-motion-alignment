"""Publish the current reviewed inventories from immutable input copies."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[2]
folder = Path(__file__).resolve().parent
inputs = []
for name in ("flexiact", "ivebench"):
    source = root / "inventory" / (name + ".json")
    content = source.read_bytes()
    json.loads(content)
    digest = hashlib.sha256(content).hexdigest()
    target = folder / (name + "_" + digest[:16] + ".json")
    if target.exists():
        assert target.read_bytes() == content
    else:
        target.write_bytes(content)
    inputs.append(str(target))

snapshot = {"created_unix": time.time(), "inputs": inputs}
(folder / "LATEST_SNAPSHOT.json").write_text(json.dumps(snapshot, indent=2) + "\n")
command = [sys.executable, str(root / "scripts" / "build_task_showcase.py")]
for path in inputs:
    command += ["--inventory", path]
subprocess.run(command, check=True)
