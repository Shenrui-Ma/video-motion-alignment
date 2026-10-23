"""Reference-branch-only compensation of selected H3 temporal RoPE pairs.

Q/K arrive after native RMSNorm and split-half RoPE. Never mutate them.
The audited source layout is [t16,h16,w16,t16,h16,w16,unrotated32].
"""

import hashlib
import json
import math

import torch

from .layout import FRAME_RESCALE


def parse_frequency_mask(value):
    """Sixteen explicit binary entries, in the checkpoint buffer's order."""
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, (tuple, list)) or len(value) != 16:
        raise ValueError("frequency_mask must contain exactly 16 binary entries")
    if any(type(v) not in (int, bool) or v not in (0, 1) for v in value):
        raise ValueError("frequency_mask entries must be binary integers or booleans")
    return tuple(bool(v) for v in value)


class PartialTemporalRotation:
    """Add delta_frames*5/3 to selected temporal Q pairs after native RoPE.

This changes the phase offset, not the checkpoint frequency buffer. Alpha is
kept outside this class and blends the reference-conditional output correction.
"""

    def __init__(self, inv_freq, delta_frames, frequency_mask):
        if not isinstance(inv_freq, torch.Tensor) or tuple(inv_freq.shape) != (16,):
            raise ValueError("actual H3 rope.inv_freq must have exactly 16 entries")
        if not inv_freq.is_floating_point():
            raise ValueError("rope.inv_freq must be floating point")
        self.inv_freq = inv_freq.detach().to(device="cpu", copy=True).contiguous()
        if not bool(torch.isfinite(self.inv_freq).all()):
            raise ValueError("rope.inv_freq contains nonfinite values")
        if isinstance(delta_frames, bool) or not math.isfinite(float(delta_frames)):
            raise ValueError("delta_frames must be a finite physical-frame offset")
        self.delta_frames = float(delta_frames)
        self.delta_rope = self.delta_frames * FRAME_RESCALE
        if not math.isfinite(self.delta_rope):
            raise ValueError("RoPE offset overflow")
        self.frequency_mask = parse_frequency_mask(frequency_mask)
        self.indices = tuple(i for i, active in enumerate(self.frequency_mask) if active)
        self.is_identity = self.delta_frames == 0 or not self.indices
        self.cache = {}

    def __call__(self, query):
        if query.ndim != 4 or query.shape[-1] != 128 or not query.is_floating_point():
            raise ValueError("expected post-RoPE floating point [B,H,N,128] query")
        if self.is_identity:
            return query
        work_dtype = torch.float64 if query.dtype == torch.float64 else torch.float32
        cache_key = (str(query.device), work_dtype)
        if cache_key not in self.cache:
            first = torch.tensor(self.indices, dtype=torch.long, device=query.device)
            angles = self.inv_freq[list(self.indices)].to(query.device, work_dtype) * self.delta_rope
            if not bool(torch.isfinite(angles).all()):
                raise ValueError("nonfinite rotation angles")
            self.cache[cache_key] = (first, first + 48, angles.cos(), angles.sin())
        first, second, cosine, sine = self.cache[cache_key]
        x = query.index_select(-1, first).to(work_dtype)
        y = query.index_select(-1, second).to(work_dtype)
        rotated = query.clone()
        rotated[..., first] = (x * cosine - y * sine).to(query.dtype)
        rotated[..., second] = (x * sine + y * cosine).to(query.dtype)
        return rotated

    def metadata(self):
        frequencies = self.inv_freq.double().tolist()
        return {
            "delta_physical_frames": self.delta_frames,
            "delta_rope_units": self.delta_rope,
            "frame_rescale": FRAME_RESCALE,
            "frequency_mask": [int(v) for v in self.frequency_mask],
            "selected_pair_indices": list(self.indices),
            "rotated_channel_pairs": [[i, i + 48] for i in self.indices],
            "inv_freq": frequencies,
            "inv_freq_dtype": str(self.inv_freq.dtype),
            "inv_freq_sha256": hashlib.sha256(self.inv_freq.view(torch.uint8).numpy().tobytes()).hexdigest(),
            "frequency_source": "actual diffusion.rope.inv_freq buffer; no guessed frequency base/order",
            "selected_periods_physical_frames": [
                None if frequencies[i] == 0 else 2 * math.pi / abs(frequencies[i] * FRAME_RESCALE)
                for i in self.indices],
            "spatial_channels_unchanged": [[16, 48], [64, 96]],
            "non_rope_channels_unchanged": [96, 128],
            "positive_delta": "adds to query time coordinate; output motion-lag sign needs measurement",
        }


