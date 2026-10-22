"""Legacy ComfyUI custom node, confined to this experiment's cloned MODEL."""

from .core import EventBlockPatch, EventState, conditioning_metadata, event_latent_range


class H3EventEmphasis:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",), "positive": ("CONDITIONING",),
            "factor": ("INT", {"default": 2, "min": 1, "max": 2}),
            "start_frame": ("INT", {"default": 39, "min": 0}),
            "end_frame": ("INT", {"default": 44, "min": 0}),
            "run_id": ("STRING", {"default": "event_emphasis_factor2"}),
            "audit_dir": ("STRING", {"default": "/tmp/h3-event-emphasis-audit"}),
        }}

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "apply"
    CATEGORY = "research/H3EventEmphasis"

    def apply(self, model, positive, factor, start_frame, end_frame, run_id, audit_dir):
        import comfy.ldm.minimax.model as h3
        metadata = conditioning_metadata(positive)
        ref = next(r for r in metadata["refs"] if r["kind"] in ("video", "video_audio"))
        event_latent_range(start_frame, end_frame, ref["latent_t"])
        diffusion = model.get_model_object("diffusion_model")
        if not isinstance(diffusion, h3.MiniMaxH3Model):
            raise TypeError("H3EventEmphasis requires MiniMaxH3Model")
        if (tuple(diffusion.patch_size), diffusion.latents_dim, len(diffusion.blocks)) != ((1, 2, 2), 24, 50):
            raise ValueError("unexpected H3 patch geometry / channel count / block count")
        if tuple(h3.FRAME_PER_TOKEN) != (1, 4, 4, 4, 4) or h3.FRAME_RESCALE != 5.0 / 3.0:
            raise ValueError("installed Core changed the H3 temporal positional mapping")
        if getattr(h3.optimized_attention, "__name__", None) != "attention_pytorch":
            raise ValueError("launch with native PyTorch attention for this fixed-backend experiment")
        options = model.model_options.get("transformer_options", {})
        if options.get("optimized_attention_override") is not None:
            raise ValueError("existing attention override is unsupported")
        previous = options.get("patches_replace", {}).get("dit", {})
        if any(("double_block", i) in previous for i in range(len(diffusion.blocks))):
            raise ValueError("refusing to replace another DiT block patch")
        cloned = model.clone()
        state = EventState(metadata, factor, start_frame, end_frame, run_id, audit_dir,
                           num_blocks=len(diffusion.blocks))
        for i in range(len(diffusion.blocks)):
            cloned.set_model_patch_replace(EventBlockPatch(state, i), "dit", "double_block", i)
        return (cloned,)


NODE_CLASS_MAPPINGS = {"H3EventEmphasis": H3EventEmphasis}
NODE_DISPLAY_NAME_MAPPINGS = {"H3EventEmphasis": "H3 Event Emphasis (controlled KV duplication)"}
