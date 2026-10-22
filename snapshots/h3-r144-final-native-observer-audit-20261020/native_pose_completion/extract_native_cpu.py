"""One CPU-only final Native pose extraction using the exact existing source recipe."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GIB = 2**30


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_new(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def identity(pid):
    p = Path("/proc") / str(pid)
    try:
        before = (p / "stat").read_text().rsplit(") ", 1)[1].split()
        command = (p / "cmdline").read_bytes()
        after = (p / "stat").read_text().rsplit(") ", 1)[1].split()
        if before[19] != after[19] or after[0] == "Z" or not command:
            return None
        return {"pid": pid, "uid": p.stat().st_uid, "start_ticks": int(after[19]),
                "cmdline_sha256": hashlib.sha256(command).hexdigest()}
    except FileNotFoundError:
        return None


def capacity(old):
    sys.path.insert(0, str(old / "scripts"))
    import cgroup_memory
    from working_set_capacity import file_credit
    snapshot = cgroup_memory.snapshot()
    assert snapshot["uid"] == 1004
    rows = []
    for row in snapshot["ancestors"]:
        if row.get("high_bytes") is None:
            continue
        _, credit = file_credit(row["stat"], 6 * GIB)
        adjusted = row["current_bytes"] - min(row["current_bytes"], credit)
        rows.append({"path": row["path"], "adjusted_high_headroom_bytes": row["high_bytes"] - adjusted})
    assert rows and any(r["path"] == "/user.slice" for r in rows)
    return {"admitted": all(r["adjusted_high_headroom_bytes"] >= 18 * GIB for r in rows),
            "minimum_high_headroom_bytes": 18 * GIB, "PSI_role": "diagnostic_only",
            "adjusted": rows, "snapshot": snapshot}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("long_0039", "short_0358"), required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "EXTRACTION_MANIFEST.json").read_text())
    job = manifest["jobs"][args.case]
    old = Path(manifest["original_root"])
    output = ROOT / args.case
    output.mkdir(exist_ok=False)
    receipt = {"source_id": args.case, "started_unix": time.time(), "wrapper_identity": identity(os.getpid()),
               "status": "preflight", "GPU_started": False}
    write_new(output / "WRAPPER.json", receipt)
    probe = old / "scripts/pose_probe.py"
    assert sha(probe) == manifest["probe_sha256"]
    assert sha(old / "scripts/adult_selector.py") == manifest["selector_sha256"]
    assert sha(job["video"]) == job["video_sha256"]
    assert sha(job["source_pose"]) == job["source_pose_sha256"]
    source = json.loads(Path(job["source_pose"]).read_text())
    for name, expected in manifest["existing_model_and_code"].items():
        assert sha(name) == expected, name
    for key in ("detector_sha256", "pose_sha256", "detector_code_sha256", "pose_code_sha256"):
        assert source["provenance"][key] == job["source_provenance"][key], key
    assert source["provenance"]["providers"] == ["CPUExecutionProvider"]
    assert source["provenance"]["device"] == "cpu" and source["provenance"]["threads"] == 4
    before = capacity(old)
    write_new(output / "CAPACITY_BEFORE.json", before)
    if not before["admitted"]:
        write_new(output / "EXIT.json", {**receipt, "status": "blocked_capacity_before_CPU",
                                       "finished_unix": time.time()})
        return 3
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="", PYTHONDONTWRITEBYTECODE="1",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               OMP_NUM_THREADS="4", MKL_NUM_THREADS="4", OPENBLAS_NUM_THREADS="4", NUMEXPR_NUM_THREADS="4")
    command = [sys.executable, str(probe), "--video", job["video"], "--output-dir", str(output / "raw"),
               "--aux-root", manifest["aux_root"], "--threads", "4", "--stride", "1"]
    expected_command = hashlib.sha256(b"\0".join(os.fsencode(x) for x in command) + b"\0").hexdigest()
    started = time.monotonic()
    with (output / "pose_cpu.log").open("x") as log:
        child = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            entry = None
            for _ in range(100):
                candidate = identity(child.pid)
                if candidate and candidate["cmdline_sha256"] == expected_command:
                    entry = candidate
                    break
                if child.poll() is not None:
                    break
                time.sleep(.01)
            assert entry and entry["uid"] == 1004, "CPU child identity unavailable"
            write_new(output / "CHILD.json", {"identity": entry, "command": command,
                                             "CUDA_VISIBLE_DEVICES": "", "threads": 4,
                                             "network_downloads": False})
            print(json.dumps({"started": args.case, "identity": entry,
                              "high_headroom_GiB": [x["adjusted_high_headroom_bytes"] / GIB
                                                    for x in before["adjusted"]]}), flush=True)
            code = child.wait(timeout=600)
        except BaseException:
            # Popen owns this unreaped child, so its PID cannot be recycled here.
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            raise
    receipt.update(returncode=code, child_identity=entry, CPU_wall_seconds=time.monotonic() - started,
                   child_generation_absent=identity(child.pid) != entry, finished_unix=time.time())
    if code:
        write_new(output / "EXIT.json", {**receipt, "status": "failed_CPU_extraction"})
        return code
    pose = output / "raw" / (Path(job["video"]).stem + ".pose.json")
    raw = json.loads(pose.read_text())
    assert raw["video"]["sha256"] == job["video_sha256"]
    assert raw["provenance"]["providers"] == ["CPUExecutionProvider"]
    assert raw["provenance"]["device"] == "cpu" and raw["provenance"]["threads"] == 4
    for key in ("detector_sha256", "pose_sha256", "detector_code_sha256", "pose_code_sha256",
                "script_sha256", "torch", "opencv", "onnxruntime"):
        assert raw["provenance"][key] == source["provenance"][key], key
    from adult_selector import adult_only
    filtered, rejected = adult_only(raw, job["geometry"], job["bounds"])
    final = output / "native.selected.pose.json"
    write_new(final, filtered)
    write_new(output / "SELECTION.json", {"bounds": job["bounds"], "rejected_frames": rejected,
                                        "raw_pose_sha256": sha(pose), "selected_pose_sha256": sha(final),
                                        "selector": "original largest/IoU choice kept only within frozen source bbox bounds",
                                        "content_boundary_filter": False, "no_reselection": True})
    write_new(output / "CAPACITY_AFTER.json", capacity(old))
    receipt.update(status="complete", raw_pose=str(pose), raw_pose_sha256=sha(pose),
                   selected_pose=str(final), selected_pose_sha256=sha(final),
                   processed_frames=len(raw["frames"]), valid_frames=job["valid_frames"],
                   ROI_rejected_frames=rejected, original_source_recipe_equal=True)
    write_new(output / "EXIT.json", receipt)
    print(json.dumps(receipt), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
