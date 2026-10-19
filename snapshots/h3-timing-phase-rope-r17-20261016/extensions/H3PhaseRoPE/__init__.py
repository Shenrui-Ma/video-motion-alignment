"""Staged reference-only temporal phase actuator. Never auto-installed."""

from .core import PhaseBlockPatch, PhaseState
from .layout import conditioning_metadata, event_latent_range
from .architecture import architecture_contract


class H3PhaseRoPE:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",), "positive": ("CONDITIONING",),
            "delta_frames": ("FLOAT", {"default": 0.0, "min": -240.0, "max": 240.0, "step": 1.0}),
            "alpha": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0}),
            "start_frame": ("INT", {"default": 50, "min": 0}),
            "end_frame": ("INT", {"default": 65, "min": 0}),
            "block_start": ("INT", {"default": 0, "min": 0, "max": 49}),
            "block_end": ("INT", {"default": 50, "min": 1, "max": 50}),
            "step_start": ("INT", {"default": 6, "min": 0, "max": 19}),
            "step_end": ("INT", {"default": 15, "min": 1, "max": 20}),
            "run_id": ("STRING", {"default": "phase_rope_unique_run"}),
            "audit_dir": ("STRING", {"default": "/data5/researcher/h3_runs/timing_phase_rope_r17_20261016/audit/phase_rope"}),
        }}

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "apply"
    CATEGORY = "research/H3PhaseRoPE"

    def apply(self, model, positive, delta_frames, alpha, start_frame, end_frame,
              block_start, block_end, step_start, step_end, run_id, audit_dir):
        import comfy.ldm.minimax.model as h3
        import hashlib
        import inspect
        import json
        from pathlib import Path
        import weakref
        import torch

        if (delta_frames not in (-4.0, 0.0, 4.0) or alpha != 0.5
                or (start_frame, end_frame, block_start, block_end, step_start, step_end)
                != (50, 65, 0, 50, 6, 15)):
            raise ValueError("R17 requires delta -4/0/+4, alpha.5, window50..65, blocks[0,50), steps[6,15)")
        root = Path(audit_dir).resolve()
        allowed = Path("/data5/researcher/h3_runs/timing_phase_rope_r17_20261016").resolve()
        if not root.is_relative_to(allowed):
            raise ValueError("R17 audit path must remain in its own run root")

        metadata = conditioning_metadata(positive)
        reference = next(r for r in metadata["refs"] if r["kind"] in ("video", "video_audio"))
        if (reference["latent_t"], reference["latent_h"], reference["latent_w"]) != (42, 46, 82):
            raise ValueError("R17 requires frozen R3 source geometry")
        clean = positive[0][1]["minimax_refs"][reference["index"]]["latent"].detach().to("cpu").contiguous()
        if clean.dtype != torch.float32 or not bool(torch.isfinite(clean).all()):
            raise ValueError("R17 requires finite original FP32 clean reference")
        clean_sha = hashlib.sha256(clean.view(torch.uint8).numpy().tobytes()).hexdigest()
        if clean_sha != "75140c3ce5f144cdce940b6cd84a56dc40c9a94f15fdc917e6ad712ba9e94734":
            raise ValueError("actual clean reference differs from frozen R3 .9 input")
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
        contract = architecture_contract(diffusion)
        baseline_path = Path(__file__).resolve().parents[2] / "configs/parent_native_attention.json"
        baseline_bytes = baseline_path.read_bytes()
        baseline = json.loads(baseline_bytes)["first_attention"]
        if (contract["heads"], contract["head_dim"], contract["attention_inner"]) != (
                baseline["heads"], baseline["qkv_shape"][-1], baseline["returned_shape"][-1]):
            raise ValueError("actual model differs from R3 recorded attention dimensions")
        if any(type(block.attn) is not h3.Attention for block in diffusion.blocks):
            raise ValueError("R17 requires actual unmodified H3 Attention modules")
        source = Path(inspect.getfile(h3.MiniMaxH3Model)).resolve()
        provenance = {"h3_source_path": str(source),
                      "h3_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                      "model_class": f"{type(diffusion).__module__}.{type(diffusion).__qualname__}",
                      "frequency_source": "diffusion.rope.inv_freq",
                      "actual_reference_clean_sha256": clean_sha,
                      "parent_attention_evidence_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
                      "no_checkpoint_weight_mutation": True}
        options = model.model_options.get("transformer_options", {})
        if options.get("optimized_attention_override") is not None:
            raise ValueError("existing attention override unsupported")
        replacements = options.get("patches_replace", {}).get("dit", {})
        if any(("double_block", i) in replacements for i in range(50)):
            raise ValueError("use PhaseRoPE instead of, not on top of, another DiT block patch")
        state = PhaseState(metadata, diffusion.rope.inv_freq, delta_frames, alpha, start_frame,
                           end_frame, block_start, block_end, step_start, step_end, run_id, audit_dir,
                           model_contract=contract, model_ref=weakref.ref(diffusion), source_provenance=provenance)
        cloned = model.clone()
        for index in range(50):
            cloned.set_model_patch_replace(PhaseBlockPatch(state, index), "dit", "double_block", index)
        return (cloned,)


NODE_CLASS_MAPPINGS = {"H3PhaseRoPE": H3PhaseRoPE}
NODE_DISPLAY_NAME_MAPPINGS = {"H3PhaseRoPE": "H3 reference-only temporal RoPE (diagnostic)"}
