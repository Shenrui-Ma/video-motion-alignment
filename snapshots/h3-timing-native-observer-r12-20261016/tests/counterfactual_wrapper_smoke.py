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
    from H3NativeObserverRouter import H3NativeObserverRouter
    from H3NativeObserverRouter.core import KEY, condition_signature, readout
    from H3NativeObserverRouter.dependencies import router
    from H3X0Readout import H3X0Readout
    from counterfactual_support import PhysicalObservations, cpu_attention, run_blocks, dense_attention
    from test_counterfactual import LAGS, EXPECTED
    from unittest.mock import patch

    # Reproduce production node loading rather than only canonical imports.
    # nodes.load_custom_node uses an absolute-path module name for .py files,
    # creating a second Guider_Basic class object from the same official source.
    import nodes
    sampler_source = Path(args.comfy_root).resolve() / "comfy_extras/nodes_custom_sampler.py"
    if not asyncio.run(nodes.load_custom_node(str(sampler_source), module_parent="comfy_extras")):
        raise RuntimeError("actual Comfy node loader failed")
    graph = json.loads((root / "configs/r12_s05_native_observer.json").read_text())
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
        noise=noise, seed=123)
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

    rows = []
    with tempfile.TemporaryDirectory(prefix='h3-counterfactual-cpu-') as temporary:
        temp = Path(temporary)
        # Same actual Euler, one model prediction per step, independently prescribed masks.
        baselines = {}
        for tag, mask in [('native', []), ('variable', EXPECTED)]:
            baseline_state = router.RouterState({'refs':[]},'mass_preserve',1.0,0,0,50,65,0,50,6,20,'reference_'+tag,str(temp))
            baseline_state.plan_for = lambda _: tiny_plan
            baseline_state.selected = lambda block: baseline_state.forward_index in mask and 0 <= block < 50
            baseline_patches = {('double_block',i):router.EventBlockPatch(baseline_state,i) for i in range(50)}
            baseline_guider, baseline_options = setup_guider(base)
            assert type(baseline_guider) is not Guider_Basic
            assert Path(sys.modules[type(baseline_guider).__module__].__file__).resolve() == sampler_source
            def baseline_prediction(self,x,sigma,model_options=None,seed=None):
                return x*0.25 + run_blocks(baseline_state,baseline_patches,sigmas=sigmas).mean()*0.001
            baseline_guider.predict_noise=types.MethodType(baseline_prediction,baseline_guider)
            baseline_chosen=[]
            with cpu_attention():
                baseline=sampler.sample(baseline_guider,sigmas,{'seed':123,'model_options':baseline_options},
                    lambda i,y,x,total:baseline_chosen.append(y.clone()),noise,latent,disable_pbar=True)
            assert len(baseline_chosen)==20 and baseline_state.audit['completed_forward_calls']==20
            baselines[tag]=(baseline,baseline_chosen)
        cases = [('native_after','native_observer','probe_first',False),
                 ('native_before','native_observer','readout_first',True),
                 ('off_after','off','probe_first',False),
                 ('off_before','off','readout_first',True),
                 ('fixed_after','fixed','probe_first',False),
                 ('fixed_before','fixed','readout_first',True)]
        for name, policy, order, nested_cb in cases:
            expected_mask = [] if policy == 'off' else EXPECTED
            expected_nfe = 20 + len(expected_mask)
            baseline, baseline_chosen = baselines['native' if policy == 'off' else 'variable']
            def install_probe(patcher):
                return H3NativeObserverRouter().apply(patcher,positive,policy,
                    ','.join(map(str,EXPECTED)) if policy=='fixed' else '',name,str(temp/'probe'))[0]
            def install_readout(patcher):
                return H3X0Readout().apply(patcher,name,str(temp/'x0'),1312,736,141)[0]
            patched = install_readout(install_probe(base)) if order=='probe_first' else install_probe(install_readout(base))
            sampled = patched.clone()
            state=sampled.get_wrappers(WrappersMP.SAMPLER_SAMPLE,KEY)[0].state
            assert sampled.get_wrappers(WrappersMP.PREDICT_NOISE,KEY)[0].state is state
            assert patched.get_wrappers(WrappersMP.SAMPLER_SAMPLE,KEY)[0].state is state
            patches=sampled.model_options['transformer_options']['patches_replace']['dit']
            assert all(p.state is state for p in patches.values())
            try: install_probe(sampled)
            except ValueError as error: assert 'already registered' in str(error)
            else: raise AssertionError('duplicate wrapper accepted')
            state.plan_for=lambda _:tiny_plan
            state.observer=PhysicalObservations(state, [None] if policy=='fixed' else LAGS, full_lag=-24)
            guider,options=setup_guider(sampled)
            bound=condition_signature(guider)  # real H3 extra_conds tree, not plain toy condition.
            def prediction(self,x,sigma,model_options=None,seed=None):
                return x*0.25 + run_blocks(state,patches,sigmas=sigmas).mean()*0.001
            guider.predict_noise=types.MethodType(prediction,guider)
            callbacks=[]
            callback_ids={}
            def callback(i,y,x,total):
                callbacks.append(i)
                callback_ids[i]=(id(y),id(x),total)
                packed_y=torch.cat([v.reshape(1,1,-1) for v in y.unbind()],dim=-1) if y.is_nested else y
                assert torch.equal(packed_y,baseline_chosen[i]), ('chosen mismatch',i)
            def original(model_wrap,grid,extra_args,cb,noise,latent_image,mask,disable):
                def delivered(i,y,x,total):
                    if nested_cb:
                        y=NestedTensor(unpack_latents(y,shapes));x=NestedTensor(unpack_latents(x,shapes))
                    before=(id(y),id(x),total)
                    returned=cb(i,y,x,total)
                    assert callback_ids[i]==before
                    return returned
                return sampler.sample(model_wrap,grid,extra_args,delivered,noise,latent_image,mask,disable)
            wrappers=get_all_wrappers(WrappersMP.SAMPLER_SAMPLE,options,is_model_options=True)
            executor=WrapperExecutor.new_class_executor(original,sampler,wrappers)
            before_rng=torch.random.get_rng_state().clone(); before_env=dict(os.environ)
            before_noise=noise.clone();before_reference=reference.clone()
            with cpu_attention():
                result=executor.execute(guider,sigmas,{'seed':123,'model_options':options},callback,noise,latent,None,True)
            assert torch.equal(result,baseline)
            assert callbacks==list(range(20))
            assert state.audit['completed_forward_calls']==expected_nfe and state.audit['completed_calls']==50*expected_nfe
            assert state.audit['routed_calls']==50*len(expected_mask) and state.full_indices==expected_mask
            assert condition_signature(guider)==bound
            assert torch.equal(before_rng,torch.random.get_rng_state()) and dict(os.environ)==before_env
            assert torch.equal(noise,before_noise) and torch.equal(reference,before_reference)
            manifest=json.loads((temp/'x0'/name/'manifest.json').read_text())
            assert manifest['status']=='complete' and manifest['callback_count']==20
            for row in state.audit['counterfactual']['inputs']:
                item=torch.load(row['file'],weights_only=True)
                assert readout.tensor_signature(item['packed']) == row['packed_signature']
                assert item['metadata']['full_grid']==sigmas.double().tolist()
            rows.append({'case':name,'wrapper_order':order,'nested_callback':nested_cb,
                         'all20_chosen_and_final_equal_singleforward_expected_mask':True,
                         'policy':policy,'expected_mask':expected_mask,'actual_mask':state.full_indices,
                         'NFE':expected_nfe,'callbacks':20,'callback_arguments_unchanged':True,
                         'real_processed_condition_signature_passed':True,
                         'condition_hash_seconds':sum(v['condition_copy_hash_seconds'] for v in state.audit['counterfactual']['branches']),
                         'archive_readout_seconds':sum(v['archive_and_readout_seconds'] for v in state.audit['counterfactual']['branches'])})
    assert not torch.cuda.is_initialized()
    print('H3_NATIVE_OBSERVER_CPU_SMOKE='+json.dumps({'success':True,'device':'cpu','CUDA_initialized':False,
        'actual_node_loader_module_alias_tested':True,'real_H3_extra_conds_tested':True,
        'real_local_generator_helpers_tested':True,'real_PDD_grid_lookup_tested':True,
        'core_sha256':hashlib.sha256((root/'extensions/H3NativeObserverRouter/core.py').read_bytes()).hexdigest(),
        'both_wrapper_orders_all_policies':True,'off_exact_native':True,
        'Full_observer_does_not_choose_branch':True,'index5_passive_first_choice_false':True,
        'index19_can_trigger':True,'cases':rows}))

if __name__=='__main__': main()
