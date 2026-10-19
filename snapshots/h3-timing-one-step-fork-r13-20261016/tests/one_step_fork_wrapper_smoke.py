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
    sys.argv = ["fork_wrapper_smoke", "--cpu", "--disable-dynamic-vram", "--use-pytorch-cross-attention"]
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
    from H3OneStepForkAudit import install, ModelAudit
    from H3OneStepForkAudit.core import KEY, restore_uuid, condition_signature, readout, output_head_contract
    from fork_support import MemorySource

    from H3CounterfactualRouter.dependencies import router
    from H3X0Readout import H3X0Readout
    from counterfactual_support import Observations, cpu_attention, run_blocks, dense_attention
    from unittest.mock import patch

    # Reproduce production node loading rather than only canonical imports.
    # nodes.load_custom_node uses an absolute-path module name for .py files,
    # creating a second Guider_Basic class object from the same official source.
    import nodes
    sampler_source = Path(args.comfy_root).resolve() / "comfy_extras/nodes_custom_sampler.py"
    if not asyncio.run(nodes.load_custom_node(str(sampler_source), module_parent="comfy_extras")):
        raise RuntimeError("actual Comfy node loader failed")
    graph = json.loads((root / "configs/r13_s05_one_step_fork.json").read_text())
    assert graph["60"]["class_type"] == "H3OneStepForkAudit"
    graph_guider_type = "BasicGuider"
    assert graph_guider_type == "BasicGuider"
    graph_guider_node = nodes.NODE_CLASS_MAPPINGS[graph_guider_type]

    # Production custom-node directory loading must not depend on extensions in sys.path.
    saved_path = list(sys.path)
    hidden = {k: v for k, v in list(sys.modules.items()) if k == 'H3CounterfactualRouter' or k.startswith('H3CounterfactualRouter.')}
    try:
        sys.path[:] = [p for p in sys.path if p != str(root / 'extensions')]
        for key in hidden: del sys.modules[key]
        assert asyncio.run(nodes.load_custom_node(str(root / 'extensions/H3OneStepForkAudit')))
        actual_node = nodes.NODE_CLASS_MAPPINGS['H3OneStepForkAudit']
        node_module = sys.modules[actual_node.__module__]
        install, ModelAudit = node_module.install, node_module.ModelAudit
        assert actual_node.RETURN_TYPES == ('STRING',) and actual_node.OUTPUT_NODE is True
    finally:
        sys.path[:] = saved_path
        sys.modules.update(hidden)

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
    model.manual_cast_dtype = torch.float32
    model.concat_keys = ()
    diffusion.dtype = torch.float32
    diffusion.hidden_size = 8
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


    processed = model.extra_conds(cross_attn=positive[0][0], device=torch.device('cpu'),
        latent_shapes=list(shapes), minimax_refs=positive[0][1]['minimax_refs'],
        noise=noise, seed=2026101311)
    assert type(processed['minimax_payload']).__name__ == 'CONDConstant'
    assert type(processed['minimax_payload'].cond['layout']).__name__ == 'PackedLayout'
    assert type(processed['c_crossattn']).__name__ == 'CONDRegular'
    tiny_plan = {'seq_len':84,'frame_rows':1,'latent_interval_half_open':[14,20],
                 'query_interval_half_open':[56,62],'reference_video_segment':[0,42]}

    def setup_guider(patcher):
        guider = graph_guider(patcher)
        guider.inner_model = model
        guider.conds = {'positive': [dict(guider.original_conds['positive'][0], model_conds=processed)]}
        options = create_model_options_clone(guider.model_options)
        merge_nested_dicts(options['transformer_options'].setdefault('wrappers', {}), patcher.wrappers, copy_dict1=False)
        options['transformer_options']['sample_sigmas'] = sigmas
        guider.model_options = options
        return guider, options

    # Actual model condition-noise helpers repeat a local CPU Generator; no global RNG.
    small_video = torch.arange(24*2*4*4,dtype=torch.float32).reshape(1,24,2,4,4)/100
    small_audio = torch.arange(32*2*3,dtype=torch.float32).reshape(1,32,2,3)/100
    payload = {'seed':123,'cond_video_latents':[small_video],'cond_audio_latents':[small_audio],
               'visual_cond_noise_aug':0.999,'audio_cond_noise_aug':0.999}
    previous_rng = torch.random.get_rng_state().clone()
    cv = diffusion._cond_video_rows(payload, torch.device('cpu'))
    ca = diffusion._cond_audio_rows(payload, torch.device('cpu'))
    assert torch.equal(cv,diffusion._cond_video_rows(payload,torch.device('cpu')))
    assert torch.equal(ca,diffusion._cond_audio_rows(payload,torch.device('cpu')))
    assert torch.equal(previous_rng,torch.random.get_rng_state())
    # Same MixedPrecisionOps factory as the actual INT8 loader. The unquantized
    # fp32 head state_dict is loaded into bf16 Parameters by the official loader.
    # No mocked head or checkpoint weights are used.
    import comfy.ops
    final_rng = torch.random.get_rng_state().clone()
    final_ops = comfy.ops.mixed_precision_ops(compute_dtype=torch.bfloat16)
    final = h3.FinalLayer(5376, 2, 96, 32, 1e-6, dtype=torch.bfloat16,
                         device=torch.device('cpu'), operations=final_ops)
    shapes_by_name = {'norm.weight': (5376,), 'adaln_proj.linear.weight': (10752, 2),
                     'adaln_proj.linear.bias': (10752,), 'video_out.weight': (96, 5376),
                     'video_out.bias': (96,), 'audio_out.weight': (32, 5376), 'audio_out.bias': (32,)}
    head_state_dict = {name: (torch.ones(shape, dtype=torch.float32) if name == 'norm.weight' else
        (torch.arange(torch.Size(shape).numel(), dtype=torch.float32).reshape(shape) % 31 - 15) / 65536)
        for name, shape in shapes_by_name.items()}
    final.load_state_dict(head_state_dict, strict=True)
    assert torch.equal(final_rng, torch.random.get_rng_state())
    head_contract = output_head_contract(final)
    assert head_contract['bank_size'] == 1 and head_contract['pdd_active'] is False
    assert isinstance(final.video_out, final_ops.Linear) and not isinstance(final.video_out, torch.nn.Linear)
    assert final.video_out.weight.dtype == final.audio_out.weight.dtype == torch.bfloat16
    assert all(value.dtype == torch.float32 for value in head_state_dict.values())
    head_x = (torch.arange(6 * 5376, dtype=torch.float32).reshape(6, 5376) / 8192).to(torch.bfloat16)
    head_t = torch.tensor([[0.25, 0.5], [0.75, 1.0]], dtype=torch.bfloat16)
    video_seg, audio_seg = (1, 3, 0), (4, 6, 1)
    head_calls = []
    head_handles = [getattr(final, name).register_forward_hook(
        lambda module, args, result, name=name: head_calls.append((name, tuple(result.shape))))
        for name in ('video_out', 'audio_out')]
    with torch.no_grad():
        expected_heads = {m: tuple(v.clone() for v in final(head_x, head_t, video_seg, audio_seg,
                          sigmas[m], sigmas, (12., 3.))) for m in (7, 11, 15)}
        shift, scale = final.adaln_proj(head_t)
        expected_segments = []
        for name, (a, b, row) in (('video_out', video_seg), ('audio_out', audio_seg)):
            mod = (final.norm(head_x[a:b]) * (1.0 + scale[row]) + shift[row]).to(torch.float32)
            expected_segments.append(getattr(final, name)(mod))
        assert all(torch.equal(a, b) for a, b in zip(expected_heads[7], expected_segments))
    assert head_calls[:6] == [('video_out', (2, 96)), ('audio_out', (2, 32))] * 3
    head_calls.clear()
    head_data_before = [readout.tensor_signature(v) for v in (head_x, head_t, *final.parameters())]

    rows=[]
    before_env=dict(os.environ)
    with tempfile.TemporaryDirectory(prefix='h3-fork-real-cpu-') as temporary:
        temp=Path(temporary)
        prototype,prototype_options=setup_guider(base)
        source=MemorySource(temp,condition_signature(prototype),noise,reference,euler=sample_euler)
        for use_clone in [False,True]:
            name='real_clone' if use_clone else 'real_direct'
            patched,state=install(base,positive,source,name,str(temp/'out'),observer=Observations([0]),require_cuda=False)
            sampled=patched.clone() if use_clone else patched
            wrapper=sampled.get_wrappers(WrappersMP.SAMPLER_SAMPLE,KEY)[0]
            assert wrapper.state is state
            assert all(p.state is state for p in sampled.model_options['transformer_options']['patches_replace']['dit'].values())
            state.plan_for=lambda _:tiny_plan
            guider=graph_guider(sampled)
            original_uuid=guider.original_conds['positive'][0]['uuid']
            state.audit['fork']['uuid_restoration']=restore_uuid(guider,source)
            assert guider.original_conds['positive'][0]['uuid']!=original_uuid
            guider.inner_model=model
            guider.conds={'positive':[dict(guider.original_conds['positive'][0])]}
            options=create_model_options_clone(guider.model_options)
            merge_nested_dicts(options['transformer_options'].setdefault('wrappers',{}),sampled.wrappers,copy_dict1=False)
            guider.model_options=options
            patches=options['transformer_options']['patches_replace']['dit']
            diffusion.final_layer=final
            calls=[]
            def prediction(self,x,sigma,model_options=None,seed=None):
                calls.append((state.phase.copy(),x.clone(),sigma.clone()))
                run_blocks(state,patches,sigmas=model_options['transformer_options']['sample_sigmas'])
                with torch.no_grad():
                    head_outputs = final(head_x, head_t, video_seg, audio_seg, sigma.reshape(()),
                                         model_options['transformer_options']['sample_sigmas'], (12., 3.))
                assert all(torch.equal(a, b) for a, b in zip(
                    head_outputs, expected_heads[state.phase['eval_euler_index']]))
                return x*0.25+0.015625
            guider.predict_noise=types.MethodType(prediction,guider)
            old_rng=torch.random.get_rng_state().clone()
            with cpu_attention(), ModelAudit(model,state), \
                 patch.object(model.model_sampling,'noise_scaling',side_effect=AssertionError('noise_scaling called')), \
                 patch.object(model.model_sampling,'inverse_noise_scaling',side_effect=AssertionError('inverse_noise_scaling called')), \
                 patch.object(sampler,'sample',side_effect=AssertionError('sampler executor called')):
                # Real process_conds/extra_conds and SAMPLER_SAMPLE executor inside real inner_sample.
                output=guider.inner_sample(noise,latent,torch.device('cpu'),sampler,sigmas,None,None,True,2026101311,latent_shapes=list(shapes))
            assert torch.equal(output,torch.zeros_like(noise))
            assert state.extra_conds_calls==1 and len(calls)==6 and len(state.audit['fork']['pdd'])==6
            assert condition_signature(guider)==source.condition
            assert state.audit['completed_calls']==300 and state.audit['routed_calls']==0
            assert state.audit['fork']['sampler_callbacks']==0 and state.audit['fork']['euler_updates']==0
            assert torch.equal(old_rng,torch.random.get_rng_state()) and dict(os.environ)==before_env
            assert all(p['full_next_input_exact'] and p['full_next_endpoint_exact'] for p in state.audit['fork']['pairs'])
            assert state.audit['status']=='complete' and not torch.cuda.is_initialized()
            assert 'extra_conds' not in vars(model)
            assert len(final._forward_pre_hooks)==0
            assert head_calls == [('video_out', (2, 96)), ('audio_out', (2, 32))] * 6
            head_calls.clear()
            assert [readout.tensor_signature(v) for v in (head_x, head_t, *final.parameters())] == head_data_before
            assert all(p['pdd_active'] is False and p['head_mode'] == 'single_linear' and
                       p['bank_size'] == 1 and p['start'] is None and p['stop'] is None
                       for p in state.audit['fork']['pdd'])
            rows.append({'case':name,'NFE':6,'callbacks':0,'Euler_updates':0,'extra_conds_calls':1,
                         'input_and_endpoint_replay_bitwise':True,'head_call_indices':[p['index'] for p in state.audit['fork']['pdd']],
                         'official_head_hook_bitwise_equal':True,'official_stream_slices_bitwise_equal':True,
                         'head_input_parameters_unchanged':True,'head_contract':head_contract,
                         'no_noise_scaling':True,'UUID_restoration_full_condition_hash':True,'RNG_unchanged':True})
    for handle in head_handles: handle.remove()
    print('H3_ONE_STEP_FORK_CPU_SMOKE='+json.dumps({'success':True,'device':'cpu','CUDA_initialized':False,
         'actual_loader_alias':True,'actual_custom_node_directory_loader_without_sys_path':True,
         'actual_H3_conditions':True,'actual_PDD':False,'actual_frozen_single_head':True,'actual_inner_sample':True,
         'actual_mixed_precision_head_factory_and_state_dict_loader':True,
         'head_checkpoint_dtype':'torch.float32','head_loaded_dtype':'torch.bfloat16',
         'core_sha256':hashlib.sha256((root/'extensions/H3OneStepForkAudit/core.py').read_bytes()).hexdigest(),
         'node_sha256':hashlib.sha256((root/'extensions/H3OneStepForkAudit/__init__.py').read_bytes()).hexdigest(),
         'smoke_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cases':rows}))

if __name__=='__main__':main()
