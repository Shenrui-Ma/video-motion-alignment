"""Collect only the independently released book decode and small proof files."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import PurePosixPath

from collect_completed import fetch
from prepare_comparison import ROOT, bound, read, require
from prepare_recovered_book import BINDING_SHA, validate_recovery


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--attempt", required=True)
    p.add_argument("--gate-sha256", required=True)
    p.add_argument("--release-sha256", required=True)
    a = p.parse_args()
    require("/" not in a.attempt and a.attempt not in ("", ".", ".."), "Invalid attempt")
    case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]
                if c["source_id"] == "long_0039")
    remote = PurePosixPath(read(ROOT / "runtime/long_0039.json")["remote_root"])
    recovery = remote / "audit/recovery_decode"
    remote_attempt = recovery / a.attempt
    dest = ROOT / "incoming/long_0039" / ("recovery_" + a.attempt)
    dest.mkdir(parents=True, exist_ok=True)
    gate = dest / "RECOVERY_GATE.json"
    release = dest / "RELEASE.json"
    result = dest / "DECODE_RESULT.json"
    binding = dest / "BINDING.json"
    for src, dst, expected in (
        (remote_attempt / gate.name, gate, a.gate_sha256),
        (remote_attempt / release.name, release, a.release_sha256),
        (recovery / binding.name, binding, BINDING_SHA),
    ):
        fetch(src, dst, 2_000_000)
        require(bound(dst)["sha256"] == expected, "Root-confirmed recovery proof SHA differs")
    g = read(gate)
    require(g["passed"] is True and g["run_id"] == case["R148"]["run_id"], "Recovery not complete")
    require(g["decode_result"]["file"] == str(remote_attempt / result.name)
            and g["release"]["file"] == str(remote_attempt / release.name),
            "Receipt paths differ from the requested recovery attempt")
    fetch(remote_attempt / result.name, result, 2_000_000)
    require(bound(result)["sha256"] == g["decode_result"]["sha256"], "Decode result changed")
    source = PurePosixPath(g["video"]["file"])
    require(source.parent == remote_attempt
            and source.name == case["R148"]["run_id"] + "_recovered.mp4", "Wrong recovery output")
    target = dest / source.name
    fetch(source, target, 50_000_000)
    proof = validate_recovery(case, target, gate, result, release, binding)
    receipt = {
        "schema": "r148-small-recovered-output-collection-v1",
        "collected_utc": datetime.now(timezone.utc).isoformat(),
        "source_id": "long_0039", "recovery_attempt": a.attempt,
        "original_attempt_complete": False, "new_dit_forwards": 0,
        "validated_execution": proof,
        "files": [{**bound(f), "bytes": f.stat().st_size}
                  for f in (gate, release, result, binding, target)],
        "large_audit_or_tensor_downloaded": False,
    }
    (dest / "COLLECTION.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"directory": str(dest), "video": bound(target),
                      "new_dit_forwards": 0, "original_attempt_complete": False}))


if __name__ == "__main__":
    main()
