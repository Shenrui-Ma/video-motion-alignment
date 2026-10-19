"""Task-local frozen-H3 temporal routing diagnostic node."""

from .core import EventBlockPatch, MODES, RouterState
from .layout import conditioning_metadata, event_latent_range
from .mask import load_mask


class H3LocalTemporalRouter:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",), "positive": ("CONDITIONING",),
            "mask_variant": (["roi", "uniform"], {"default": "roi"}),
            "mask_path": ("STRING", {"default": ""}),
            "mask_sha256": ("STRING", {"default": ""}),
            "mode": (list(MODES), {"default": "native"}),
            "alpha": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0}),
            "radius": ("INT", {"default": 0, "min": 0, "max": 1}),
            "time_offset": ("INT", {"default": 0, "min": -1000, "max": 1000}),
            "start_frame": ("INT", {"default": 54, "min": 0}),
            "end_frame": ("INT", {"default": 69, "min": 0}),
            "block_start": ("INT", {"default": 0, "min": 0, "max": 49}),
            "block_end": ("INT", {"default": 50, "min": 1, "max": 50}),
            "step_start": ("INT", {"default": 0, "min": 0}),
            "step_end": ("INT", {"default": 20, "min": 1}),
            "run_id": ("STRING", {"default": "temporal_router"}),
            "audit_dir": ("STRING", {"default": "/tmp/h3-temporal-router"}),
        }}

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "apply"
    CATEGORY = "research/H3LocalTemporalRouter"

    def apply(self, model, positive, mode, alpha, radius, time_offset, start_frame,
              end_frame, block_start, block_end, step_start, step_end, run_id, audit_dir,
              mask_variant, mask_path, mask_sha256):
        import comfy.ldm.minimax.model as h3

        if (mode, alpha, radius, time_offset, start_frame, end_frame,
                block_start, block_end, step_start, step_end) != (
                "mass_preserve", 1.0, 0, 0, 50, 65, 0, 50, 6, 15):
            raise ValueError("local-route pilot requires frozen R3 Full6..14 parameters")
        query_gain, mask_metadata = load_mask(mask_path, mask_sha256, mask_variant)
        metadata = conditioning_metadata(positive)
        ref = next(r for r in metadata["refs"] if r["kind"] in ("video", "video_audio"))
        if (ref["latent_t"], ref["latent_h"], ref["latent_w"]) != (42, 46, 82):
            raise ValueError("local-route source geometry must be141x736x1312")
        import hashlib
        import torch
        raw_ref = positive[0][1]["minimax_refs"][ref["index"]]["latent"]
        raw_cpu = raw_ref.detach().to(device="cpu", copy=True).contiguous()
        if raw_cpu.dtype != torch.float32 or not bool(torch.isfinite(raw_cpu).all()):
            raise ValueError("reference must preserve the frozen finitefloat32 representation")
        actual_ref_sha = hashlib.sha256(raw_cpu.view(torch.uint8).numpy()).hexdigest()
        if actual_ref_sha != "75140c3ce5f144cdce940b6cd84a56dc40c9a94f15fdc917e6ad712ba9e94734":
            raise ValueError("actual clean reference differs from frozen R3 .9 source")
        event_latent_range(start_frame, end_frame, ref["latent_t"])
        diffusion = model.get_model_object("diffusion_model")
        if not isinstance(diffusion, h3.MiniMaxH3Model):
            raise TypeError("H3LocalTemporalRouter requires MiniMaxH3Model")
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
        state.query_gain = query_gain
        state.audit["local_query_gain"] = {
            "variant": mask_variant, "mask_file_sha256": mask_sha256,
            "source": mask_metadata, "all_heads_share_gain": True,
            "zero_rows_written": False,
            "formula": "O+a_q*m_ref*(O_same-O_ref)",
            "no_new_model_prediction": True,
            "expected_model_calls": 20, "expected_euler_updates": 20,
            "actual_clean_reference_sha256": actual_ref_sha,
            "sum_alpha_not_m_ref_weighted_dose": True}
        state.write()
        cloned = model.clone()
        for index in range(50):
            cloned.set_model_patch_replace(EventBlockPatch(state, index), "dit", "double_block", index)
        return (cloned,)


NODE_CLASS_MAPPINGS = {"H3LocalTemporalRouter": H3LocalTemporalRouter}
NODE_DISPLAY_NAME_MAPPINGS = {"H3LocalTemporalRouter": "H3 Local Temporal Router (diagnostic)"}
