"""Fetch one explicitly completed case's small receipts and final video once."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shlex
import subprocess
from datetime import datetime, timezone

from prepare_comparison import ROOT, bound, read, require


def fetch(remote, local, max_bytes):
    if local.exists():
        return
    command = f"head -c {max_bytes + 1} -- {shlex.quote(str(remote))}"
    data = subprocess.check_output(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
         "H3_SERVER_B", command], timeout=90)
    require(len(data) <= max_bytes, "Remote file exceeds this small-transfer limit")
    local.write_bytes(data)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--attempt", required=True)
    p.add_argument("--complete-sha256", required=True)
    p.add_argument("--release-sha256", required=True)
    a = p.parse_args()
    require("/" not in a.attempt and a.attempt not in ("", ".", ".."), "Invalid attempt")
    binding = read(ROOT / "runtime" / (a.case + ".json"))
    remote = PurePosixPath(binding["remote_root"])
    dest = ROOT / "incoming" / a.case / a.attempt
    dest.mkdir(parents=True, exist_ok=True)
    gate = dest / "COMBINED_RUNTIME_GATE.json"
    complete = dest / "COMPLETE.json"
    release = dest / "ROOT_EXIT_RECEIPT.json"
    fetch(remote / binding["receipt_files"]["gate"], gate, 2_000_000)
    for path, expected in ((complete, a.complete_sha256), (release, a.release_sha256)):
        fetch(remote / "audit" / a.attempt / path.name, path, 2_000_000)
        require(bound(path)["sha256"] == expected, "Root-confirmed receipt SHA differs")
        require(read(path).get("passed") is True, "Receipt did not pass")
    g = read(gate)
    require(g.get("passed") is True and g.get("schema") == binding["gate_schema"],
            "Successful case gate required")
    require(g["runs"]["fixed_phase"]["run_id"] == binding["run_id"], "Wrong output run")
    video = g["runs"]["fixed_phase"]["video"]
    source = PurePosixPath(video["file"])
    require(source.is_relative_to(remote / "output") and ".." not in source.parts,
            "Video is outside the case output")
    target = dest / source.name
    fetch(source, target, 50_000_000)
    require(bound(target)["sha256"] == video["sha256"], "Video SHA differs")
    receipt = {"schema": "r148-small-output-collection-v1",
               "collected_utc": datetime.now(timezone.utc).isoformat(),
               "source_id": a.case, "attempt": a.attempt, "remote_root": str(remote),
               "files": [{**bound(q), "bytes": q.stat().st_size}
                         for q in (gate, complete, release, target)],
               "large_audit_or_tensor_downloaded": False}
    (dest / "COLLECTION.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"case": a.case, "directory": str(dest), "video": bound(target),
                      "total_local_bytes": sum(q["bytes"] for q in receipt["files"])}))


if __name__ == "__main__":
    main()
