"""Optional H3 attention adapter; no global registration or monkey patching."""

import math

import torch

from .routing import CoverageConfig, sampled_time_quality, solve_temporal_coverage


def _packed(output):
    batch, heads, length, dim = output.shape
    return output.transpose(1, 2).reshape(batch, length, heads * dim)


@torch.no_grad()
def coverage_attention(query, key, value, heads, plan, *, attention,
                       enabled=False, alpha=1.0, config=CoverageConfig(),
                       query_samples=8, head_samples=4, key_chunk=256,
                       diagnostics=None):
    """O + alpha*m_ref*(sum_j P[t,j]*O_frame_j - O_ref), Flash-compatible.

    ``attention`` must return both output and exact LSE without materializing
    dense token attention in production (pass frozen core.flash_attention_lse).
    Small CPU tests inject a dense oracle. Invalid plans raise; numerical/weak
    coverage estimates explicitly fall back to the already computed native O.
    """
    if not math.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ValueError("alpha must be in [0,1]")
    if (query.ndim != 4 or query.shape != key.shape or key.shape != value.shape
            or query.shape[0] != 1 or query.shape[1] != heads
            or any(x.device != query.device or x.dtype != query.dtype for x in (key, value))):
        raise ValueError("expected matching single-batch [1,H,N,D] Q/K/V")
    native, full_lse = attention(query, key, value)
    if not enabled or alpha == 0:
        if diagnostics is not None:
            diagnostics.update(applied=False, reason="disabled", attention_calls=1)
        return _packed(native)
    qa, qb = plan["query_interval_half_open"]
    ra, rb = plan["reference_video_segment"]
    ta, tb = plan["target_video_segment"]
    lo, hi = plan["latent_interval_half_open"]
    spatial = plan["frame_rows"]
    length = query.shape[-2]
    if (type(spatial) is not int or spatial < 1 or not 0 <= ra < rb <= length
            or not 0 <= ta < tb <= length or not 0 <= qa < qb <= length
            or max(ra, ta) < min(rb, tb) or not 0 <= lo < hi
            or (rb - ra) % spatial or rb - ra != tb - ta
            or qa != ta + lo * spatial or qb != ta + hi * spatial
            or hi * spatial > rb - ra or plan.get("seq_len", length) != length):
        raise ValueError("plan must describe matching disjoint full-frame H3 video segments")
    count = hi - lo
    if count > config.max_bins:
        raise ValueError("event window exceeds max_bins")
    q_event = query[:, :, qa:qb]
    all_ref_keys, all_ref_values = key[:, :, ra:rb], value[:, :, ra:rb]
    window_keys = key[:, :, ra + lo * spatial:ra + hi * spatial]
    window_values = value[:, :, ra + lo * spatial:ra + hi * spatial]
    quality = sampled_time_quality(q_event, window_keys, spatial,
                                   query_samples=query_samples, head_samples=head_samples,
                                   key_chunk=key_chunk)
    route = solve_temporal_coverage(quality, config=config)
    if diagnostics is not None:
        diagnostics.update(route.summary(), attention_calls=1,
                           conditional_coverage=route.probabilities.sum(0).detach(),
                           window_half_open=[lo, hi])
    route_radius=config.radius
    if not route.applied:
        route_radius=0
        # Explicit v2 fallback: keep the verified same-time weak intervention.
        # It is logged separately from successful cross-time transport.
        route.probabilities = torch.eye(count, device=query.device, dtype=torch.float32)
        if diagnostics is not None:
            diagnostics.update(applied=True, reason="same_time_fallback", fallback_reason=route.reason,
                               routing_solved=False, fallback_policy=config.fallback_policy,
                               conditional_coverage=route.probabilities.sum(0).detach())
    elif diagnostics is not None:
        diagnostics.update(routing_solved=True, fallback_policy=config.fallback_policy)
    reference, reference_lse = attention(q_event, all_ref_keys, all_ref_values)
    log_mass = reference_lse.float() - full_lse[:, :, qa:qb].float()
    mass = log_mass.clamp(max=0).exp()
    grouped_q = q_event[0].reshape(heads, count, spatial, -1).permute(1, 0, 2, 3)
    grouped_k = window_keys[0].reshape(heads, count, spatial, -1).permute(1, 0, 2, 3)
    grouped_v = window_values[0].reshape(heads, count, spatial, -1).permute(1, 0, 2, 3)
    work_dtype = torch.float64 if query.dtype == torch.float64 else torch.float32
    routed = torch.zeros_like(grouped_q, dtype=work_dtype)
    attention_calls = 2
    # Batch equal-sized frame pairs by temporal offset; no duplicated/padded
    # keys. At most 2*radius+1 kernel calls, each with <=T independent pairs.
    for offset in range(-min(route_radius, count - 1), min(route_radius, count - 1) + 1):
        start, stop = max(0, -offset), min(count, count - offset)
        rows = torch.arange(start, stop, device=query.device)
        columns = rows + offset
        part, _ = attention(grouped_q[rows].contiguous(), grouped_k[columns].contiguous(),
                            grouped_v[columns].contiguous())
        weight = route.probabilities[rows, columns].to(work_dtype)
        routed[rows] += weight[:, None, None, None] * part.to(work_dtype)
        attention_calls += 1
    routed = routed.permute(1, 0, 2, 3).reshape_as(q_event)
    old = native[:, :, qa:qb]
    correction = mass.to(work_dtype).unsqueeze(-1) * (routed - reference.to(work_dtype))
    changed = (old.to(work_dtype) + alpha * correction).to(old.dtype)
    if not bool(torch.isfinite(changed).all()):
        if diagnostics is not None:
            diagnostics.update(applied=False, reason="nonfinite_correction", attention_calls=attention_calls)
        return _packed(native)
    if diagnostics is not None:
        diagnostics.update(attention_calls=attention_calls, reference_mass=mass.detach(),
                           log_mass=log_mass.detach(), before=old.detach().clone(),
                           after=changed.detach())
    native[:, :, qa:qb].copy_(changed)
    return _packed(native)


