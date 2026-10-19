#!/usr/bin/env python3
"""Real Comfy CPU clone/guider/Euler/wrapper integration, without model weights.

Run in the existing Comfy environment. Only DiT QKV/geometry are tiny test data;
the node, ModelPatcher.clone, Guider_Basic, wrapper executor, Euler sampler,
H3 process_latent_out and independent H3X0Readout execute real implementations.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfy-root", required=True)
    parser.add_argument("--compat-bootstrap", required=True)
    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    import torch
    torch.set_num_threads(1)
    if torch.cuda.is_initialized():
        raise RuntimeError("CUDA must remain uninitialized")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "extensions"))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, args.comfy_root)
    sys.argv = ["feedback_wrapper_smoke", "--cpu", "--disable-dynamic-vram", "--use-pytorch-cross-attention"]
    import comfy.options
    comfy.options.enable_args_parsing()
    spec = importlib.util.spec_from_file_location("h3_feedback_existing_compat", args.compat_bootstrap)
    compat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compat)
    compat.install()
    compat.install_video_compat()
    from comfy.model_base import MiniMaxH3, ModelType, model_sampling
    from comfy.latent_formats import MiniMaxH3Video
    from comfy.model_patcher import ModelPatcher, create_model_options_clone
    from comfy.patcher_extension import WrapperExecutor, WrappersMP, merge_nested_dicts, get_all_wrappers
    from comfy.samplers import KSAMPLER
    from comfy.k_diffusion.sampling import sample_euler
    from comfy_extras.nodes_custom_sampler import Guider_Basic
    from comfy import model_management
    from comfy.nested_tensor import NestedTensor
    from comfy.utils import unpack_latents
    import comfy.ldm.minimax.model as h3
    from H3FeedbackRouter import H3FeedbackRouter
    from H3FeedbackRouter.core import WRAPPER_KEY
    from H3FeedbackRouter.dependencies import router
    from H3X0Readout import H3X0Readout
    import H3X0Readout.core as readout_core
    from test_feedback_support import Observations, cpu_attention, run_blocks, dense_attention

    # Reproduce production node loading rather than only canonical imports.
    # nodes.load_custom_node uses an absolute-path module name for .py files,
    # creating a second Guider_Basic class object from the same official source.
    import nodes
    sampler_source = Path(args.comfy_root).resolve() / "comfy_extras/nodes_custom_sampler.py"
    if not asyncio.run(nodes.load_custom_node(str(sampler_source), module_parent="comfy_extras")):
        raise RuntimeError("actual Comfy node loader failed")
    graph = json.loads((root / "configs/r14_s05_seed1313_native_host9.json").read_text())
    graph_guider_type = graph["7"]["class_type"]
    assert graph_guider_type == "BasicGuider"
    graph_guider_node = nodes.NODE_CLASS_MAPPINGS[graph_guider_type]

    def graph_guider(patcher):
        return graph_guider_node.execute(model=patcher, conditioning=positive)[0]

    model = MiniMaxH3.__new__(MiniMaxH3)
    torch.nn.Module.__init__(model)
    diffusion = h3.MiniMaxH3Model.__new__(h3.MiniMaxH3Model)
    torch.nn.Module.__init__(diffusion)
    diffusion.patch_size = (1, 2, 2)
    diffusion.latents_dim = 24
    diffusion.blocks = torch.nn.ModuleList(torch.nn.Identity() for _ in range(50))
    model.diffusion_model = diffusion
    model.model_sampling = model_sampling(None, ModelType.FLOW_AV)
    model.model_sampling.set_parameters(shift=12, audio_shift=3)
    model.latent_format = MiniMaxH3Video()
    shapes = ((1, 24, 42, 46, 82), (1, 32, 2, 235))
    model.latent_shapes = list(shapes)
    base = ModelPatcher(model, torch.device("cpu"), torch.device("cpu"), size=1)
    reference = torch.zeros(shapes[0])
    positive = [[torch.zeros((1, 2, 8)), {"minimax_refs": [
        {"kind": "image", "latent": torch.zeros((1, 24, 1, 2, 2)), "latent_h": 2, "latent_w": 2},
        {"kind": "video", "latent": reference, "latent_t": 42, "latent_h": 46,
         "latent_w": 82, "ref_audio_t": 0}]}]]
    count = sum(torch.Size(s).numel() for s in shapes)
    noise = torch.arange(count, dtype=torch.float32).reshape(1, 1, -1) / count
    latent = torch.zeros_like(noise)
    sigmas = torch.linspace(1, 0, 21)
    sampler = KSAMPLER(sample_euler)
    q = torch.arange(168, dtype=torch.float32).reshape(1, 1, 84, 2) / 100
    baseline_value = dense_attention(q, q.flip(-2).contiguous(), torch.sin(q * 3))[0].mean()

    baseline_guider = graph_guider(base)
    assert type(baseline_guider) is not Guider_Basic
    assert Path(sys.modules[type(baseline_guider).__module__].__file__).resolve() == sampler_source
    baseline_guider.inner_model = model
    def baseline_prediction(self, x, sigma, model_options=None, seed=None, **kwargs):
        return x * 0.25 + baseline_value * 0.001
    baseline_guider.predict_noise = types.MethodType(baseline_prediction, baseline_guider)
    baseline = sampler.sample(baseline_guider, sigmas, {"seed": 123, "model_options": {}},
                              None, noise, latent, disable_pbar=True)
    rows, results, captured = [], {}, {}
    lags = [5, 3, 2, 3, -4, 4, None, 0, 0, 0, 0, 0, 0, 4, 4]
    expected_mask = [6, 7, 8, 9, 11, 19]
    with tempfile.TemporaryDirectory(prefix="h3-feedback-wrapper-cpu-") as temp:
        for name, policy, order, nested_cb in (
                ("off_after", "off", "feedback_first", False),
                ("off_before", "off", "readout_first", True),
                ("feedback_after", "feedback", "feedback_first", False),
                ("fixed_before", "fixed", "readout_first", False),
                ("feedback_original_readout", "feedback", "feedback_first", False)):
            def install_feedback(patcher):
                return H3FeedbackRouter().apply(
                    patcher, positive, policy, "6,7,8,9,11,19" if policy == "fixed" else "",
                    50, 65, 1312, 736, 141, name, str(Path(temp) / "router"))[0]
            def install_readout(patcher):
                return H3X0Readout().apply(patcher, name, str(Path(temp) / "x0"), 1312, 736, 141)[0]
            patched = install_readout(install_feedback(base)) if order == "feedback_first" else install_feedback(install_readout(base))
            sampled = patched.clone()
            wrapper = sampled.get_wrappers(WrappersMP.SAMPLER_SAMPLE, WRAPPER_KEY)[0]
            state = wrapper.state
            assert wrapper is patched.get_wrappers(WrappersMP.SAMPLER_SAMPLE, WRAPPER_KEY)[0]
            patches = sampled.model_options["transformer_options"]["patches_replace"]["dit"]
            assert all(patches[("double_block", i)].state is state for i in range(50))
            assert sampled.model_options is not patched.model_options
            assert sampled.model_options["transformer_options"] is not patched.model_options["transformer_options"]
            try:
                install_feedback(sampled)
            except ValueError as error:
                assert "already registered" in str(error)
            else:
                raise AssertionError("duplicate wrapper was not rejected")
            state.observer = Observations(lags)
            tiny_plan = {"seq_len": 84, "frame_rows": 1, "latent_interval_half_open": [14, 20],
                         "query_interval_half_open": [56, 62], "reference_video_segment": [0, 42]}
            state.plan_for = lambda _: tiny_plan
            guider = graph_guider(sampled)
            assert type(guider) is type(baseline_guider)
            guider.inner_model = model
            def prediction(self, x, sigma, model_options=None, seed=None, **kwargs):
                values = run_blocks(state, patches, sigmas=sigmas)
                return x * 0.25 + values.mean() * 0.001
            guider.predict_noise = types.MethodType(prediction, guider)
            # Same merge used by sampler_helpers.prepare_model_patcher, without loading weights.
            options = create_model_options_clone(guider.model_options)
            merge_nested_dicts(options["transformer_options"].setdefault("wrappers", {}), sampled.wrappers, copy_dict1=False)
            options["transformer_options"]["sample_sigmas"] = sigmas
            wrappers = get_all_wrappers(WrappersMP.SAMPLER_SAMPLE, options, is_model_options=True)
            assert sum(getattr(w, "state", None) is state for w in wrappers) == 1
            callback_identity, callback_indices = {}, []
            def callback(index, x0, x, total):
                callback_indices.append(index)
                callback_identity[index] = (id(x0), id(x), total)
            def original_sample(model_wrap, grid, extra_args, cb, noise, latent_image, mask, disable):
                def wrapped_callback(index, x0, x, total):
                    if nested_cb:
                        x0 = NestedTensor(unpack_latents(x0, shapes))
                        x = NestedTensor(unpack_latents(x, shapes))
                    ids = id(x0), id(x), total
                    value = cb(index, x0, x, total)
                    assert callback_identity[index] == ids
                    return value
                return sampler.sample(model_wrap, grid, extra_args, wrapped_callback,
                                      noise, latent_image, mask, disable)
            executor = WrapperExecutor.new_class_executor(original_sample, sampler, wrappers)
            old_noise, old_reference, old_sigmas = noise.clone(), reference.clone(), sigmas.clone()
            old_rng, old_env = torch.random.get_rng_state().clone(), dict(os.environ)
            capture_steps = (5, 10, 15, 19) if name == "feedback_original_readout" else (5, 6, 7, 8, 9, 10, 15, 19)
            with cpu_attention(), patch.object(readout_core, "CAPTURE_STEPS", capture_steps):
                result = executor.execute(guider, sigmas, {"seed": 123, "model_options": options},
                                          callback, noise, latent, None, True)
            assert torch.equal(noise, old_noise) and torch.equal(reference, old_reference) and torch.equal(sigmas, old_sigmas)
            assert torch.equal(torch.random.get_rng_state(), old_rng) and dict(os.environ) == old_env
            assert callback_indices == list(range(20))
            assert state.audit["completed_calls"] == 1000 and state.audit["completed_forward_calls"] == 20
            assert state.active_indices == ([] if policy == "off" else expected_mask)
            x0_manifest = json.loads((Path(temp) / "x0" / name / "manifest.json").read_text())
            assert x0_manifest["status"] == "complete" and x0_manifest["callback_count"] == 20
            assert x0_manifest["capture_steps_zero_based"] == list(capture_steps)
            captured[name] = {r["step_zero_based"]: (r["video"], r["audio"])
                              for r in x0_manifest["captures"]}
            final = torch.load(Path(temp) / "x0" / name / "sampler_final.pt", map_location="cpu", weights_only=True)
            ready = model.process_latent_out(NestedTensor(unpack_latents(result, shapes))).unbind()
            assert torch.equal(final["video"], ready[0]) and torch.equal(final["audio"], ready[1])
            if policy == "off":
                assert torch.equal(result, baseline)
            results[name] = result
            rows.append({"case": name, "policy": policy, "wrapper_order": order,
                         "nested_callback": nested_cb, "state_shared_through_actual_clone": True,
                         "callbacks_unchanged": True, "noise_reference_rng_env_unchanged": True,
                         "active_indices": state.active_indices, "NFE": 20,
                         "capture_steps_zero_based": list(capture_steps),
                         "blocks": state.audit["completed_calls"], "audio_scale": model.audio_scale(),
                         "guider_contract": state.audit["feedback"]["guider_contract"],
                         "guider_created_by_actual_graph_node_registry": True,
                         "passive_readout_normalization_matches_real_model": True})
        assert torch.equal(results["off_after"], results["off_before"])
        assert torch.equal(results["feedback_after"], results["fixed_before"])
        assert torch.equal(results["feedback_after"], results["feedback_original_readout"])
        for index in (5, 10, 15, 19):
            assert captured["feedback_after"][index] == captured["feedback_original_readout"][index]
    assert not torch.cuda.is_initialized()
    assert str(model_management.get_torch_device()) == "cpu"
    print("H3_FEEDBACK_CPU_SMOKE=" + json.dumps({
        "success": True, "device": "cpu", "loaded_model_weights": False,
        "comfy_root": str(Path(args.comfy_root).resolve()),
        "runtime_sha256": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(list((root / "extensions").rglob("*.py")) +
                            [root / "scripts/compatibility_bootstrap.py", Path(__file__).resolve()])
            if "__pycache__" not in p.parts},
        "comfy_source_sha256": {rel: hashlib.sha256((Path(args.comfy_root) / rel).read_bytes()).hexdigest()
            for rel in json.loads((root / "configs/parent_core_hashes.json").read_text())},
        "CUDA_initialized": False, "torch_version": str(torch.__version__),
        "core_sha256": hashlib.sha256((root / "extensions/H3FeedbackRouter/core.py").read_bytes()).hexdigest(),
        "scope": "real Comfy clone/guider/wrapper/Euler/normalization with tiny fake DiT attention",
        "graph_guider_class_type": graph_guider_type,
        "graph_guider_source_sha256": hashlib.sha256(sampler_source.read_bytes()).hexdigest(),
        "actual_node_loader_module_alias_tested": True,
        "off_equals_native": True, "fixed_mask_equals_feedback": True,
        "expanded_readout_common_x0_and_final_bitwise_equal": True, "cases": rows}))


if __name__ == "__main__":
    main()
