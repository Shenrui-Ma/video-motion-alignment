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
        from r120_contract import validate_job, ROOT, read, geometry
        from pathlib import Path
        row = validate_job(run_id)
        allowed = Path(read(ROOT/'configs/runtime.json')['remote_root'])/'audit/x0'
        if Path(output_dir)!=allowed or (width,height,length)!=tuple(geometry(row['case'])[k] for k in ('width','height','frames')):
            raise ValueError('R26 passive recorder path/geometry mismatch')
        config = CaptureConfig(run_id, output_dir, width, height, length)
        cloned = model.clone()
        cloned.add_wrapper_with_key(WrappersMP.SAMPLER_SAMPLE, key, PassiveRecorder(config))
        return (cloned,)


NODE_CLASS_MAPPINGS = {"H3X0Readout": H3X0Readout}
NODE_DISPLAY_NAME_MAPPINGS = {"H3X0Readout": "H3 passive x0 readout (Euler20)"}
