"""Staged reference-only temporal phase actuator. Never auto-installed."""

from .core import PhaseBlockPatch, PhaseState
from .layout import conditioning_metadata, event_latent_range


class H3PhaseRoPE:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",), "positive": ("CONDITIONING",),
            "delta_frames": ("FLOAT", {"default": 0.0, "min": -240.0, "max": 240.0, "step": 1.0}),
            "alpha": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0}),
            "start_frame": ("INT", {"default": 50, "min": 0}),
            "end_frame": ("INT", {"default": 65, "min": 0}),
            "block_start": ("INT", {"default": 0, "min": 0, "max": 49}),
            "block_end": ("INT", {"default": 50, "min": 1, "max": 50}),
            "step_start": ("INT", {"default": 0, "min": 0, "max": 19}),
            "step_end": ("INT", {"default": 20, "min": 1, "max": 20}),
            "run_id": ("STRING", {"default": "phase_rope_unique_run"}),
            "audit_dir": ("STRING", {"default": "/tmp/h3-phase-rope"}),
        }}

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "apply"
    CATEGORY = "research/H3PhaseRoPE"

    def apply(self, model, positive, delta_frames, alpha, start_frame, end_frame,
              block_start, block_end, step_start, step_end, run_id, audit_dir):
        import comfy.ldm.minimax.model as h3

        metadata = conditioning_metadata(positive)
        reference = next(r for r in metadata["refs"] if r["kind"] in ("video", "video_audio"))
        event_latent_range(start_frame, end_frame, reference["latent_t"])
        diffusion = model.get_model_object("diffusion_model")
        if not isinstance(diffusion, h3.MiniMaxH3Model):
            raise TypeError("H3PhaseRoPE requires MiniMaxH3Model")
        if (tuple(diffusion.patch_size), diffusion.latents_dim, len(diffusion.blocks)) != ((1, 2, 2), 24, 50):
            raise ValueError("unexpected H3 architecture")
        if tuple(h3.FRAME_PER_TOKEN) != (1, 4, 4, 4, 4) or h3.FRAME_RESCALE != 5 / 3:
            raise ValueError("H3 temporal positional mapping changed")
        if getattr(h3.optimized_attention, "__name__", None) != "attention_pytorch":
            raise ValueError("launch with --use-pytorch-cross-attention")
        options = model.model_options.get("transformer_options", {})
        if options.get("optimized_attention_override") is not None:
            raise ValueError("existing attention override unsupported")
        replacements = options.get("patches_replace", {}).get("dit", {})
        if any(("double_block", i) in replacements for i in range(50)):
            raise ValueError("use PhaseRoPE instead of, not on top of, another DiT block patch")
        state = PhaseState(metadata, diffusion.rope.inv_freq, delta_frames, alpha, start_frame,
                           end_frame, block_start, block_end, step_start, step_end, run_id, audit_dir)
        cloned = model.clone()
        for index in range(50):
            cloned.set_model_patch_replace(PhaseBlockPatch(state, index), "dit", "double_block", index)
        return (cloned,)


NODE_CLASS_MAPPINGS = {"H3PhaseRoPE": H3PhaseRoPE}
NODE_DISPLAY_NAME_MAPPINGS = {"H3PhaseRoPE": "H3 reference-only temporal RoPE (diagnostic)"}
