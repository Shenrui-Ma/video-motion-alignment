"""Persist CPU-only verification evidence without loading a model or CUDA."""
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
import unittest

import torch

from .frozen import load_frozen


def main():
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise RuntimeError("Run with CUDA_VISIBLE_DEVICES='' for CPU verification")
    if torch.cuda.is_initialized():
        raise RuntimeError("CUDA was initialized before CPU verification")
    torch.set_num_threads(1)
    start = time.perf_counter()
    suite = unittest.defaultTestLoader.loadTestsFromName(__package__ + ".test_runtime")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    root = Path(__file__).resolve().parent
    evidence = {
        "scope": "CPU small-tensor algebra and fake Comfy block adaptation; no video validation",
        "passed": result.wasSuccessful() and not torch.cuda.is_initialized(),
        "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "seconds": time.perf_counter() - start, "python": platform.python_version(),
        "torch": torch.__version__, "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"],
        "cuda_initialized_after_tests": torch.cuda.is_initialized(), "torch_cpu_threads": torch.get_num_threads(),
        "gpu_inference_runs": 0, "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(root.glob("*.py"))},
        "frozen_dependency_sha256": load_frozen().hashes,
        "remaining": ["real Comfy/H3 node load and CUDA Flash compatibility",
                      "actual geometry wall time, peak memory and kernel overhead",
                      "paired video quality / editing / action-time measurements"],
    }
    path = root / "cpu_verification.json"
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(evidence, ensure_ascii=False))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
