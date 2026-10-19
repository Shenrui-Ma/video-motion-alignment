"""Unified model node: one shared state for routing and next-call feedback."""
from .core import (FeedbackBlockPatch, FeedbackConfig, FeedbackRecorder,
                   FeedbackState, POLICIES, WRAPPER_KEY, extract_reference)


class H3FeedbackRouter:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",), "positive": ("CONDITIONING",),
            "policy": (list(POLICIES), {"default": "feedback"}),
            "fixed_indices": ("STRING", {"default": ""}),
            "start_frame": ("INT", {"default": 50}),
            "end_frame": ("INT", {"default": 65}),
            "width": ("INT", {"default": 1312}),
            "height": ("INT", {"default": 736}),
            "length": ("INT", {"default": 141}),
            "run_id": ("STRING", {"default": "feedback_unique_run"}),
            "audit_dir": ("STRING", {"default": "/tmp/h3-feedback"}),
        }}

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "apply"
    CATEGORY = "research/H3FeedbackRouter"

    def apply(self, model, positive, policy, fixed_indices, start_frame, end_frame,
              width, height, length, run_id, audit_dir):
        import comfy.ldm.minimax.model as h3
        from comfy.patcher_extension import WrappersMP

        config = FeedbackConfig(policy, fixed_indices, start_frame, end_frame,
                                width, height, length, run_id, audit_dir)
        diffusion = model.get_model_object("diffusion_model")
        if not isinstance(diffusion, h3.MiniMaxH3Model):
            raise TypeError("H3FeedbackRouter requires MiniMaxH3Model")
        if (tuple(diffusion.patch_size), diffusion.latents_dim, len(diffusion.blocks)) != ((1, 2, 2), 24, 50):
            raise ValueError("unexpected H3 architecture")
        if tuple(h3.FRAME_PER_TOKEN) != (1, 4, 4, 4, 4) or h3.FRAME_RESCALE != 5.0 / 3.0:
            raise ValueError("H3 positional geometry changed")
        if getattr(h3.optimized_attention, "__name__", None) != "attention_pytorch":
            raise ValueError("launch with --use-pytorch-cross-attention")
        if model.get_wrappers(WrappersMP.SAMPLER_SAMPLE, WRAPPER_KEY):
            raise ValueError("feedback wrapper already registered")
        options = model.model_options.get("transformer_options", {})
        if options.get("optimized_attention_override") is not None:
            raise ValueError("existing attention override unsupported")
        old = options.get("patches_replace", {}).get("dit", {})
        if old:
            raise ValueError("refusing to combine existing DiT replacements")
        metadata, reference = extract_reference(positive, config)
        state = FeedbackState(metadata, reference, config)
        cloned = model.clone()
        for index in range(50):
            cloned.set_model_patch_replace(FeedbackBlockPatch(state, index), "dit", "double_block", index)
        cloned.add_wrapper_with_key(WrappersMP.SAMPLER_SAMPLE, WRAPPER_KEY, FeedbackRecorder(state))
        return (cloned,)


NODE_CLASS_MAPPINGS = {"H3FeedbackRouter": H3FeedbackRouter}
NODE_DISPLAY_NAME_MAPPINGS = {"H3FeedbackRouter": "H3 causal feedback router (Euler20 pilot)"}
