"""Small dense numerical diagnostics; never use this oracle for full H3 inputs."""

import math


def fp32_attention(q, k, v):
    """Noncausal FP32 dense oracle on the exact supplied (possibly low-bit) QKV."""
    import torch

    logits = torch.matmul(q.float(), k.float().transpose(-1, -2)) / math.sqrt(q.shape[-1])
    return torch.matmul(logits.softmax(-1), v.float()), logits.logsumexp(-1)


def flash_attention_lse(q, k, v):
    """Same explicit ATen Flash seam as R142; never math/SDPA fallback."""
    import torch

    if q.device.type != "cuda" or q.dtype not in (torch.float16, torch.bfloat16):
        raise ValueError("Flash check requires CUDA fp16/bf16 tensors")
    out, lse = torch.ops.aten._scaled_dot_product_flash_attention.default(
        q, k, v, 0.0, False, False
    )[:2]
    if out.shape != q.shape or lse.shape != q.shape[:-1]:
        raise ValueError("unexpected Flash output/LSE shape")
    return out, lse


def mass_preserve(full, reference, aligned, full_lse, reference_lse, *, alpha):
    """FP32 correction with raw exp(ln Z_ref - ln Z_full); deliberately no clamp.

    alpha=0 returns the original full output before reading the correction.
    Other alpha values return FP32 so comparison retains pre-cast error.
    """
    if not math.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ValueError("alpha must be finite and in [0,1]")
    if alpha == 0:
        return full
    if full.shape != reference.shape or full.shape != aligned.shape:
        raise ValueError("attention output shape mismatch")
    if full_lse.shape != full.shape[:-1] or reference_lse.shape != full_lse.shape:
        raise ValueError("LSE shape mismatch")
    log_mass = reference_lse.float() - full_lse.float()
    return full.float() + alpha * log_mass.exp().unsqueeze(-1) * (
        aligned.float() - reference.float()
    )


def error_metrics(actual, expected):
    """Absolute and RMS errors; relative RMS denominator is reported explicitly."""
    diff = actual.float() - expected.float()
    reference_rms = expected.float().square().mean().sqrt().item()
    rms = diff.square().mean().sqrt().item()
    return {
        "max_abs": diff.abs().max().item(),
        "rms": rms,
        "reference_rms": reference_rms,
        "relative_rms": rms / reference_rms if reference_rms else None,
    }


def make_case(torch, name, *, device, dtype, dim=64, seed=20261020):
    """Unequal, non-block lengths plus distinct reference/complement K means."""
    generator = torch.Generator(device="cpu").manual_seed(seed)
    q = torch.randn((2, 3, 19, dim), generator=generator) * 0.2
    k = torch.randn((2, 3, 131, dim), generator=generator) * 0.2
    v = torch.randn((2, 3, 131, dim), generator=generator)
    reference = slice(23, 90)  # 67 keys; aligned subset has 17 keys.
    aligned = slice(31, 48)
    if name == "different_k_means":
        k[:, :, :23] += 4
        k[:, :, reference] -= 3
        k[:, :, 90:] += 2
    elif name in ("mass_near_zero", "mass_near_one"):
        q[..., 0] = math.sqrt(dim)
        k[..., 0] = 0
        k[:, :, reference, 0] = -12 if name == "mass_near_zero" else 12
    elif name != "random":
        raise ValueError(f"unknown case: {name}")
    return tuple(x.to(device=device, dtype=dtype) for x in (q, k, v)), reference, aligned
