"""Repeatable CPU validation with machine-readable evidence; no CUDA init."""

import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import unittest

import torch


def main():
    root = Path(__file__).resolve().parent
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise RuntimeError("set CUDA_VISIBLE_DEVICES='' explicitly for this CPU-only verification")
    if torch.cuda.is_initialized():
        raise RuntimeError("CUDA was already initialized")
    torch.set_num_threads(1)
    suite = unittest.defaultTestLoader.loadTestsFromName("temporal_coverage.test_temporal_coverage")
    with (root / "cpu_test_output.txt").open("w") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    report = {
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "python": sys.version,
        "torch": torch.__version__,
        "platform": platform.platform(),
        "device": "cpu",
        "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"],
        "cuda_initialized_after_tests": torch.cuda.is_initialized(),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "successful": result.wasSuccessful() and not torch.cuda.is_initialized(),
        "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted(root.glob("*.py"))},
        "not_run": ["CUDA/Flash execution", "ComfyUI model-patcher runtime integration",
                    "H3 DiT inference", "VAE decoding", "video quality or speed measurement"],
    }
    (root / "cpu_validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
