"""Independent opt-in same-time guidance controller; no intermediate decoding."""
from .attention import FeatureConfig, attach
from .frozen import load_frozen


class H3TemporalGainFieldFixedBudget:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",), "positive": ("CONDITIONING",),
            "enabled": ("BOOLEAN", {"default": False}),
            "mode": (["gain_field_fixed_budget", "fixed"],),
            "alpha_prior": ("FLOAT", {"default": .25, "min": 0., "max": 1.}),
            "alpha_max": ("FLOAT", {"default": .5, "min": 0., "max": 1.}),
            "prior_weight": ("FLOAT", {"default": 1., "min": 0.}),
            "smoothness": ("FLOAT", {"default": .625, "min": 0.}),
            "probes": ("INT", {"default": 8, "min": 1, "max": 32}),
            "basis": (["centered"],),
            "start_frame": ("INT", {"default": 0, "min": 0}),
            "end_frame": ("INT", {"default": -1, "min": -1}),
            "step_start": ("INT", {"default": 0, "min": 0, "max": 19}),
            "step_end": ("INT", {"default": 20, "min": 1, "max": 20}),
            "block_start": ("INT", {"default": 0, "min": 0, "max": 49}),
            "block_end": ("INT", {"default": 50, "min": 1, "max": 50}),
            "run_id": ("STRING", {"default": "gain_field_run"}),
            "audit_dir": ("STRING", {"default": ""}),
        }}

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "apply"
    CATEGORY = "research/H3TemporalGainFieldFixedBudget"

    def apply(self, model, positive, enabled=False, mode="gain_field_fixed_budget",
              alpha_prior=.25, alpha_max=.5, prior_weight=1., smoothness=.625,
              probes=8, basis="centered", start_frame=0, end_frame=-1,
              step_start=0, step_end=20, block_start=0, block_end=50,
              run_id="gain_field_run", audit_dir=""):
        if not enabled:
            return (model,)
        for lo, hi, limit in ((step_start, step_end, 20), (block_start, block_end, 50)):
            if type(lo) is not int or type(hi) is not int or not 0 <= lo < hi <= limit:
                raise ValueError("invalid half-open step/block interval")
        if basis != "centered":
            raise ValueError("gain field requires rank-one centered tangent")
        config = FeatureConfig(mode=mode, alpha_prior=alpha_prior, alpha_max=alpha_max,
                               prior_weight=prior_weight, smoothness=smoothness,
                               probes=probes, basis=basis)
        frozen = load_frozen()
        metadata = frozen.layout.conditioning_metadata(positive)
        reference = next(r for r in metadata["refs"] if r["kind"] in ("video", "video_audio"))
        if end_frame == -1:
            end_frame = sum(frozen.layout.frame_spans(reference["latent_t"])) - 1
        frozen.layout.event_latent_range(start_frame, end_frame, reference["latent_t"])
        result = attach(model, positive, config=config, start_frame=start_frame, end_frame=end_frame,
                        step_start=step_start, step_end=step_end, block_start=block_start,
                        block_end=block_end, run_id=run_id, audit_dir=audit_dir)
        return (result,)
