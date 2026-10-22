"""Independent Comfy patch; install only in a separately admitted H3 runtime."""
from dataclasses import asdict

from .frozen import load_frozen
from .runtime import DirectionConfig, MODES, REASONS, direction_attention, serialize_report


FROZEN = load_frozen()


def parse_layers(value, num_blocks=50):
    if value.strip() == "all":
        return tuple(range(num_blocks))
    if value.strip() in ("", "none"):
        return ()
    layers = set()
    for field in value.split(","):
        field = field.strip()
        if "-" in field:
            bounds = field.split("-")
            if len(bounds) != 2 or not all(x.isdecimal() for x in bounds):
                raise ValueError("layers must be all, none, or comma-separated integer/range values")
            a, b = map(int, bounds)
            if a > b or b >= num_blocks:
                raise ValueError("layer range must be increasing and within the model")
            layers.update(range(a, b + 1))
        elif field.isdecimal():
            layers.add(int(field))
        else:
            raise ValueError("invalid layer selector")
    if any(not 0 <= block < num_blocks for block in layers):
        raise ValueError("selected block outside model")
    return tuple(sorted(layers))


class DirectionState(FROZEN.schedule.ScheduleState):
    def __init__(self, metadata, *, mode, config, selected_layers, enabled,
                 start_frame, end_frame, schedule, run_id, audit_dir, num_blocks=50):
        if mode not in MODES:
            raise ValueError("invalid direction mode")
        if any(type(x) is not int or not 0 <= x < num_blocks for x in selected_layers):
            raise ValueError("invalid explicit layer selection")
        self.direction_config = config
        self.direction_mode = mode
        self.selected_layers = frozenset(selected_layers)
        self.enabled = enabled
        self.direction_pending = []
        super().__init__(metadata, "mass_preserve", config.alpha, 0, 0, start_frame,
                         end_frame, 0, num_blocks, 0, 20, run_id, audit_dir,
                         num_blocks=num_blocks, schedule=schedule)
        self.audit.update(
            schema="h3-direction-runtime-v1", mode=mode, enabled=enabled,
            routing_implementation="independent direction_attention; frozen Flash/LSE and aligned grouping",
            frozen_dependency_root=FROZEN.root, frozen_dependency_hashes=FROZEN.hashes,
            direction_config=asdict(config), selected_layers=sorted(self.selected_layers),
            layer_selection="explicit immutable set; no dynamic layer selection",
            probe_spatial_policy="2x2 quarter grid per bin, all heads, deduplicated for tiny grids",
            probe_aggregation="mean individual squared positive-cosine gates; unknown samples count as zero",
            unknown_reason_labels=list(REASONS), direction_forward_summaries=[],
            compute_call_totals={}, probe_logits_matmul_total=0,
            cumulative_native_correction_energy=0.0, cumulative_applied_correction_energy=0.0,
            cumulative_correction_element_count=0,
            metric_scope="exact intervention-interval correction energy; per-head/bin gates; reference routing is not physical action time",
            frozen_periodic_temporal_readout=False,
            full_dit_forward_calls_added=0, intermediate_vae_decode_calls=0,
        )
        self.write()

    def selected(self, block):
        return self.enabled and block in self.selected_layers and super().selected(block)

    def finish_forward(self):
        records = []
        forward_counts = {}
        probe_calls = 0
        for block, pending in self.direction_pending:
            report = serialize_report(pending)
            report["block"] = block
            report["forward_index"] = self.forward_index
            for name, count in report["compute"]["attention_calls"].items():
                forward_counts[name] = forward_counts.get(name, 0) + count
                self.audit["compute_call_totals"][name] = self.audit["compute_call_totals"].get(name, 0) + count
            probe_calls += report["compute"]["probe_logits_matmul_calls"]
            if not report.get("finite_output", True):
                raise FloatingPointError("nonfinite direction output")
            self.audit["cumulative_native_correction_energy"] += report.get("native_correction_energy", 0.0)
            self.audit["cumulative_applied_correction_energy"] += report.get("applied_correction_energy", 0.0)
            self.audit["cumulative_correction_element_count"] += report.get("correction_element_count", 0)
            records.append(report)
        self.audit["probe_logits_matmul_total"] += probe_calls
        self.audit["direction_forward_summaries"].append({
            "forward_index": self.forward_index, "attention_calls": forward_counts,
            "probe_logits_matmul_calls": probe_calls, "layer_stats": records,
        })
        self.direction_pending.clear()
        super().finish_forward()


