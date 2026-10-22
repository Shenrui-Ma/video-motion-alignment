"""R17 phase operator configured by actual reference/target clock origins.

Existing-method control. Original joint Q/K/V, PackedLayout and RoPE table are
read only. The auxiliary reference-video branch rotates only video queries.
"""
import hashlib
import math

from .alignment import aligned_positions
from .core import (RouterState, EventBlockPatch, flash_attention_lse,
                   route_attention, temporal_readout, _bounded_stats)


class TemporalPhaseRotation:
    """Same temporal channel pairs as R17, expressed directly in RoPE units."""
    def __init__(self, inv_freq, displacement):
        import torch
        if (not isinstance(inv_freq, torch.Tensor) or inv_freq.shape != (16,)
                or not inv_freq.is_floating_point() or not math.isfinite(displacement)):
            raise ValueError("invalid actual checkpoint temporal frequency or displacement")
        self.inv_freq = inv_freq.detach().to(device="cpu", copy=True).contiguous()
        if not torch.isfinite(self.inv_freq).all():
            raise ValueError("nonfinite checkpoint temporal frequency")
        self.displacement = float(displacement)
        self.cache = {}

    def __call__(self, query):
        import torch
        if query.ndim != 4 or query.shape[-1] != 128 or not query.is_floating_point():
            raise ValueError("expected H3 [B,H,N,128] query")
        if self.displacement == 0:
            return query
        dtype = torch.float64 if query.dtype == torch.float64 else torch.float32
        key = (query.device, dtype)
        if key not in self.cache:
            angles = self.inv_freq.to(device=query.device, dtype=dtype) * self.displacement
            self.cache[key] = (angles.cos(), angles.sin())
        cosine, sine = self.cache[key]
        a, b = query[..., :16].to(dtype), query[..., 48:64].to(dtype)
        result = query.clone()
        result[..., :16] = (a * cosine - b * sine).to(query.dtype)
        result[..., 48:64] = (a * sine + b * cosine).to(query.dtype)
        return result

    def metadata(self):
        import torch
        return {
            "displacement_rope_units": self.displacement,
            "frequency_source": "actual diffusion.rope.inv_freq checkpoint buffer",
            "inv_freq": self.inv_freq.double().tolist(),
            "inv_freq_dtype": str(self.inv_freq.dtype),
            "inv_freq_sha256": hashlib.sha256(self.inv_freq.view(torch.uint8).numpy().tobytes()).hexdigest(),
            "time_channel_pairs": [[0, 16], [48, 64]],
            "math": "R_t(reference_origin-target_origin) q in auxiliary video-reference branch",
            "arithmetic": "float32 angles and products for fp16/bf16; cast once to query dtype",
        }


def origin_attention(q, k, v, heads, plan, rotation, *, alpha=1.0,
                     attention=flash_attention_lse, diagnostics=None):
    """O + alpha*m_ref*(softmax(R_t(-Delta)q K_R)V_R - z_original)."""
    import torch
    if (not math.isfinite(alpha) or not 0 <= alpha <= 1 or q.ndim != 4
            or q.shape != k.shape or k.shape != v.shape or q.shape[0] != 1
            or q.shape[1] != heads or q.shape[-1] != 128
            or any(x.device != q.device or x.dtype != q.dtype for x in (k, v))):
        raise ValueError("invalid single-batch H3 self-attention or alpha")
    full, full_lse = attention(q, k, v)
    if alpha == 0 or rotation.displacement == 0:
        return full.transpose(1, 2).reshape(1, q.shape[-2], heads * q.shape[-1])
    qa, qb = plan["query_interval_half_open"]
    ra, rb = plan["reference_video_segment"]
    va, vb = plan["target_video_segment"]
    if not (0 <= ra < rb <= k.shape[-2] and 0 <= va <= qa < qb <= vb <= q.shape[-2]):
        raise ValueError("auxiliary branch must stay within target video queries and video reference keys")
    query, keys, values = q[:, :, qa:qb], k[:, :, ra:rb], v[:, :, ra:rb]
    original, ref_lse = attention(query, keys, values)
    shifted, _ = attention(rotation(query), keys, values)
    dtype = torch.float64 if q.dtype == torch.float64 else torch.float32
    log_mass = ref_lse.to(dtype) - full_lse[:, :, qa:qb].to(dtype)
    mass = log_mass.clamp(max=0).exp()
    before = full[:, :, qa:qb]
    changed = (before.to(dtype) + alpha * mass.unsqueeze(-1) *
               (shifted.to(dtype) - original.to(dtype))).to(before.dtype)
    if diagnostics is not None:
        diagnostics.append(_bounded_stats(before, changed, mass, log_mass))
    full[:, :, qa:qb].copy_(changed)
    return full.transpose(1, 2).reshape(1, q.shape[-2], heads * q.shape[-1])


