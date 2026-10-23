"""Opt-in Comfy node for independently tested reference-time coverage."""
from .attention import attach_h3_coverage
from .frozen import load_frozen
from .routing import CoverageConfig


class H3TemporalCoverageV2:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",), "positive": ("CONDITIONING",),
            "enabled": ("BOOLEAN", {"default": False}),
            "alpha": ("FLOAT", {"default": 0.25, "min": 0., "max": 1.}),
            "start_frame": ("INT", {"default": 0, "min": 0}),
            "end_frame": ("INT", {"default": -1, "min": -1,
                "tooltip": "Inclusive source frame; -1 selects the last valid reference positional frame."}),
            "step_start": ("INT", {"default": 0, "min": 0, "max": 19,
                "tooltip": "Zero-based inclusive denoising step; 0 starts at step 1."}),
            "step_end": ("INT", {"default": 20, "min": 1, "max": 20,
                "tooltip": "Zero-based exclusive denoising step; 20 includes step 20."}),
            "block_start": ("INT", {"default": 0, "min": 0, "max": 49}),
            "block_end": ("INT", {"default": 50, "min": 1, "max": 50}),
            "radius": ("INT", {"default": 2, "min": 0, "max": 255}),
            "entropy": ("FLOAT", {"default": 0.5, "min": 0.000001}),
            "temporal_penalty": ("FLOAT", {"default": 0.25, "min": 0.}),
            "iterations": ("INT", {"default": 64, "min": 1}),
            "tolerance": ("FLOAT", {"default": 0.0002, "min": 0.000001, "max": 0.999}),
            "min_quality_span": ("FLOAT", {"default": 0.001, "min": 0.}),
            "minimum_mean_gap": ("FLOAT", {"default": 0., "min": 0., "max": 1.}),
            "run_id": ("STRING", {"default": "coverage_run"}),
            "audit_dir": ("STRING", {"default": "", "tooltip": "Absolute directory for unique run audit JSON."}),
        }}

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "apply"
    CATEGORY = "research/H3TemporalCoverageV2"

    def apply(self, model, positive, enabled=False, alpha=0.25,
              start_frame=0, end_frame=-1, step_start=0, step_end=20,
              block_start=0, block_end=50, radius=2, entropy=0.5,
              temporal_penalty=0.25, iterations=64, tolerance=2e-4,
              min_quality_span=1e-3, minimum_mean_gap=0.,
              run_id="coverage_run", audit_dir=""):
        # Disabled graphs do not import Comfy, load frozen sources or create files.
        if not enabled:
            return (model,)
        for lo, hi, limit, name in ((step_start, step_end, 20, "step"),
                                    (block_start, block_end, 50, "block")):
            if type(lo) is not int or type(hi) is not int or not 0 <= lo < hi <= limit:
                raise ValueError(f"invalid half-open {name} interval")
        frozen = load_frozen()
        metadata = frozen.layout.conditioning_metadata(positive)
        reference = next(r for r in metadata["refs"] if r["kind"] in ("video", "video_audio"))
        last_frame = sum(frozen.layout.frame_spans(reference["latent_t"])) - 1
        if end_frame == -1:
            end_frame = last_frame
        frozen.layout.event_latent_range(start_frame, end_frame, reference["latent_t"])
        config = CoverageConfig(radius=radius, entropy=entropy, temporal_penalty=temporal_penalty,
                                iterations=iterations, tolerance=tolerance,
                                min_quality_span=min_quality_span, minimum_mean_gap=minimum_mean_gap)
        result = attach_h3_coverage(
            model, positive, core=frozen.core, enabled=True, config=config, alpha=alpha,
            start_frame=start_frame, end_frame=end_frame, block_start=block_start,
            block_end=block_end, step_start=step_start, step_end=step_end,
            run_id=run_id, audit_dir=audit_dir)
        return (result,)
