"""Frozen utility excerpts; source SHA256 7f21d35d58ff8e36f9c0e0d0e819917e680ebd7095c69a28bda40b34a56836e1. No live imports."""
import math

def flash_attention_lse(q, k, v):
    """Explicit CUDA Flash backend. Dense/math fallback is deliberately absent."""
    import torch

    if q.device.type != "cuda" or q.dtype not in (torch.float16, torch.bfloat16):
        raise ValueError("production Flash backend requires CUDA fp16/bf16 tensors")
    if any(x.ndim != 4 or x.stride(-1) != 1 for x in (q, k, v)):
        raise ValueError("expected [B,H,N,D] tensors with contiguous last dimension")
    result = torch.ops.aten._scaled_dot_product_flash_attention.default(
        q, k, v, 0.0, False, False
    )
    out, lse = result[:2]
    if out.shape != q.shape or lse.shape != q.shape[:-1]:
        raise ValueError(f"unexpected Flash output/LSE shapes: {out.shape}, {lse.shape}")
    return out, lse


def _bounded_stats(before, after, mass, lse_delta):
    """Sample at most 8 heads x 128 queries x 16 channels, without host sync."""
    import torch

    hs = max(1, math.ceil(before.shape[1] / 8))
    qs = max(1, math.ceil(before.shape[2] / 128))
    ds = max(1, math.ceil(before.shape[3] / 16))
    a = before[:, ::hs, ::qs, ::ds].float()
    b = after[:, ::hs, ::qs, ::ds].float()
    m = mass[:, ::hs, ::qs].float()
    delta = lse_delta[:, ::hs, ::qs].float()
    finite = torch.isfinite(a).all() & torch.isfinite(b).all() & torch.isfinite(m).all()
    return torch.stack((m.mean(), m.max(),
                        (b - a).square().mean().sqrt() / a.square().mean().sqrt().clamp_min(1e-8),
                        finite.float(), delta.max())).detach()