class ReferenceOriginState(RouterState):
    def __init__(self, *args, inv_freq, **kwargs):
        import torch
        super().__init__(*args, **kwargs)
        self.actual_inv_freq = inv_freq.detach().to(device="cpu", copy=True)
        self.origin_layout = self.original_positions = self.rotation = None
        self.audit["reference_origin"] = {
            "configuration": "R17 operator with actual reference-origin displacement",
            "new_method_claim": False, "original_QKV_and_table_preserved": True,
            "extra_query_scope": "target_video_only", "reference_scope": "all_video_reference_keys",
            "mass_source": "original_reference_LSE_minus_original_joint_LSE",
            "first_six_prediction_equality_required": False,
            "layout_validation_count": 0, "rotation_calls": 0,
            "original_rope_table_calls": 0,
        }

    def prepare_origin(self, layout):
        import torch
        if self.origin_layout is None:
            # Reuse the canonical validation; do not install its derived positions.
            derived, details = aligned_positions(layout, self.metadata)
            del derived
            self.origin_layout, self.original_positions = layout, layout.position_ids.clone()
            self.rotation = TemporalPhaseRotation(self.actual_inv_freq, details["target_time_displacement"])
            self.audit["reference_origin"].update(layout=details, rotation=self.rotation.metadata(),
                                                   layout_validation_count=1)
        if layout is not self.origin_layout:
            raise ValueError("PackedLayout identity changed")
        if self.next_block == 0 and not torch.equal(layout.position_ids, self.original_positions):
            raise ValueError("original PackedLayout was modified")


class ReferenceOriginAttentionOverride:
    def __init__(self, state, plan, block):
        self.state, self.plan, self.block, self.calls = state, plan, block, 0

    def __call__(self, native, q, k, v, heads, **kwargs):
        if getattr(native, "__name__", None) != "attention_pytorch":
            raise ValueError("registered attention_pytorch entry required")
        if kwargs.get("mask") is not None or not kwargs.get("skip_reshape") or kwargs.get("skip_output_reshape", False):
            raise ValueError("expected unmasked preshaped native attention")
        if q.shape[-2] != self.plan["seq_len"]:
            raise ValueError("packed attention length differs")
        self.calls += 1
        if self.calls != 1:
            raise ValueError("expected one attention per block")
        state = self.state
        if self.block == 25 and state.forward_index in (0, 5, 10, 15, 19):
            record = temporal_readout(q, k, self.plan)
            record.update(block_index=self.block, forward_index=state.forward_index)
            state.audit["temporal_readouts"].append(record)
        active = state.selected(self.block) and state.alpha != 0
        stats = []
        if active:
            out = origin_attention(q, k, v, heads, self.plan, state.rotation,
                                   alpha=state.alpha, diagnostics=stats)
            state.audit["routed_calls"] += 1
            state.audit["routed_by_block"][self.block] += 1
            state.audit["routed_by_forward"][state.forward_index] += 1
            state.audit["reference_origin"]["rotation_calls"] += 1
        else:
            out = route_attention(q, k, v, heads, self.plan, mode="native")
        state.audit["native_override_calls"] += 1
        if stats:
            state.pending_stats.append((self.block, stats[0]))
        if "first_attention" not in state.audit:
            state.audit["first_attention"] = {"qkv_shape": list(q.shape), "dtype": str(q.dtype),
                "device": str(q.device), "heads": heads, "flash_lse": True, "returned_shape": list(out.shape)}
        return out


class ReferenceOriginBlockPatch(EventBlockPatch):
    override_class = ReferenceOriginAttentionOverride

    def __call__(self, args, extra_args):
        self.state.prepare_origin(args["layout"])
        original_table = args["rope_freqs"]
        original = extra_args["original_block"]
        def checked(local):
            if local["rope_freqs"] is not original_table or local["layout"] is not args["layout"]:
                raise ValueError("original joint RoPE table or layout replaced")
            self.state.audit["reference_origin"]["original_rope_table_calls"] += 1
            return original(local)
        return super().__call__(args, dict(extra_args, original_block=checked))
