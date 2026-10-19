"""One bounded actual-Comfy CPU Euler transaction case; synthetic predictions only."""
import argparse
import asyncio
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import types
from unittest.mock import patch


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--core', required=True)
    p.add_argument('--case', choices=('off', 'restart'), required=True)
    args = p.parse_args()
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise ValueError('CUDA must be hidden before torch import')
    started = time.monotonic()
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root/'scripts'), str(root/'extensions'), args.core,
                   str(Path(args.core).parent/'runtime_deps')]
    sys.argv = ['r50-cpu-transaction', '--cpu', '--disable-dynamic-vram', '--use-pytorch-cross-attention']
    import torch
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    import comfy.options
    comfy.options.enable_args_parsing()
    from compatibility_bootstrap import install, install_video_compat
    install(); install_video_compat()
    import nodes
    sampler_path = Path(args.core)/'comfy_extras/nodes_custom_sampler.py'
    assert asyncio.run(nodes.load_custom_node(str(sampler_path), module_parent='comfy_extras'))
    from comfy.model_base import MiniMaxH3, ModelType, model_sampling
    from comfy.latent_formats import MiniMaxH3Video
    from comfy.model_patcher import ModelPatcher, create_model_options_clone
    from comfy.patcher_extension import WrapperExecutor, WrappersMP, merge_nested_dicts, get_all_wrappers
    from comfy.samplers import KSAMPLER
    from comfy.k_diffusion.sampling import sample_euler
    from comfy.nested_tensor import NestedTensor
    from comfy.utils import unpack_latents
    import comfy.sample
    import comfy.ldm.minimax.model as h3
    from H3AutomaticWindowRouter import H3AutomaticWindowRouter
    from H3AutomaticWindowRouter.core import KEY, condition_signature
    from H3AutomaticWindowRouter.geometry import FLEXIACT as g
    from H3AutomaticWindowRouter.selector import Controller
    from H3AutomaticWindowRouter.dynamic_support import make_gain
    from H3AutomaticWindowRouter.dependencies import router
    import H3AutomaticWindowRouter.core as control_core
    from H3X0Readout import H3X0Readout

    cases = json.loads((root/'configs/protocol.json').read_text())['cases']
    case = cases[0 if args.case == 'off' else 1]
    run, seed = case['run_id'], case['seed']
    graph = json.loads((root/'configs/parent_graphs'/f"{case['parent_run']}.json").read_text())
    assert graph['7']['class_type'] == 'BasicGuider' and graph['6']['inputs']['noise_seed'] == seed
    sigmas = torch.tensor([float(x) for x in graph['9']['inputs']['sigmas'].split(',')])
    model = MiniMaxH3.__new__(MiniMaxH3); torch.nn.Module.__init__(model)
    diffusion = h3.MiniMaxH3Model.__new__(h3.MiniMaxH3Model); torch.nn.Module.__init__(diffusion)
    diffusion.patch_size=(1,2,2); diffusion.latents_dim=24
    diffusion.blocks=torch.nn.ModuleList(torch.nn.Identity() for _ in range(50))
    diffusion.dtype=torch.float32; diffusion.hidden_size=8
    model.diffusion_model=diffusion; model.model_sampling=model_sampling(None,ModelType.FLOW_AV)
    model.model_sampling.set_parameters(shift=12,audio_shift=3)
    model.latent_format=MiniMaxH3Video(); model.latent_shapes=list(g.stream_shapes)
    model.manual_cast_dtype=torch.float32; model.concat_keys=()
    base=ModelPatcher(model,torch.device('cpu'),torch.device('cpu'),size=1)
    reference=torch.zeros(g.stream_shapes[0])
    positive=[[torch.zeros((1,2,8)),{'minimax_refs':[
        {'kind':'image','latent':torch.zeros((1,24,1,2,2)),'latent_h':2,'latent_w':2},
        {'kind':'video','latent':reference,'latent_t':47,'latent_h':48,'latent_w':72,'ref_audio_t':0}]}]]
    native_noise=comfy.sample.prepare_noise(NestedTensor([torch.zeros(s) for s in g.stream_shapes]),seed)
    noise=torch.cat([v.reshape(1,1,-1) for v in native_noise.unbind()],dim=-1)
    latent=torch.zeros_like(noise)
    processed=model.extra_conds(cross_attn=positive[0][0],device=torch.device('cpu'),latent_shapes=list(g.stream_shapes),
        minimax_refs=positive[0][1]['minimax_refs'],noise=noise,seed=seed)
    assert type(processed['minimax_payload'].cond['layout']).__name__=='PackedLayout'
    actual_layout=processed['minimax_payload'].cond['layout']
    assert actual_layout.signature[1:]==(47,48,72,263)
    sampler=KSAMPLER(sample_euler)
    n=g.latent_bins
    q=torch.arange(4*n,dtype=torch.float32).reshape(1,1,2*n,2)/100
    k=q.flip(-2).contiguous(); v=torch.sin(q*3)
    tiny_plan={'seq_len':2*n,'frame_rows':1,'latent_interval_half_open':[0,n],
               'query_interval_half_open':[n,2*n],'reference_video_segment':[0,n]}
    def dense(q,k,v):
        z=q@k.transpose(-1,-2)/math.sqrt(q.shape[-1]); return z.softmax(-1)@v,z.logsumexp(-1)
    route_original=router.route_attention
    @contextmanager
    def cpu_attention():
        with patch.object(router,'route_attention',lambda *a,**kw:route_original(*a,**kw,attention=dense)):
            yield
    def measure(index):
        present=args.case=='restart' and (index in (0,1,2,4,5) or index>=6)
        window=[0,15] if index<=2 else ([50,65] if index<=5 else [115,146])
        comparison={str(c):{'proposal_lag':5,'null_comparisons':[
            {'proposal_cost':.1,'null_cost':.5} for _ in range(5)]} for c in (.3,.5)}
        rows=[{'window':window,'feature':'arm_direction','status':'measured','baseline':'delayed_candidate',
               'min_gain':.8,'comparison':comparison}] if present else []
        return {'status':'complete','observer':{'schema':'r27-whole-timeline-observation-v1',
                'physical_index':index,'status':'measured','windows':rows,'observation_domain':g.domain_record}}
    controller=Controller(g); decisions=[controller.select(i,measure(i)) for i in range(20)]
    expected=[i for i,d in enumerate(decisions) if d['chosen_full']]
    assert expected==([] if args.case=='off' else [1,2,5]+list(range(7,20)))
    def setup(patcher):
        guider=nodes.NODE_CLASS_MAPPINGS['BasicGuider'].execute(model=patcher,conditioning=positive)[0]
        guider.inner_model=model
        guider.conds={'positive':[dict(guider.original_conds['positive'][0],model_conds=processed)]}
        options=create_model_options_clone(guider.model_options)
        merge_nested_dicts(options['transformer_options'].setdefault('wrappers',{}),patcher.wrappers,copy_dict1=False)
        options['transformer_options']['sample_sigmas']=sigmas; guider.model_options=options
        return guider,options
    print('STAGE independent_single_prediction_Euler',args.case,flush=True)
    baseline_guider,baseline_options=setup(base)
    baseline_calls=[]; baseline_chosen=[]
    def baseline_prediction(self,x,sigma,model_options=None,seed=None):
        index=len(baseline_calls); baseline_calls.append(index)
        out=route_original(q,k,v,1,tiny_plan,mode='mass_preserve',
            query_gain=make_gain(decisions[index]['latent_bins'],(1,1),geometry=g),attention=dense)
        return x*.25+out.mean()*.001
    baseline_guider.predict_noise=types.MethodType(baseline_prediction,baseline_guider)
    with torch.inference_mode():
        baseline=sampler.sample(baseline_guider,sigmas,{'seed':seed,'model_options':baseline_options},
            lambda i,x0,x,total:baseline_chosen.append(x0.clone()),noise,latent,disable_pbar=True)
    assert baseline_calls==list(range(20)) and len(baseline_chosen)==20
    print('STAGE Native_optionalFull_Euler',args.case,flush=True)
    with tempfile.TemporaryDirectory(prefix='r50-transaction-') as tmp:
        temp=Path(tmp)
        patched=H3AutomaticWindowRouter().apply(base,positive,run,str(temp/'counterfactual'))[0]
        patched=H3X0Readout().apply(patched,run,str(temp/'x0'),g.width,g.height,g.frames)[0]
        sampled=patched.clone(); state=sampled.get_wrappers(WrappersMP.SAMPLER_SAMPLE,KEY)[0].state
        state.plan_for=lambda _:tiny_plan
        state.observer=lambda video: {'accepted':False,'best':None,'rejection_reasons':['CPU_fixture']}
        observations=[]
        def observer(s,row):
            assert row['branch']=='native' and len(s.transaction['branches'])==1
            observations.append(row['physical_index']);return measure(row['physical_index'])
        state.live_observer=observer
        class PendingHistoricalFixture:
            # No R49 parent results exist yet; this is explicitly not a pairing certificate.
            def begin(self,*a): pass
            def branch(self,*a): pass
            def decision(self,*a): pass
            def finish(self,*a): pass
        state.pair_gate=PendingHistoricalFixture()
        patches=sampled.model_options['transformer_options']['patches_replace']['dit']
        guider,options=setup(sampled); condition=condition_signature(guider)
        def blocks():
            result=None; marker=object()
            def attention_pytorch(*a,**kw):raise AssertionError('must intercept native attention')
            def original(a):
                nonlocal result
                override=a['transformer_options']['optimized_attention_override']
                result=override(attention_pytorch,q,k,v,1,skip_reshape=True)
                return {'img':result}
            for block in range(50):
                opts={'block_index':block,'minimax_h3_layout':marker,'sample_sigmas':sigmas}
                patches[('double_block',block)]({'layout':marker,'transformer_options':opts},{'original_block':original})
            return result
        def prediction(self,x,sigma,model_options=None,seed=None): return x*.25+blocks().mean()*.001
        guider.predict_noise=types.MethodType(prediction,guider)
        callbacks=[]
        def callback(i,x0,x,total):
            assert total==20 and torch.equal(x0,baseline_chosen[i]);callbacks.append(i)
        wrappers=get_all_wrappers(WrappersMP.SAMPLER_SAMPLE,options,is_model_options=True)
        executor=WrapperExecutor.new_class_executor(sampler.sample,sampler,wrappers)
        rng=torch.get_rng_state().clone(); env=dict(os.environ); oldnoise=noise.clone(); oldref=reference.clone()
        oldqkv=[z.clone() for z in (q,k,v)]
        with torch.inference_mode(),cpu_attention(),patch.object(control_core,'make_gain',lambda bins,geometry:make_gain(bins,(1,1),geometry=geometry)):
            result=executor.execute(guider,sigmas,{'seed':seed,'model_options':options},callback,noise,latent,None,True)
        assert torch.equal(result,baseline) and callbacks==observations==list(range(20))
        assert state.full_indices==expected and state.audit['completed_forward_calls']==20+len(expected)
        assert state.audit['completed_calls']==50*(20+len(expected)) and state.audit['routed_calls']==50*len(expected)
        assert condition_signature(guider)==condition and torch.equal(rng,torch.get_rng_state()) and dict(os.environ)==env
        assert torch.equal(oldnoise,noise) and torch.equal(oldref,reference)
        assert all(torch.equal(a,b) for a,b in zip(oldqkv,(q,k,v)))
        assert not base.get_wrappers(WrappersMP.SAMPLER_SAMPLE,KEY)
        cap=json.loads((temp/'x0'/run/'manifest.json').read_text())
        assert cap['status']=='complete' and cap['callback_count']==20 and cap['geometry']==g.video_geometry
        assert [c['step_zero_based'] for c in cap['captures']]==list(range(20))
        assert len(list((temp/'x0'/run).glob('*.pt')))==21
        for step in state.audit['counterfactual']['steps']:
            assert step['decision']['latent_bins']==decisions[step['physical_index']]['latent_bins']
        archive_bytes=sum(p.stat().st_size for p in temp.rglob('*') if p.is_file())
        report={'status':'PASS','case':args.case,'geometry':g.video_geometry,'valid_frames':147,
                'DiT_synthetic_calls':20+len(expected),'real_model_DiT_NFE':0,'Euler_updates':20,'callbacks':20,
                'blocks':50*(20+len(expected)),'routes':50*len(expected),'observations':20,'chosen_capture_files':21,
                'active_indices':expected,'actual_Comfy_Euler_and_wrapper':True,'all20_chosen_and_final_equal_independent_Euler':True,
                'same_input_branches':True,'QKV_noise_reference_RNG_unchanged':True,'CPU_processed_condition_tree_guard':True,
                'actual_R49_parent_pairing':'PENDING_NOT_TESTED','observer':'synthetic rows; no VAE/pose execution',
                'attention_geometry':'47bins tiny1row_per_bin; actual full layout covered separately',
                'temporary_archive_bytes':archive_bytes,
                'chosen20_capture_seconds':sum(row['capture_seconds'] for row in cap['captures']),
                'branch_archive_seconds':sum(row['archive_and_readout_seconds'] for row in state.audit['counterfactual']['branches']),
                'input_archive_seconds':sum(row['archive_seconds'] for row in state.audit['counterfactual']['inputs']),
                'final_archive_cost':'included in total wall time; not separately instrumented',
                'CUDA_initialized':torch.cuda.is_initialized(),'wall_seconds':time.monotonic()-started}
    assert not torch.cuda.is_initialized()
    print('R50_TRANSACTION_CPU='+json.dumps(report,allow_nan=False))


if __name__=='__main__':main()