def flash_attention_lse(q, k, v):
    """Same explicit Flash/LSE backend as frozen H3Study; no dense fallback."""
    if q.device.type != "cuda" or q.dtype not in (torch.float16, torch.bfloat16):
        raise ValueError("production Flash backend requires CUDA fp16/bf16 tensors")
    if any(x.ndim != 4 or x.stride(-1) != 1 for x in (q, k, v)):
        raise ValueError("expected [B,H,N,D] tensors with contiguous last dimension")
    out, lse = torch.ops.aten._scaled_dot_product_flash_attention.default(
        q, k, v, 0.0, False, False)[:2]
    if out.shape != q.shape or lse.shape != q.shape[:-1]:
        raise ValueError("unexpected Flash output/LSE shapes")
    return out, lse


def partial_phase_attention(q, k, v, heads, plan, *, rotation, alpha=1.0,
                            enabled=True, attention=flash_attention_lse,
                            diagnostics=None):
    """O + alpha*m_ref*(A(R_mask(delta)Q,K_ref,V_ref)-A(Q,K_ref,V_ref)).

The full joint attention sees original Q/K/V. The extra branch sees output
video queries and all reference-video K/V, excluding the identity-image rows.
Only the chosen output rows are replaced. m_ref is measured before rotation.
"""
    if type(enabled) is not bool:
        raise ValueError("enabled must be boolean")
    if isinstance(alpha, bool) or not math.isfinite(float(alpha)) or not 0 <= alpha <= 1:
        raise ValueError("alpha must be finite and within [0,1]")
    if q.ndim != 4 or q.shape != k.shape or k.shape != v.shape or q.shape[0] != 1:
        raise ValueError("expected equal single-batch [B,H,N,D] self-attention tensors")
    if q.shape[1] != heads or q.shape[-1] != 128 or not q.is_floating_point():
        raise ValueError("unexpected H3 heads/head dimension or dtype")
    if any(t.device != q.device or t.dtype != q.dtype for t in (k, v)):
        raise ValueError("QKV device/dtype mismatch")
    full, full_lse = attention(q, k, v)
    if not enabled or alpha == 0 or rotation.is_identity:
        return full.transpose(1, 2).reshape(1, q.shape[-2], heads * 128)
    qa, qb = plan["query_interval_half_open"]
    ra, rb = plan["reference_video_segment"]
    ta, tb = plan["target_video_segment"]
    if not (0 <= ra < rb <= q.shape[-2] and 0 <= ta <= qa < qb <= tb <= q.shape[-2]):
        raise ValueError("selected ranges must be valid output/reference-video rows")
    if max(qa, ra) < min(qb, rb):
        raise ValueError("output-video query and reference-video segments overlap")
    if any(max(ra, a) < min(rb, b) for a, b in plan.get("reference_image_segments", [])):
        raise ValueError("reference-video branch overlaps identity-image rows")
    query, keys, values = q[:, :, qa:qb], k[:, :, ra:rb], v[:, :, ra:rb]
    original_ref, original_lse = attention(query, keys, values)
    rotated_ref, _ = attention(rotation(query), keys, values)
    work_dtype = torch.float64 if q.dtype == torch.float64 else torch.float32
    log_mass = original_lse.to(work_dtype) - full_lse[:, :, qa:qb].to(work_dtype)
    mass = log_mass.clamp(max=0).exp()
    before = full[:, :, qa:qb]
    correction = alpha * mass.unsqueeze(-1) * (rotated_ref.to(work_dtype) - original_ref.to(work_dtype))
    changed = (before.to(work_dtype) + correction).to(before.dtype)
    if diagnostics is not None:
        # Only scalar reductions are retained until the end-of-forward CPU audit.
        diagnostics.append(torch.stack((mass.mean(), mass.max(), log_mass.max(),
            correction.square().mean().sqrt(), torch.isfinite(changed).all().to(work_dtype))).detach())
    full[:, :, qa:qb].copy_(changed)
    return full.transpose(1, 2).reshape(1, q.shape[-2], heads * 128)
