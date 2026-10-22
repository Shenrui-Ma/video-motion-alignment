"""Task-local frozen-H3 temporal routing diagnostic node."""

from .core import EventBlockPatch, MODES, RouterState
from .layout import conditioning_metadata, event_latent_range


from r63_contract import validate_router as validate_run_contract


class H3TemporalRouter:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",), "positive": ("CONDITIONING",),
            "mode": (list(MODES), {"default": "native"}),
            "alpha": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0}),
            "radius": ("INT", {"default": 0, "min": 0, "max": 1}),
            "time_offset": ("INT", {"default": 0, "min": -1000, "max": 1000}),
            "start_frame": ("INT", {"default": 0, "min": 0}),
            "end_frame": ("INT", {"default": 0, "min": 0}),
            "block_start": ("INT", {"default": 0, "min": 0, "max": 49}),
            "block_end": ("INT", {"default": 50, "min": 1, "max": 50}),
            "step_start": ("INT", {"default": 0, "min": 0}),
            "step_end": ("INT", {"default": 20, "min": 1}),
            "run_id": ("STRING", {"default": "temporal_router"}),
            "audit_dir": ("STRING", {"default": "/tmp/h3-temporal-router"}),
        }}

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "apply"
    CATEGORY = "research/H3TemporalRouter"

    def apply(self, model, positive, mode, alpha, radius, time_offset, start_frame,
              end_frame, block_start, block_end, step_start, step_end, run_id, audit_dir):
        import comfy.ldm.minimax.model as h3

        validate_run_contract(mode, alpha, radius, time_offset, start_frame, end_frame,
                              block_start, block_end, step_start, step_end, run_id, audit_dir)
        metadata = conditioning_metadata(positive)
        ref = next(r for r in metadata["refs"] if r["kind"] in ("video", "video_audio"))
        event_latent_range(start_frame, end_frame, ref["latent_t"])
        diffusion = model.get_model_object("diffusion_model")
        if not isinstance(diffusion, h3.MiniMaxH3Model):
            raise TypeError("H3TemporalRouter requires MiniMaxH3Model")
        if (tuple(diffusion.patch_size), diffusion.latents_dim, len(diffusion.blocks)) != ((1, 2, 2), 24, 50):
            raise ValueError("unexpected H3 architecture")
        if tuple(h3.FRAME_PER_TOKEN) != (1, 4, 4, 4, 4) or h3.FRAME_RESCALE != 5.0 / 3.0:
            raise ValueError("H3 temporal positional mapping changed")
        if getattr(h3.optimized_attention, "__name__", None) != "attention_pytorch":
            raise ValueError("launch with --use-pytorch-cross-attention")
        options = model.model_options.get("transformer_options", {})
        if options.get("optimized_attention_override") is not None:
            raise ValueError("existing attention override unsupported")
        old = options.get("patches_replace", {}).get("dit", {})
        if any(("double_block", i) in old for i in range(50)):
            raise ValueError("refusing to replace another DiT block patch")
        state = RouterState(metadata, mode, alpha, radius, time_offset, start_frame,
                            end_frame, block_start, block_end, step_start, step_end,
                            run_id, audit_dir)
        cloned = model.clone()
        for index in range(50):
            cloned.set_model_patch_replace(EventBlockPatch(state, index), "dit", "double_block", index)
        return (cloned,)


NODE_CLASS_MAPPINGS = {"H3TemporalRouter": H3TemporalRouter}
NODE_DISPLAY_NAME_MAPPINGS = {"H3TemporalRouter": "H3 Temporal Router (diagnostic)"}
