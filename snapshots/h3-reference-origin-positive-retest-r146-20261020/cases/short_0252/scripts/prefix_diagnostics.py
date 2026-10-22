"""Bounded CPU cross-host prediction diagnostics; equality is observational."""
import hashlib
import math
import torch

SAMPLE_COUNT = 1024


def summarize(tensor):
    if tensor.device.type != "cpu" or tensor.dtype != torch.float32 or not bool(torch.isfinite(tensor).all()):
        raise ValueError("expected finite CPU float32 prediction")
    flat = tensor.contiguous().view(-1)
    count = min(SAMPLE_COUNT, flat.numel())
    indices = torch.arange(count, dtype=torch.int64) * (flat.numel() - 1) // max(count - 1, 1)
    whole = flat.to(torch.float64)
    return {"shape": list(tensor.shape), "dtype": str(tensor.dtype),
            "tensor_sha256": hashlib.sha256(flat.numpy().tobytes()).hexdigest(),
            "numel": flat.numel(), "sample_count": count,
            "sample_indices": "floor(i*(numel-1)/(count-1)), i=0..count-1",
            "sample_values": flat[indices].tolist(),
            "rms": float(whole.square().mean().sqrt()), "mean": float(whole.mean()),
            "min": float(whole.min()), "max": float(whole.max())}


def compare(tensor, parent):
    actual = summarize(tensor)
    for key in ("shape", "dtype", "numel", "sample_count", "sample_indices"):
        if actual[key] != parent[key]:
            raise ValueError("prefix diagnostic schema differs: " + key)
    a = torch.tensor(actual["sample_values"], dtype=torch.float64)
    b = torch.tensor(parent["sample_values"], dtype=torch.float64)
    delta = a - b
    return {"full_tensor_sha256_equal": actual["tensor_sha256"] == parent["tensor_sha256"],
            "actual_tensor_sha256": actual["tensor_sha256"],
            "parent_tensor_sha256": parent["tensor_sha256"],
            "sample_count": actual["sample_count"], "sample_indices": actual["sample_indices"],
            "sample_difference_rms": float(delta.square().mean().sqrt()),
            "sample_difference_max_abs": float(delta.abs().max()),
            "actual_whole_tensor_rms": actual["rms"], "parent_whole_tensor_rms": parent["rms"],
            "actual_whole_tensor_mean": actual["mean"], "parent_whole_tensor_mean": parent["mean"],
            "equality_required": False, "reason": "historical R122 host9 vs current host41; no environment repeat"}
