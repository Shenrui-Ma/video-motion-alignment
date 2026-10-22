"""CPU-only compatibility check for the pinned public evaluation runtime."""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import argparse
import hashlib
import importlib.metadata
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Keep each compatibility attempt separately")
    start = time.monotonic()
    receipt = {"passed": False, "CUDA_VISIBLE_DEVICES": os.environ["CUDA_VISIBLE_DEVICES"]}
    try:
        for item in json.loads((ROOT / "VENDOR.json").read_text())["files"]:
            if sha(ROOT / item["file"]) != item["sha256"]:
                raise ValueError("Vendored source hash mismatch")
        checkpoint = ROOT / "weights/cotracker_stride_4_wind_8.pth"
        if sha(checkpoint) != "dbb9006c0dc89479c34993ac23d37ae0af13deac18be6028009d7483754b2fc3":
            raise ValueError("Checkpoint hash mismatch")
        import torch
        torch.set_num_threads(1)
        sys.path.insert(0, str(ROOT / "vendor/co-tracker"))
        import cotracker.predictor
        from cotracker.predictor import CoTrackerPredictor
        from metric_adapter import tracking_functions, scoring_functions
        tracking_functions()
        scoring_functions()
        model = CoTrackerPredictor(checkpoint=str(checkpoint))
        receipt.update({"predictor_path": cotracker.predictor.__file__,
                        "parameters": sum(p.numel() for p in model.parameters()),
                        "parameter_devices": sorted({str(p.device) for p in model.parameters()}),
                        "cuda_initialized": torch.cuda.is_initialized(),
                        "versions": {name: importlib.metadata.version(name) for name in ("torch", "numpy", "einops", "timm")},
                        "checkpoint_sha256": sha(checkpoint), "model_forwards": 0})
        if receipt["cuda_initialized"] or receipt["parameter_devices"] != ["cpu"]:
            raise ValueError("Expected CPU-only checkpoint loading")
        receipt["passed"] = True
    except Exception as exc:
        receipt["error"] = repr(exc)
        raise
    finally:
        receipt["wall_seconds"] = time.monotonic() - start
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt))


if __name__ == "__main__":
    main()