class DirectionAttentionOverride:
    def __init__(self, state, plan, block):
        self.state, self.plan, self.block, self.calls = state, plan, block, 0

    def __call__(self, native, q, k, v, heads, **kwargs):
        if getattr(native, "__name__", None) != "attention_pytorch":
            raise ValueError("direction patch requires attention_pytorch entry")
        if kwargs.get("mask") is not None or not kwargs.get("skip_reshape") or kwargs.get("skip_output_reshape", False):
            raise ValueError("direction patch requires unmasked preshaped attention")
        self.calls += 1
        if self.calls != 1:
            raise ValueError("expected exactly one attention call per block")
        state = self.state
        selected = state.selected(self.block)
        mode = state.direction_mode if selected else "native"
        reports = []
        out = direction_attention(q, k, v, heads, self.plan, mode=mode,
                                  config=state.direction_config, diagnostics=reports)
        state.audit["native_override_calls"] += 1
        if selected and mode != "native" and state.alpha != 0 and "skip_reason" not in reports[0]:
            state.audit["routed_calls"] += 1
            state.audit["routed_by_block"][self.block] += 1
            state.audit["routed_by_forward"][state.forward_index] += 1
        state.direction_pending.append((self.block, reports[0]))
        if "first_attention" not in state.audit:
            state.audit["first_attention"] = {"qkv_shape": list(q.shape), "dtype": str(q.dtype),
                                             "device": str(q.device), "heads": heads,
                                             "flash_lse": True, "returned_shape": list(out.shape)}
        return out


class DirectionBlockPatch(FROZEN.schedule.ScheduleBlockPatch):
    override_class = DirectionAttentionOverride


class H3DirectionGatedSchedule:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",), "positive": ("CONDITIONING",),
            "enabled": ("BOOLEAN", {"default": True}),
            "mode": (list(MODES), {"default": "direction_gated"}),
            "schedule": (list(FROZEN.schedule.SCHEDULES), {"default": "global_weak"}),
            "selected_layers": ("STRING", {"default": "all"}),
            "alpha": ("FLOAT", {"default": 0.45, "min": 0., "max": 1.}),
            "min_routing_offset": ("FLOAT", {"default": 0.25, "min": 0.}),
            "min_concentration": ("FLOAT", {"default": 0.15, "min": 0., "max": 1.}),
            "min_tangent_norm": ("FLOAT", {"default": 1e-6, "min": 0.}),
            "query_chunk": ("INT", {"default": 16, "min": 1, "max": 64}),
            "key_chunk": ("INT", {"default": 512, "min": 1, "max": 2048}),
            "record_cuda_timing": ("BOOLEAN", {"default": True}),
            "start_frame": ("INT", {"default": 0, "min": 0}),
            "end_frame": ("INT", {"default": 60, "min": 0}),
            "run_id": ("STRING",), "audit_dir": ("STRING",),
        }}

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "apply"
    CATEGORY = "research/H3DirectionRuntime"

    def apply(self, model, positive, enabled, mode, schedule, selected_layers, alpha,
              min_routing_offset, min_concentration, min_tangent_norm, query_chunk,
              key_chunk, record_cuda_timing, start_frame, end_frame, run_id, audit_dir):
        import comfy.ldm.minimax.model as h3

        diffusion = model.get_model_object("diffusion_model")
        if not isinstance(diffusion, h3.MiniMaxH3Model) or len(diffusion.blocks) != 50:
            raise ValueError("Expected H3 50 DiT blocks")
        if tuple(h3.FRAME_PER_TOKEN) != (1, 4, 4, 4, 4):
            raise ValueError("Changed H3 temporal mapping")
        if getattr(h3.optimized_attention, "__name__", None) != "attention_pytorch":
            raise ValueError("Require PyTorch attention entry")
        options = model.model_options.get("transformer_options", {})
        if options.get("patches_replace", {}).get("dit") or options.get("optimized_attention_override"):
            raise ValueError("Existing attention/block patch cannot be composed")
        config = DirectionConfig(alpha=alpha, min_routing_offset=min_routing_offset,
                                 min_concentration=min_concentration, min_tangent_norm=min_tangent_norm,
                                 query_chunk=query_chunk, key_chunk=key_chunk,
                                 record_cuda_timing=record_cuda_timing)
        state = DirectionState(FROZEN.layout.conditioning_metadata(positive), mode=mode,
                               config=config, selected_layers=parse_layers(selected_layers),
                               enabled=enabled, start_frame=start_frame, end_frame=end_frame,
                               schedule=schedule, run_id=run_id, audit_dir=audit_dir)
        clone = model.clone()
        for i in range(50):
            clone.set_model_patch_replace(DirectionBlockPatch(state, i), "dit", "double_block", i)
        return (clone,)
