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
    parser.add_argument("--case", choices=[t+"_"+o for t in ("off","restart","always") for o in ("probe_first","readout_first")])
    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    import torch
    torch.set_num_threads(1)
    if torch.cuda.is_initialized():
        raise RuntimeError("CUDA must remain uninitialized")
    import faulthandler
    faulthandler.dump_traceback_later(25,repeat=True)
    print("STAGE imports",flush=True)
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "extensions"))
    sys.path.insert(0, str(root / "scripts"))
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
    from H3AutomaticWindowRouter import H3AutomaticWindowRouter
    from H3AutomaticWindowRouter.core import KEY, condition_signature, readout
    from H3AutomaticWindowRouter.dependencies import router
    from H3X0Readout import H3X0Readout
    from counterfactual_support import PhysicalObservations, cpu_attention, run_blocks, dense_attention
    from pose_test_support import TAGS, OfflineObserver, NoHistoricalGate, measurement
    from H3AutomaticWindowRouter.selector import Controller
    from H3AutomaticWindowRouter.dynamic_support import make_gain
    import H3AutomaticWindowRouter.core as control_core
    from unittest.mock import patch

    # Reproduce production node loading rather than only canonical imports.
    # nodes.load_custom_node uses an absolute-path module name for .py files,
    # creating a second Guider_Basic class object from the same official source.
    import nodes
    sampler_source = Path(args.comfy_root).resolve() / "comfy_extras/nodes_custom_sampler.py"
    if not asyncio.run(nodes.load_custom_node(str(sampler_source), module_parent="comfy_extras")):
        raise RuntimeError("actual Comfy node loader failed")
    graph = json.loads((root / 'configs/r44_source28289_seed2026101701_auto.json').read_text())
    graph_guider_type = graph["7"]["class_type"]
    assert graph_guider_type == "BasicGuider"
    graph_guider_node = nodes.NODE_CLASS_MAPPINGS[graph_guider_type]

    import H3EventAudit as aux
    # Actual graph paths/defaults, no writes outside this isolated CPU stage.
    with patch.object(Path,'mkdir',lambda *args,**kwargs:None):
        for key,cls in (('5',aux.H3EventAuditReference),('6',aux.H3EventAuditNoise)):
            expected=graph[key]['inputs']['audit_dir']
            assert aux.audit_root(expected)==Path(expected).resolve()
            assert cls.INPUT_TYPES()['required']['audit_dir'][1]['default']==expected
        for bad in ('relative','/tmp/outside','/data5/researcher/h3_runs/timing_spatial_r3_20261016/audit'):
            try:aux.audit_root(bad)
            except ValueError:pass
            else:raise AssertionError('aux root escape')

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


    print("STAGE model_setup",flush=True)
    processed = model.extra_conds(cross_attn=positive[0][0], device=torch.device('cpu'),
        latent_shapes=list(shapes), minimax_refs=positive[0][1]['minimax_refs'],
        noise=noise, seed=123)
    assert type(processed['minimax_payload']).__name__ == 'CONDConstant'
    assert type(processed['minimax_payload'].cond['layout']).__name__ == 'PackedLayout'
    assert type(processed['c_crossattn']).__name__ == 'CONDRegular'
    tiny_plan = {'seq_len':84,'frame_rows':1,'latent_interval_half_open':[0,42],
                 'query_interval_half_open':[42,84],'reference_video_segment':[0,42]}

    def setup_guider(patcher):
        guider = graph_guider(patcher)
        guider.inner_model = model
        guider.conds = {'positive': [dict(guider.original_conds['positive'][0], model_conds=processed)]}
        options = create_model_options_clone(guider.model_options)
        merge_nested_dicts(options['transformer_options'].setdefault('wrappers', {}), patcher.wrappers, copy_dict1=False)
        options['transformer_options']['sample_sigmas'] = sigmas
        guider.model_options = options
        return guider, options

    # Use official Guider_Basic original_conds, not a guessed plain-dict schema.
    from H3AutomaticWindowRouter.pair_gate import compare_embedding_tensors
    official=graph_guider(base).original_conds['positive']
    assert len(official)==1 and torch.equal(official[0]['cross_attn'],positive[0][0])
    expected_embedding=readout.tensor_signature(positive[0][0]);expected_embedding.pop('bytes')
    compare_embedding_tensors(official[0]['cross_attn'],positive[0][0].clone(),expected_embedding)
    try: compare_embedding_tensors(official[0]['cross_attn']+1,positive[0][0].clone(),expected_embedding)
    except ValueError: pass
    else: raise AssertionError('different actual embedding accepted')

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
    rows = []
    with tempfile.TemporaryDirectory(prefix='h3-counterfactual-cpu-') as temporary:
        temp = Path(temporary)
        # Same actual Euler, one model prediction per step, independently prescribed masks.
        # Both actual run IDs create independent states from the same cached ModelPatcher.
        cached_states=[]
        for cache_attempt,actual_run in enumerate(('r44_source28289_seed2026101701_auto','r44_source28289_seed2026101701_auto')):
            cached=H3AutomaticWindowRouter().apply(base,positive,actual_run,str(temp/('cached_states_'+str(cache_attempt))))[0]
            cs=cached.get_wrappers(WrappersMP.SAMPLER_SAMPLE,KEY)[0].state
            assert cs.callback_count==0 and cs.forward_index==-1 and not cs.entered
            cached_states.append(cs)
        assert cached_states[0] is not cached_states[1]
        assert not base.get_wrappers(WrappersMP.SAMPLER_SAMPLE,KEY)
        assert not base.model_options.get('transformer_options',{}).get('patches_replace',{}).get('dit')
        # Actual native cold noise may advance global CPU RNG; compare its exact native behavior.
        # Cache hits must preserve the post-cold state and return independent copies.
        noise_values=[]
        for case_seed in (2026101701,):
            provider=aux.CachedNoise(case_seed,temp,'noise_'+str(case_seed),'cache_'+str(case_seed))
            target={'samples':NestedTensor([torch.zeros(shape) for shape in shapes])}
            oldrng=torch.random.get_rng_state().clone()
            import comfy.sample
            native_noise=comfy.sample.prepare_noise(target['samples'],case_seed)
            native_rng=torch.random.get_rng_state().clone();torch.random.set_rng_state(oldrng)
            cold=provider.generate_noise(target);cold_rng=torch.random.get_rng_state().clone()
            assert torch.equal(native_rng,cold_rng)
            assert all(torch.equal(a,b) for a,b in zip(cold.unbind(),native_noise.unbind()))
            hit=provider.generate_noise(target)
            assert torch.equal(cold_rng,torch.random.get_rng_state())
            historical=json.loads((root/'configs'/'parent_noise.json').read_text())
            assert [aux.tensor_info(v)[0] for v in cold.unbind()]==historical['actual_noise_streams']
            assert all(torch.equal(a,b) and a.data_ptr()!=b.data_ptr() for a,b in zip(cold.unbind(),hit.unbind()))
            noise_values.append(cold)
        assert len(noise_values)==1
        print("STAGE baselines",flush=True)
        baselines = {}
        chosen_tags=TAGS if args.case is None else (args.case.split('_')[0],)
        plans={}
        for tag in chosen_tags:
            controller=Controller();plans[tag]=[controller.select(i,measurement(tag,i)) for i in range(20)]
        for tag in chosen_tags:
            print("STAGE baseline",tag,flush=True)
            mask=[i for i,d in enumerate(plans[tag]) if d['chosen_full']]
            baseline_state = router.RouterState({'refs':[]},'mass_preserve',1.0,0,0,50,65,0,50,6,20,'reference_'+tag,str(temp))
            baseline_state.plan_for = lambda _: tiny_plan
            baseline_state.selected = lambda block: baseline_state.forward_index in mask and 0 <= block < 50
            baseline_patches = {('double_block',i):router.EventBlockPatch(baseline_state,i) for i in range(50)}
            baseline_guider, baseline_options = setup_guider(base)
            assert type(baseline_guider) is not Guider_Basic
            assert Path(sys.modules[type(baseline_guider).__module__].__file__).resolve() == sampler_source
            def baseline_prediction(self,x,sigma,model_options=None,seed=None):
                n=baseline_state.forward_index+1
                baseline_state.query_gain=make_gain(plans[tag][n]['latent_bins'],(1,1))
                return x*0.25 + run_blocks(baseline_state,baseline_patches,sigmas=sigmas).mean()*0.001
            baseline_guider.predict_noise=types.MethodType(baseline_prediction,baseline_guider)
            baseline_chosen=[]
            with cpu_attention():
                baseline=sampler.sample(baseline_guider,sigmas,{'seed':123,'model_options':baseline_options},
                    lambda i,y,x,total:baseline_chosen.append(y.clone()),noise,latent,disable_pbar=True)
            assert len(baseline_chosen)==20 and baseline_state.audit['completed_forward_calls']==20
            baselines[tag]=(baseline,baseline_chosen)
        cases = [(tag+'_'+order, tag, order, order=='readout_first') for tag in TAGS for order in ('probe_first','readout_first')]
        if args.case is not None:cases=[v for v in cases if v[0]==args.case]
        for name, tag, order, nested_cb in cases:
            print("STAGE wrapper",name,flush=True)
            policy='automatic_windows'
            expected_mask=[i for i,d in enumerate(plans[tag]) if d['chosen_full']]
            expected_nfe=20+len(expected_mask)
            baseline,baseline_chosen=baselines[tag]
            def install_probe(patcher):
                return H3AutomaticWindowRouter().apply(patcher,positive,name,str(temp/'probe'))[0]
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
            state.observer=PhysicalObservations(state, [None], full_lag=-24)
            state.live_observer=OfflineObserver(tag)
            state.pair_gate=NoHistoricalGate()
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
            with cpu_attention(), patch.object(control_core,'make_gain',lambda bins:make_gain(bins,(1,1))):
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
            assert [v['step_zero_based'] for v in manifest['captures']]==list(range(20))
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
    faulthandler.cancel_dump_traceback_later()
    assert not torch.cuda.is_initialized()
    print('H3_POSE_OBSERVER_CPU_SMOKE='+json.dumps({'success':True,'device':'cpu','CUDA_initialized':False,
        'actual_node_loader_module_alias_tested':True,'real_H3_extra_conds_tested':True,'official_original_conds_clean_embedding_adapter_tested':True,
        'real_local_generator_helpers_tested':True,'full_grid_preserved':True,
        'core_sha256':hashlib.sha256((root/'extensions/H3AutomaticWindowRouter/core.py').read_bytes()).hexdigest(),
        'case_filter':args.case,'cached_base_same_new_run_repeated_fresh_state':True,'actual_seed1701_noise_cold_hit_pass':True,'cold_noise_native_rng_and_archived_AV_hashes_equal':True,'cache_hits_rng_unchanged':True,'automatic_union_replay_matches_singleforward_masks':True,
        'Full_observer_does_not_choose_branch':True,'index0_observed_and_no_forced_prefix':True,
        'index19_can_trigger':True,'cases':rows}))

if __name__=='__main__': main()
