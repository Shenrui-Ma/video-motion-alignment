"""Bound single GPU child; recheck admission, monitor memory, verify release."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def identity(pid):
    try:
        path = Path("/proc") / str(pid)
        tail = (path / "stat").read_text().rsplit(")", 1)[1].split()
        if tail[0] == "Z":
            return None
        return {"pid": pid, "uid": path.stat().st_uid, "start_ticks": int(tail[19]),
                "cmdline_sha256": hashlib.sha256((path / "cmdline").read_bytes()).hexdigest()}
    except (FileNotFoundError, ProcessLookupError):
        return None


def query(uuid):
    row = subprocess.check_output([
        "nvidia-smi", "-i", uuid,
        "--query-gpu=uuid,memory.free,memory.total,utilization.gpu",
        "--format=csv,noheader,nounits"], text=True, timeout=10).strip().split(", ")
    assert row[0] == uuid
    apps = subprocess.check_output([
        "nvidia-smi", "-i", uuid, "--query-compute-apps=pid,used_gpu_memory",
        "--format=csv,noheader,nounits"], text=True, timeout=10)
    processes = []
    for line in apps.strip().splitlines():
        pid, memory = line.split(", ")
        processes.append({"pid": int(pid), "used_mib": int(memory) if memory.isdigit() else None})
    return {"uuid": uuid, "free_mib": int(row[1]), "total_mib": int(row[2]),
            "utilization": int(row[3]), "processes": processes}


def main():
    def interrupt(signum, _frame):
        raise SystemExit(128 + signum)
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, interrupt)
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--steps", type=int, nargs="+", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    manifest = json.loads(args.manifest.read_text())
    output = args.output.resolve()
    assert output.is_relative_to(root)
    output.mkdir(parents=True, exist_ok=False)
    uuid = manifest["gpu_uuid"]
    assert uuid == "GPU-REDACTED"
    selected = [s for s in manifest["steps"] if s["step"] in args.steps]
    assert len(selected) == len(args.steps)
    for entry in manifest["weights"] + [s["video"] for s in selected]:
        h = hashlib.sha256()
        with Path(entry["file"]).open("rb") as f:
            for data in iter(lambda: f.read(1 << 20), b""):
                h.update(data)
        assert h.hexdigest() == entry["sha256"], entry["file"]
    before = query(uuid)
    write(output / "BEFORE.json", before)
    assert before["free_mib"] >= 8192, "GPU admission: need at least 8 GiB free"
    command = [sys.executable, str(root / "pose_probe_gpu.py"), "--output-dir",
               str(output / "poses"), "--aux-root", manifest["aux_root"],
               "--threads", "4", "--stride", "1", "--backend", "gpu", "--gpu-uuid", uuid]
    for step in selected:
        command.extend(["--video", step["video"]["file"]])
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=uuid, PYTHONDONTWRITEBYTECODE="1",
               NVIDIA_TF32_OVERRIDE="0", OMP_NUM_THREADS="4", MKL_NUM_THREADS="4",
               OPENBLAS_NUM_THREADS="4")
    env["LD_LIBRARY_PATH"] = manifest["LD_LIBRARY_PATH"]
    child = None
    owner = None
    started = time.monotonic()
    samples = []
    error = None
    try:
        with (output / "probe.log").open("wb") as log:
            child = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            expected = hashlib.sha256(b"\0".join(os.fsencode(x) for x in command) + b"\0").hexdigest()
            for _ in range(100):
                owner = identity(child.pid)
                if owner and owner["cmdline_sha256"] == expected:
                    break
                if child.poll() is not None:
                    raise RuntimeError("Probe exited before identity binding")
                time.sleep(.01)
            assert owner and owner["cmdline_sha256"] == expected and owner["uid"] == os.getuid()
            write(output / "PROCESS.json", {"identity": owner, "command": command})
            while child.poll() is None:
                snapshot = query(uuid)
                samples.append({"elapsed_s": time.monotonic() - started, **snapshot})
                write(output / "MEMORY_SAMPLES.json", samples)
                if time.monotonic() - started > max(240, len(selected) * 180):
                    raise TimeoutError("Bound observation GPU probe timeout")
                if snapshot["free_mib"] < 4096:
                    raise RuntimeError("GPU free memory fell below 4 GiB during isolated trial")
                time.sleep(.5)
            if child.returncode:
                raise RuntimeError(f"Probe exit {child.returncode}; see probe.log")
    except BaseException as exc:
        error = type(exc).__name__ + ": " + str(exc)
    finally:
        if child is not None and child.poll() is None:
            if owner and identity(child.pid) == owner:
                fd = os.pidfd_open(child.pid)
                try:
                    if identity(child.pid) == owner:
                        signal.pidfd_send_signal(fd, signal.SIGTERM)
                finally:
                    os.close(fd)
            else:
                # A direct child whose exec binding failed is still ours until reaped.
                child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                if owner and identity(child.pid) == owner:
                    fd = os.pidfd_open(child.pid)
                    try:
                        if identity(child.pid) == owner:
                            signal.pidfd_send_signal(fd, signal.SIGKILL)
                    finally:
                        os.close(fd)
                    child.wait(timeout=10)
        after = query(uuid)
        for _ in range(30):
            absent = not owner or identity(owner["pid"]) != owner
            cuda_absent = not owner or all(p["pid"] != owner["pid"] for p in after["processes"])
            if absent and cuda_absent:
                break
            time.sleep(1)
            after = query(uuid)
        owned_samples = [p["used_mib"] for s in samples for p in s["processes"]
                         if owner and p["pid"] == owner["pid"] and p["used_mib"] is not None]
        write(output / "RELEASE.json", {
            "identity": owner, "exact_generation_absent": absent, "own_CUDA_pid_absent": cuda_absent,
            "returncode": child.returncode if child else None, "error": error,
            "wall_s": time.monotonic() - started, "sampled_own_peak_mib": max(owned_samples, default=0),
            "after": after, "other_processes_signaled": [],
        })
    if error:
        raise RuntimeError(error)
    assert absent and cuda_absent


if __name__ == "__main__":
    main()
