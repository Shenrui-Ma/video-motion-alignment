"""Extract one fixed 49-frame clip with the pinned author CoTracker code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
CHECKPOINT_SHA = "dbb9006c0dc89479c34993ac23d37ae0af13deac18be6028009d7483754b2fc3"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_timebase(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                             "-show_entries", "stream=width,height,r_frame_rate,avg_frame_rate:frame=best_effort_timestamp_time",
                             "-of", "json", str(path)], check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    times = [float(frame["best_effort_timestamp_time"]) for frame in data["frames"]]
    if len(times) != 49 or any(abs(t - i / 8) > 1e-6 for i, t in enumerate(times)):
        raise ValueError("Metric input must contain exactly 49 frames at original timestamps j/8")
    return data


def check_gpu(uuid):
    if os.environ.get("CUDA_VISIBLE_DEVICES") != uuid:
        raise ValueError("Bind the exact admitted GPU UUID before starting")
    raw = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,gpu_uuid", "--format=csv,noheader,nounits"],
                         check=True, capture_output=True, text=True).stdout
    owned = set()
    processes = []
    for line in raw.strip().splitlines():
        pid, used_uuid = [x.strip() for x in line.split(",")]
        if used_uuid == uuid:
            raise ValueError("Selected GPU has an existing compute process")
        proc = Path("/proc") / pid
        if proc.exists() and proc.stat().st_uid == os.getuid():
            owned.add(used_uuid)
        processes.append({"pid": int(pid), "gpu_uuid": used_uuid})
    if len(owned) >= 2:
        raise ValueError("Two own GPUs are already occupied")
    mem = int(subprocess.run(["nvidia-smi", "-i", uuid, "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             check=True, capture_output=True, text=True).stdout.strip())
    if mem > 1024:
        raise ValueError("Selected GPU is not sufficiently released")
    return {"other_compute_processes": processes, "selected_memory_MiB": mem}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-manifest", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--gpu-uuid", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest_path = Path(args.input_manifest)
    manifest = json.loads(manifest_path.read_text())
    item = next(row for row in manifest["inputs"] if row["id"] == args.case)
    video = ROOT / item["file"]
    if sha(video) != item["sha256"]:
        raise ValueError("Video differs from precommitted input")
    if item["role"] == "generated" and item["generation_frame_indices"] != list(range(0, 147, 3)):
        raise ValueError("Generated frame map differs from the fixed 8 fps sampling")
    timing = check_timebase(video)
    for source in json.loads((ROOT / "VENDOR.json").read_text())["files"]:
        if sha(ROOT / source["file"]) != source["sha256"]:
            raise ValueError("Vendored source changed")
    checkpoint = ROOT / "weights/cotracker_stride_4_wind_8.pth"
    if sha(checkpoint) != CHECKPOINT_SHA:
        raise ValueError("Checkpoint changed")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    report = {"passed": False, "case": item, "manifest_sha256": sha(manifest_path),
              "timebase": timing, "gpu_uuid": args.gpu_uuid, "pid": os.getpid(), "uid": os.getuid(),
              "checkpoint_sha256": CHECKPOINT_SHA, "metric_functions_sha256": sha(ROOT / "METRIC_FUNCTIONS.json"),
              "vendor_manifest_sha256": sha(ROOT / "VENDOR.json"), "grid_size": 55, "mask": None}
    started = time.monotonic()
    try:
        report["admission"] = check_gpu(args.gpu_uuid)
        os.environ["OMP_NUM_THREADS"] = "2"
        os.environ["MKL_NUM_THREADS"] = "2"
        import torch
        torch.set_num_threads(2)
        sys.path.insert(0, str(ROOT / "vendor/co-tracker"))
        from cotracker.predictor import CoTrackerPredictor
        from metric_adapter import tracking_functions
        functions = tracking_functions()
        model = CoTrackerPredictor(checkpoint=str(checkpoint))
        report["admission_before_cuda"] = check_gpu(args.gpu_uuid)
        model = model.cuda()
        torch.cuda.synchronize()
        tracking_start = time.monotonic()
        tracks = functions["get_tracklets"](model, str(video), mask=None)
        torch.cuda.synchronize()
        report["tracking_seconds"] = time.monotonic() - tracking_start
        if list(tracks.shape) != [3025, 49, 2] or tracks.dtype != torch.float32:
            raise ValueError("Unexpected official tracker output shape or dtype")
        destination = output / "tracks.pt"
        torch.save({"tracks": tracks.cpu()}, destination)
        report.update({"passed": True, "tracks_shape": list(tracks.shape), "tracks_dtype": str(tracks.dtype),
                       "tracks_sha256": sha(destination), "nonfinite_track_values": int((~torch.isfinite(tracks)).sum()),
                       "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                       "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
                       "torch_version": torch.__version__, "cuda_version": torch.version.cuda})
    except Exception as exc:
        report["error"] = repr(exc)
        raise
    finally:
        report["wall_seconds"] = time.monotonic() - started
        (output / "REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k: v for k, v in report.items() if k not in ("timebase", "case")}))


if __name__ == "__main__":
    main()
