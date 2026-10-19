"""Staged passive x0 recorder. Not installed in the running Comfy service."""

from .core import CaptureConfig, PassiveRecorder


class H3X0Readout:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",),
            "run_id": ("STRING", {"default": "x0_readout_unique_run"}),
            "output_dir": ("STRING", {"default": "/tmp/h3-x0-readout"}),
            "width": ("INT", {"default": 1312, "min": 32, "step": 32}),
            "height": ("INT", {"default": 736, "min": 32, "step": 32}),
            "length": ("INT", {"default": 141, "min": 5, "step": 17}),
        }}

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "apply"
    CATEGORY = "research/H3X0Readout"

    def apply(self, model, run_id, output_dir, width, height, length):
        from comfy.patcher_extension import WrappersMP
        import comfy.ldm.minimax.model as h3

        if not isinstance(model.get_model_object("diffusion_model"), h3.MiniMaxH3Model):
            raise TypeError("H3X0Readout requires MiniMaxH3Model")
        key = "H3X0Readout/passive-v1"
        if model.get_wrappers(WrappersMP.SAMPLER_SAMPLE, key):
            raise ValueError("H3X0Readout already registered on this model")
        from pathlib import Path
        allowed = Path("/data5/researcher/h3_runs/timing_cross_source_r20_20261016/audit/x0")
        if (not Path(output_dir).is_absolute() or Path(output_dir).resolve() != allowed.resolve() or
                run_id not in ("r20_s07_native", "r20_s07_full_6to14") or
                (width, height, length) != (1312, 736, 141)):
            raise ValueError("R20 x0 path/identity/geometry contract mismatch")
        config = CaptureConfig(run_id, output_dir, width, height, length)
        cloned = model.clone()
        cloned.add_wrapper_with_key(WrappersMP.SAMPLER_SAMPLE, key, PassiveRecorder(config))
        return (cloned,)


NODE_CLASS_MAPPINGS = {"H3X0Readout": H3X0Readout}
NODE_DISPLAY_NAME_MAPPINGS = {"H3X0Readout": "H3 passive x0 readout (Euler20)"}
