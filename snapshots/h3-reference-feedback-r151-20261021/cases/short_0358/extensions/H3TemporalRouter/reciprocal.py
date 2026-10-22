"""R151: two disjoint query-row corrections using the original joint mass.

Forward is the unchanged R149 implementation. Reverse SAME is the existing
R25 algebra, now sharing that exact full Flash call and its natural-log LSE.
"""
import math
from . import core
from .schedule import ScheduleState, ScheduleBlockPatch


def reverse_ranges(plan):
    ra, rb = plan["reference_video_segment"]
    ta, tb = plan["target_video_segment"]
    lo, hi = plan["latent_interval_half_open"]
    rows = plan["frame_rows"]
    if (type(rows) is not int or rows < 1 or
            not 0 <= ra < rb <= ta < tb == plan["seq_len"] or
            rb-ra != tb-ta or (rb-ra) % rows or
            not 0 <= lo < hi <= (rb-ra)//rows):
        raise ValueError("invalid disjoint equal-geometry video ranges")
    qa, qb = ra+lo*rows, ra+hi*rows
    if (plan["key_interval_half_open"] != [qa, qb] or
            plan["query_interval_half_open"] != [ta+lo*rows, ta+hi*rows]):
        raise ValueError("physical-bin query/key ranges differ")
    return qa, qb, ta, tb


def route_reciprocal(q, k, v, heads, plan, *, alpha, beta,
                     attention=core.flash_attention_lse, diagnostics=None):
    """One full call; group outputs use unmodified QKV in both directions."""
    import torch
    if any(not math.isfinite(x) or not 0 <= x <= 1 for x in (alpha, beta)):
        raise ValueError("alpha/beta must lie in [0,1]")
    rqa, rqb, ta, tb = reverse_ranges(plan)
    captured = []
    forward_stats = []

    def backend(query, keys, values):
        result = attention(query, keys, values)
        if not captured:
            if query is not q or keys is not k or values is not v:
                raise ValueError("first attention must be the original joint call")
            captured.append(result)
        return result

    # This includes the exact existing alpha=0/native branch and arithmetic.
    out = core.route_attention(q, k, v, heads, plan, mode="mass_preserve",
                               alpha=alpha, radius=0, time_offset=0,
                               attention=backend, diagnostics=forward_stats)
    if diagnostics is not None and forward_stats:
        diagnostics["forward"] = forward_stats[0]
    if beta == 0:
        return out
    full, full_lse = captured[0]
    query, keys, values = q[:, :, rqa:rqb], k[:, :, ta:tb], v[:, :, ta:tb]
    group, group_lse = attention(query, keys, values)
    log_mass = group_lse.float() - full_lse[:, :, rqa:rqb].float()
    mass = log_mass.exp()  # Raw LSE difference is recorded; no reverse clamp.
    aligned, _ = core._aligned_attention(
        query, keys, values, latent_lo=plan["latent_interval_half_open"][0],
        frame_rows=plan["frame_rows"], radius=0, time_offset=0, attention=attention)
    old = full[:, :, rqa:rqb]  # Forward wrote only target Q rows, disjoint here.
    changed = (old.float() + beta*mass.unsqueeze(-1)*(aligned.float()-group.float())).to(old.dtype)
    if diagnostics is not None:
        diagnostics["reverse"] = core._bounded_stats(old, changed, mass, log_mass)
        diagnostics["reverse_log_mass_min"] = log_mass.amin()
        diagnostics["reverse_log_mass_max"] = log_mass.amax()
        diagnostics["reverse_all_finite"] = (
            torch.isfinite(changed).all() & torch.isfinite(log_mass).all() &
            torch.isfinite(mass).all()).float()
    full[:, :, rqa:rqb].copy_(changed)
    return full.transpose(1, 2).reshape(1, q.shape[-2], heads*q.shape[-1])


class ReciprocalState(ScheduleState):
    def __init__(self, *args, beta, arm, **kwargs):
        if beta != 1.0 or arm not in ("reverse_only", "combined"):
            raise ValueError("R151 registered reverse strength/arm differs")
        self.beta, self.arm = beta, arm
        self.direction_stats = []
        super().__init__(*args, schedule="early", **kwargs)
        if self.alpha != (0.0 if arm == "reverse_only" else 1.0):
            raise ValueError("R151 forward strength differs")
        self.audit.update(
            schema="r151-bidirectional-router-v1", arm=arm, beta=beta,
            routing_implementation="R149 forward + R25 reverse SAME; one original joint O/LSE",
            direction_convention="query role reads key/value role",
            reverse_group="entire generated-video segment; portrait/audio/text excluded",
            reverse_query_window="same physical bins in reference-video segment",
            reverse_mass_clamp=False, reverse_log_mass_excess_tolerance=0.001,
            forward_routed_calls=0, reverse_routed_calls=0,
            group_mass_scope="same unmodified-QKV attention call, independently per query/head")
        self.write()

    def plan_for(self, layout):
        plan = super().plan_for(layout)
        qa, qb, ta, tb = reverse_ranges(plan)
        self.audit["reverse_ranges"] = {"query_interval_half_open": [qa, qb],
                                        "all_key_interval_half_open": [ta, tb],
                                        "same_bin_interval_half_open": plan["latent_interval_half_open"]}
        return plan

    def finish_forward(self):
        import torch
        directional = {}
        for direction in ("forward", "reverse"):
            rows = [(b, s[direction]) for b, s in self.direction_stats if direction in s]
            if rows:
                values = torch.stack([s for _, s in rows]).float().cpu().tolist()
                directional[direction] = {
                    "blocks": [b for b, _ in rows],
                    "layer_stats": [{"block": b, "mass_mean": r[0], "mass_max": r[1],
                                     "correction_ratio": r[2], "finite": r[3] == 1.,
                                     "raw_log_mass_max_sampled": r[4]}
                                    for (b, _), r in zip(rows, values)]}
                if not all(r[3] == 1. for r in values):
                    raise FloatingPointError("nonfinite directional correction")
        reverse = [s for _, s in self.direction_stats if "reverse" in s]
        if reverse:
            raw = torch.stack([torch.stack([s["reverse_log_mass_min"],
                    s["reverse_log_mass_max"], s["reverse_all_finite"]]) for s in reverse]).float().cpu().tolist()
            directional["reverse"].update(raw_log_mass_min=min(x[0] for x in raw),
                                           raw_log_mass_max=max(x[1] for x in raw),
                                           all_finite=all(x[2] == 1. for x in raw))
            # Only FP32 subset/full LSE roundoff is admitted, without changing it.
            if not directional["reverse"]["all_finite"] or max(x[1] for x in raw) > .001:
                self.audit["reverse_failure_stats"] = directional["reverse"]
                raise FloatingPointError("reverse LSE/mass audit failed")
        self.direction_stats.clear()
        super().finish_forward()
        self.audit["forward_summaries"][-1]["directions"] = directional
        self.write()


class ReciprocalOverride(core.TemporalAttentionOverride):
    def __call__(self, native, q, k, v, heads, **kwargs):
        if getattr(native, "__name__", None) != "attention_pytorch":
            raise ValueError("native attention_pytorch entry required")
        if kwargs.get("mask") is not None or not kwargs.get("skip_reshape") or kwargs.get("skip_output_reshape", False):
            raise ValueError("unmasked preshaped attention required")
        if q.shape[-2] != self.plan["seq_len"]:
            raise ValueError("packed attention length differs")
        self.calls += 1
        if self.calls != 1:
            raise ValueError("one attention per DiT block required")
        state = self.state
        if self.block == 25 and state.forward_index in (0, 5, 10, 15, 19):
            readout = core.temporal_readout(q, k, self.plan)
            readout.update(block_index=self.block, forward_index=state.forward_index)
            state.audit["temporal_readouts"].append(readout)
        active = state.selected(self.block)
        stats = {}
        out = route_reciprocal(q, k, v, heads, self.plan,
                              alpha=state.alpha if active else 0.,
                              beta=state.beta if active else 0., diagnostics=stats)
        state.audit["native_override_calls"] += 1
        if active:
            state.audit["routed_calls"] += 1
            state.audit["routed_by_block"][self.block] += 1
            state.audit["routed_by_forward"][state.forward_index] += 1
            state.audit["forward_routed_calls"] += int(state.alpha != 0)
            state.audit["reverse_routed_calls"] += int(state.beta != 0)
            state.direction_stats.append((self.block, stats))
        if "first_attention" not in state.audit:
            state.audit["first_attention"] = {
                "qkv_shape": list(q.shape), "dtype": str(q.dtype),
                "device": str(q.device), "heads": heads, "flash_lse": True,
                "returned_shape": list(out.shape)}
        return out


class ReciprocalBlockPatch(ScheduleBlockPatch):
    override_class = ReciprocalOverride
