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
    from H3OneStepForkAudit.core import KEY, restore_uuid, condition_signature, readout
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
    # Exercise actual FinalLayer's PDD sigma-grid lookup without checkpoint weights.
    final = h3.FinalLayer.__new__(h3.FinalLayer)
    torch.nn.Module.__init__(final)
    final.norm = torch.nn.Identity()
    final.adaln_proj = lambda _: (torch.zeros((1,2)),torch.zeros((1,2)))
    final.video_out = types.SimpleNamespace(weight=torch.zeros((6,2)),out_features=2)
    final.audio_out = types.SimpleNamespace(weight=torch.zeros((6,2)),out_features=2)
    head_ranges = []
    def fake_head(head, hidden, count, start, stop, shift):
        head_ranges.append((count,start,stop,shift))
        return torch.zeros_like(hidden)
    with patch.object(h3,'_pdd_head',fake_head):
        for _ in range(2):
            final(torch.zeros((4,2)),None,(0,2,0),(2,4,0),sigmas[10],sigmas,(12.,3.))
    assert head_ranges[:2] == head_ranges[2:]

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
            final.norm=torch.nn.Identity()
            diffusion.final_layer=final
            calls=[]
            def prediction(self,x,sigma,model_options=None,seed=None):
                calls.append((state.phase.copy(),x.clone(),sigma.clone()))
                run_blocks(state,patches,sigmas=model_options['transformer_options']['sample_sigmas'])
                with patch.object(h3,'_pdd_head',fake_head):
                    final(torch.zeros((4,2)),None,(0,2,0),(2,4,0),sigma.reshape(()),
                          model_options['transformer_options']['sample_sigmas'],(12.,3.))
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
            rows.append({'case':name,'NFE':6,'callbacks':0,'Euler_updates':0,'extra_conds_calls':1,
                         'input_and_endpoint_replay_bitwise':True,'PDD_indices':[p['index'] for p in state.audit['fork']['pdd']],
                         'no_noise_scaling':True,'UUID_restoration_full_condition_hash':True,'RNG_unchanged':True})
    print('H3_ONE_STEP_FORK_CPU_SMOKE='+json.dumps({'success':True,'device':'cpu','CUDA_initialized':False,
         'actual_loader_alias':True,'actual_custom_node_directory_loader_without_sys_path':True,
         'actual_H3_conditions':True,'actual_PDD':True,'actual_inner_sample':True,
         'core_sha256':hashlib.sha256((root/'extensions/H3OneStepForkAudit/core.py').read_bytes()).hexdigest(),'cases':rows}))

if __name__=='__main__':main()
