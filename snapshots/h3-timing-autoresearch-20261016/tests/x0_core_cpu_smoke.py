#!/usr/bin/env python3
"""Integration with installed Comfy classes and real Euler, without model weights.

Run with --comfy-root and --recorder-core. A stdin launcher may provide
_RECORDER_SOURCE instead of --recorder-core to avoid installing staged files.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfy-root", required=True)
    parser.add_argument("--recorder-core")
    parser.add_argument("--compat-bootstrap", required=True)
    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    import torch
    if torch.cuda.is_initialized():
        raise RuntimeError("CUDA was initialized before CPU smoke")
    sys.path.insert(0, args.comfy_root)
    sys.argv = ["x0_core_cpu_smoke", "--cpu", "--disable-dynamic-vram"]
    import comfy.options
    comfy.options.enable_args_parsing()
    spec = importlib.util.spec_from_file_location("h3_existing_compat", args.compat_bootstrap)
    compat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compat)
    compat.install()
    compat.install_video_compat()
    from comfy.nested_tensor import NestedTensor
    from comfy.utils import pack_latents, unpack_latents
    from comfy.patcher_extension import WrapperExecutor
    from comfy.model_base import MiniMaxH3, ModelType, model_sampling
    from comfy.latent_formats import MiniMaxH3Video
    from comfy.samplers import KSAMPLER
    from comfy.k_diffusion.sampling import sample_euler
    from comfy import model_management

    source = globals().get("_RECORDER_SOURCE")
    if source is None:
        source = Path(args.recorder_core).read_text()
    module = types.ModuleType("x0_staged_core_smoke")
    sys.modules[module.__name__] = module
    exec(compile(source, "<staged recorder core>", "exec"), module.__dict__)
    model = MiniMaxH3.__new__(MiniMaxH3)
    torch.nn.Module.__init__(model)
    model.model_sampling = model_sampling(None, ModelType.FLOW_AV)
    model.model_sampling.set_parameters(shift=12, audio_shift=3)
    model.latent_format = MiniMaxH3Video()
    results = []
    with tempfile.TemporaryDirectory(prefix="h3-x0-cpu-") as temporary:
        for kind in ("packed_euler", "nested_callback"):
            config = module.CaptureConfig(kind, temporary, 32, 32, 5)
            model.latent_shapes = list(config.shapes)
            video = torch.arange(torch.Size(config.shapes[0]).numel(), dtype=torch.float32).reshape(config.shapes[0]) / 200
            audio = torch.arange(torch.Size(config.shapes[1]).numel(), dtype=torch.float32).reshape(config.shapes[1]) / 300
            noise, _ = pack_latents((video, audio))
            latent = torch.zeros_like(noise)
            sigmas = torch.linspace(1, 0, 21)
            calls = []

            class Guider:
                inner_model = model
                model_patcher = types.SimpleNamespace(model=model)
                cfg = 1.0

                def __call__(self, x, sigma, **kwargs):
                    return x * 0.25 + 0.1

            guider = Guider()
            sampler = KSAMPLER(sample_euler)
            baseline = sampler.sample(guider, sigmas, {"seed": 123, "model_options": {}},
                                      None, noise, latent, disable_pbar=True)

            def original_callback(step, x0, x, total):
                calls.append((step, x0, x, total))

            original_sample = sampler.sample
            if kind == "nested_callback":
                def nested_sample(model_wrap, sigmas, extra_args, callback, noise,
                                  latent_image=None, denoise_mask=None, disable_pbar=False):
                    def nested_callback(step, x0, x, total):
                        return callback(step, NestedTensor(unpack_latents(x0, config.shapes)),
                                        NestedTensor(unpack_latents(x, config.shapes)), total)
                    return sampler.sample(model_wrap, sigmas, extra_args, nested_callback,
                                          noise, latent_image, denoise_mask, disable_pbar)
                original_sample = nested_sample
            recorder = module.PassiveRecorder(config)
            executor = WrapperExecutor.new_class_executor(original_sample, sampler, [recorder])
            before_noise, before_sigmas = noise.clone(), sigmas.clone()
            result = executor.execute(guider, sigmas, {"seed": 123, "model_options": {}},
                                      original_callback, noise, latent, None, True)
            assert torch.equal(result, baseline)
            assert torch.equal(noise, before_noise) and torch.equal(sigmas, before_sigmas)
            assert [call[0] for call in calls] == list(range(20))
            manifest = json.loads((Path(temporary) / kind / "manifest.json").read_text())
            assert manifest["status"] == "complete"
            assert manifest["audio_scale"] == 4
            final = torch.load(Path(temporary) / kind / "sampler_final.pt", weights_only=True)
            actual_out = model.process_latent_out(NestedTensor(unpack_latents(result, config.shapes)))
            assert torch.equal(final["video"], actual_out.unbind()[0])
            assert torch.equal(final["audio"], actual_out.unbind()[1])
            results.append({"case": kind, "output_bitwise_unchanged": True,
                            "callback_count": len(calls), "normalization_matches_real_model": True,
                            "endpoint_comparison": manifest["endpoint_comparison"]})
    assert str(model_management.get_torch_device()) == "cpu"
    assert not torch.cuda.is_initialized()
    print("H3_X0_CPU_SMOKE=" + json.dumps({
        "success": True, "torch_version": str(torch.__version__), "cuda_initialized": False,
        "device": "cpu", "loaded_model_weights": False,
        "recorder_core_sha256": hashlib.sha256(source.encode()).hexdigest(), "cases": results}))


if __name__ == "__main__":
    main()
