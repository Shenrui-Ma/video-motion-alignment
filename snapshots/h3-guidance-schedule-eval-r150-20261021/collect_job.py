"""Collect one passed per-job gate and its exact MP4 through configured SSH."""
import argparse
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import time
from common import ROOT, bound, read, write, require, case_and_schedule
from ingest import validate_job


def fetch(host, remote, destination, expected_sha=None):
    destination = Path(destination)
    require(destination.resolve().is_relative_to(ROOT / "actual"), "Collection outside actual/")
    if destination.exists():
        require(expected_sha is not None and bound(destination)["sha256"] == expected_sha,
                "Existing collection must match its expected SHA")
        return 0
    temporary = destination.with_suffix(destination.suffix + ".partial")
    with temporary.open("wb") as output:
        subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", host,
                        "cat -- " + shlex.quote(remote)], stdout=output, check=True, timeout=180)
    if expected_sha is not None:
        require(bound(temporary)["sha256"] == expected_sha, "Transferred SHA differs")
    temporary.rename(destination)
    return destination.stat().st_size


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--schedule", required=True, choices=("native", "fixed", "early", "late", "split", "global_weak"))
    p.add_argument("--expected-gate-sha")
    p.add_argument("--expected-video-sha", required=True)
    a = p.parse_args()
    _, case, schedule = case_and_schedule(a.case, a.schedule)
    schedule = dict(schedule, id=a.schedule)
    binding = read(ROOT / "runtime" / a.case / (a.schedule + ".json"))
    require(binding["host"] in ("H3_SERVER_A", "H3_SERVER_B"), "Unexpected host")
    folder = ROOT / "actual" / a.case / a.schedule
    folder.mkdir(parents=True, exist_ok=True)
    gate_file, video_file = folder / "GATE.json", folder / "video.mp4"
    remote_gate = str(PurePosixPath(binding["remote_root"]) / binding["gate_relative_file"])
    received_gate = fetch(binding["host"], remote_gate, gate_file, a.expected_gate_sha)
    gate = validate_job(case, schedule, binding, read(gate_file))
    require(gate["video"]["sha256"] == a.expected_video_sha, "Announced video SHA differs")
    received_video = fetch(binding["host"], gate["video"]["file"], video_file, a.expected_video_sha)
    write(folder / "TRANSFER_RECEIPT.json", {
        "host": binding["host"], "binding": bound(ROOT / "runtime" / a.case / (a.schedule + ".json")),
        "files": [
            {"remote": remote_gate, "local": bound(gate_file), "payload_bytes": received_gate},
            {"remote": gate["video"]["file"], "local": bound(video_file), "payload_bytes": received_video}],
        "network_payload_scope": "Only one per-job gate and one MP4; no tensor or recursive audit.",
        "GPU_started": False, "created_unix": time.time()})
    print(str(folder))


if __name__ == "__main__":
    main()