def make_h3_patch_classes(core):
    """Bind to an explicitly supplied, unchanged H3Study.core module.

    Reuses its strict layout/RoPE/block-order audit and Flash backend. The
    returned classes are inert until explicitly attached to a fresh model.
    """
    class CoverageState(core.RouterState):
        def __init__(self, *args, coverage_config=CoverageConfig(), **kwargs):
            self.coverage_config = coverage_config
            super().__init__(*args, **kwargs)
            self.audit.update(schema="h3-temporal-coverage-v2",
                              routing_implementation="standalone temporal_coverage.coverage_attention",
                              coverage_config=vars(coverage_config), coverage_calls=[],
                              coverage_solved_calls=0, same_time_fallback_calls=0, solver_wall_seconds=0.0,
                              coverage_scope="unit conditional probability per latent bin in selected window",
                              order_constraint="nondecreasing expected reference-bin time",
                              production_validation="not run")
            self.write()

    class CoverageAttentionOverride:
        def __init__(self, state, plan, block):
            self.state, self.plan, self.block, self.calls = state, plan, block, 0

        def __call__(self, native, q, k, v, heads, **kwargs):
            if (getattr(native, "__name__", None) != "attention_pytorch"
                    or kwargs.get("mask") is not None or not kwargs.get("skip_reshape")
                    or kwargs.get("skip_output_reshape", False)):
                raise ValueError("coverage requires unmasked preshaped attention_pytorch")
            if q.shape[-2] != self.plan["seq_len"]:
                raise ValueError("packed sequence differs from validated H3 layout")
            self.calls += 1
            if self.calls != 1:
                raise ValueError("expected one attention call per DiT block")
            state, record = self.state, {}
            active = state.selected(self.block)
            result = coverage_attention(q, k, v, heads, self.plan,
                                        attention=core.flash_attention_lse,
                                        enabled=active, alpha=state.alpha,
                                        config=state.coverage_config, diagnostics=record)
            state.audit["native_override_calls"] += 1
            if active:
                state.audit["solver_wall_seconds"] += record.get("solver_seconds",0.)
                if record.get("routing_solved"):state.audit["coverage_solved_calls"] += 1
                if record.get("reason")=="same_time_fallback":state.audit["same_time_fallback_calls"] += 1
            if record["applied"]:
                state.audit["routed_calls"] += 1
                state.audit["routed_by_block"][self.block] += 1
                state.audit["routed_by_forward"][state.forward_index] += 1
                stats = core._bounded_stats(record.pop("before"), record.pop("after"),
                                            record.pop("reference_mass"), record.pop("log_mass"))
                state.pending_stats.append((self.block, stats))
            if active:
                # Store only small serializable coverage diagnostics, not Q/K/V.
                record = {key: item for key, item in record.items() if not torch.is_tensor(item)}
                record.update(block=self.block, forward=state.forward_index)
                state.audit["coverage_calls"].append(record)
            return result

    class CoverageBlockPatch(core.EventBlockPatch):
        override_class = CoverageAttentionOverride

    return CoverageState, CoverageBlockPatch


def attach_h3_coverage(model, positive, *, core, enabled=False,
                       config=CoverageConfig(), alpha=1.0, start_frame, end_frame,
                       block_start=0, block_end=50, step_start=6, step_end=15,
                       run_id, audit_dir):
    """Explicit opt-in factory, to call only in a separate future experiment.

    Disabled returns the exact original model and creates no state/files.
    Enabled clones a fresh unpatched H3 model and uses existing block hooks;
    caller supplies the frozen core module. No live service/graph is modified.
    """
    if not enabled:
        return model
    import comfy.ldm.minimax.model as h3

    diffusion = model.get_model_object("diffusion_model")
    if not isinstance(diffusion, h3.MiniMaxH3Model) or len(diffusion.blocks) != 50:
        raise ValueError("expected H3 with 50 DiT blocks")
    if tuple(h3.FRAME_PER_TOKEN) != (1, 4, 4, 4, 4):
        raise ValueError("changed H3 positional-bin mapping")
    if getattr(h3.optimized_attention, "__name__", None) != "attention_pytorch":
        raise ValueError("requires native attention_pytorch and no Sage forward override")
    options = model.model_options.get("transformer_options", {})
    if options.get("patches_replace", {}).get("dit") or options.get("optimized_attention_override"):
        raise ValueError("cannot combine existing H3 block/attention patches")
    state_class, patch_class = make_h3_patch_classes(core)
    state = state_class(core.conditioning_metadata(positive), "mass_preserve", alpha,
                        0, 0, start_frame, end_frame, block_start, block_end,
                        step_start, step_end, run_id, audit_dir, coverage_config=config)
    clone = model.clone()
    for index in range(50):
        clone.set_model_patch_replace(patch_class(state, index), "dit", "double_block", index)
    return clone
