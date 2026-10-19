"""Real Comfy node loader/clone/Euler/readout with CPU synthetic DiT QKV.

No weights are loaded. The true reference fixture and full source geometry pass
the new node; tiny QKV/plan replace expensive DiT execution after that gate.
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
import time
import types
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfy-root", required=True)
    parser.add_argument("--compat-bootstrap", required=True)
    parser.add_argument("--reference", required=True, help="Existing R3 clean reference tensor .pt")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    started = time.monotonic()
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    assert not torch.cuda.is_initialized()
    sys.path.insert(0, str(root/"tests"))
    sys.path.insert(0, args.comfy_root)
    sys.argv = ["local_route_cpu_smoke", "--cpu", "--disable-dynamic-vram", "--use-pytorch-cross-attention"]
    import comfy.options
    comfy.options.enable_args_parsing()
    spec = importlib.util.spec_from_file_location("local_route_existing_compat", args.compat_bootstrap)
    compat = importlib.util.module_from_spec(spec); spec.loader.exec_module(compat)
    compat.install(); compat.install_video_compat()
    import nodes
    for path, parent in [(Path(args.comfy_root)/"comfy_extras/nodes_custom_sampler.py", "comfy_extras"),
                         *[(root/"extensions"/name,"custom_nodes") for name in
                           ("H3TemporalRouter", "H3LocalTemporalRouter", "H3X0Readout", "H3EventAudit", "H3PairAudit")]]:
        assert asyncio.run(nodes.load_custom_node(str(path), module_parent=parent))
    Node = nodes.NODE_CLASS_MAPPINGS["H3LocalTemporalRouter"]
    FullNode = nodes.NODE_CLASS_MAPPINGS["H3TemporalRouter"]
    Readout = nodes.NODE_CLASS_MAPPINGS["H3X0Readout"]
    local_core = sys.modules[Node.__module__+".core"]
    local_mask = sys.modules[Node.__module__+".mask"]
    full_core = sys.modules[FullNode.__module__+".core"]
    from comfy.model_base import MiniMaxH3, ModelType, model_sampling
    from comfy.latent_formats import MiniMaxH3Video
    from comfy.model_patcher import ModelPatcher, create_model_options_clone
    from comfy.patcher_extension import WrapperExecutor, WrappersMP, merge_nested_dicts, get_all_wrappers
    from comfy.samplers import KSAMPLER
    from comfy.k_diffusion.sampling import sample_euler
    from comfy.nested_tensor import NestedTensor
    from comfy.utils import unpack_latents
    import comfy.ldm.minimax.model as h3

    model = MiniMaxH3.__new__(MiniMaxH3); torch.nn.Module.__init__(model)
    diffusion = h3.MiniMaxH3Model.__new__(h3.MiniMaxH3Model); torch.nn.Module.__init__(diffusion)
    diffusion.patch_size=(1,2,2); diffusion.latents_dim=24
    diffusion.blocks=torch.nn.ModuleList(torch.nn.Identity() for _ in range(50))
    diffusion.dtype=torch.float32; diffusion.hidden_size=8
    model.diffusion_model=diffusion
    model.model_sampling=model_sampling(None,ModelType.FLOW_AV)
    model.model_sampling.set_parameters(shift=12,audio_shift=3)
    model.latent_format=MiniMaxH3Video()
    shapes=((1,24,42,46,82),(1,32,2,235)); model.latent_shapes=list(shapes)
    model.manual_cast_dtype=torch.float32;model.concat_keys=()
    base=ModelPatcher(model,torch.device('cpu'),torch.device('cpu'),size=1)
    reference=torch.load(args.reference,map_location='cpu',weights_only=True,mmap=True)
    assert isinstance(reference,torch.Tensor) and tuple(reference.shape)==shapes[0]
    assert hashlib.sha256(reference.contiguous().view(torch.uint8).numpy()).hexdigest()=="75140c3ce5f144cdce940b6cd84a56dc40c9a94f15fdc917e6ad712ba9e94734"
    positive=[[torch.zeros((1,2,8)),{'minimax_refs':[
        {'kind':'image','latent':torch.zeros((1,24,1,2,2)),'latent_h':2,'latent_w':2},
        {'kind':'video','latent':reference,'latent_t':42,'latent_h':46,'latent_w':82,'ref_audio_t':0}]}]]
    graph=json.loads((root/'configs/r16_s05_roi_6to14.json').read_text())
    # Actual graph auxiliary nodes, actual native preprocessing/metadata on small
    # CPU arrays. Only VAE and text encoder numerics are stand-ins; no weights.
    Event=nodes.NODE_CLASS_MAPPINGS['H3EventAuditReference']
    Noise=nodes.NODE_CLASS_MAPPINGS['H3EventAuditNoise']
    Pair=nodes.NODE_CLASS_MAPPINGS['H3PairConditionSnapshot']
    audit_module=sys.modules[Event.__module__]
    audit_dir=graph['5']['inputs']['audit_dir']
    assert graph['6']['inputs']['audit_dir']==audit_dir
    assert Event.INPUT_TYPES()['required']['audit_dir'][1]['default']==audit_dir
    assert Noise.INPUT_TYPES()['required']['audit_dir'][1]['default']==audit_dir
    for bad in ('relative','/tmp/outside','/data5/researcher/h3_runs/timing_spatial_r3_20261016/audit'):
        try:audit_module.audit_root(bad)
        except ValueError:pass
        else:raise AssertionError('auxiliary path escape accepted')
    class FakeVAE:
        def encode(self,frames):
            return torch.zeros((1,24,1 if len(frames)==1 else 2,frames.shape[1]//16,frames.shape[2]//16))
    class FakeClip:
        def tokenize(self,prompt,**kwargs):return {'tokens':torch.zeros((1,2),dtype=torch.long)}
        def encode_from_tokens_scheduled(self,tokens):
            return [[torch.zeros((1,2,8)),{'minimax_token_tags':torch.zeros((1,2),dtype=torch.long)}]]
    with tempfile.TemporaryDirectory(prefix='local_route_cpu_aux_',dir=audit_module.audit_root(audit_dir)) as aux:
        frames=torch.arange(5*32*32*3).reshape(5,32,32,3).float()/(5*32*32*3)
        cond,target,prepared,ref_latent=Event().encode(FakeClip(),FakeVAE(),frames,'CPU interface',32,32,5,
            aux,'shared',2,0,frames[:1])
        # The official Lanczos path round-trips through PIL uint8 even at the
        # same size (comfy/utils.py1095..1103). Geometry is preserved, floating
        # RGB values are quantized. Validate that exact transformation.
        import numpy as np
        expected_rgb=torch.from_numpy(np.clip(255.*frames.numpy(),0,255).astype(np.uint8).astype(np.float32)/255.)
        assert prepared.shape==frames.shape and torch.equal(prepared,expected_rgb)
        assert not torch.equal(prepared,frames)
        assert float((prepared-frames).abs().max())<=1/255.+1e-7
        assert ref_latent['samples'] is cond[0][1]['minimax_refs'][1]['latent']
        pair_cond,pair_target=Pair().snapshot(cond,target,aux,'shared','paired')
        assert pair_cond is cond and pair_target is target
        n=Noise().get_noise(2026101311,aux,'noise_one','paired')[0]
        first=n.generate_noise(target);second=n.generate_noise(target)
        assert all(torch.equal(a,b) for a,b in zip(first.unbind(),second.unbind()))
        assert json.loads((Path(aux)/'paired_conditioning.json').read_text())['pair_snapshot']['verified']
    sigmas=torch.tensor([float(s) for s in graph['9']['inputs']['sigmas'].split(',')])
    assert len(sigmas)==21 and graph['7']['class_type']=='BasicGuider'
    count=sum(torch.Size(s).numel() for s in shapes)
    noise=torch.arange(count,dtype=torch.float32).reshape(1,1,-1)/count
    latent=torch.zeros_like(noise);sampler=KSAMPLER(sample_euler)
    q=torch.arange(168,dtype=torch.float32).reshape(1,1,84,2)/100
    k=q.flip(-2).contiguous();v=torch.sin(q*3)
    def dense(q,k,v):
        score=q@k.transpose(-1,-2)/q.shape[-1]**.5
        return score.softmax(-1)@v,score.logsumexp(-1)
    native_value=dense(q,k,v)[0].mean()
    tiny_plan={'seq_len':84,'frame_rows':1,'latent_interval_half_open':[14,20],
               'query_interval_half_open':[56,62],'reference_video_segment':[0,42]}
    layout=object()

    # Real H3 patchifier establishes row-major time,row,column and 2x2 geometry.
    marks=(torch.arange(42).view(42,1,1)*100000 + torch.arange(46).view(1,46,1)*100
           + torch.arange(82).view(1,1,82)).float()[None,None]
    patches=h3.patchify_video(marks)
    for t,r,c in [(0,0,0),(14,9,21),(19,22,40),(41,22,40)]:
        row=t*943+r*41+c
        expected=torch.tensor([t*100000+(2*r+dr)*100+2*c+dc for dr in (0,1) for dc in (0,1)],dtype=torch.float32)
        assert torch.equal(patches[row],expected)
    assert torch.equal(h3.unpatchify_video(patches,42,23,41,c=1),marks)

    def guider(patcher):
        g=nodes.NODE_CLASS_MAPPINGS['BasicGuider'].execute(model=patcher,conditioning=positive)[0]
        g.inner_model=model
        return g
    native_g=guider(base);native_calls=[]
    def native_prediction(self,x,sigma,model_options=None,seed=None,**kwargs):
        native_calls.append(float(sigma[0]));return x*.25+native_value*.001
    native_g.predict_noise=types.MethodType(native_prediction,native_g)
    baseline=sampler.sample(native_g,sigmas,{'seed':2026101311,'model_options':{}},None,noise,latent,disable_pbar=True)
    assert len(native_calls)==20
    outputs={};reports=[]
    with tempfile.TemporaryDirectory(prefix='h3-local-route-cpu-') as directory:
        for name in ('full','zero','one','roi','uniform'):
            options=dict(graph['50']['inputs']);options.update(model=base,positive=positive,
                run_id='cpu_'+name,audit_dir=str(Path(directory)/'router'),
                mask_path=str(root/'configs/source_query_mask.json'),
                mask_variant='uniform' if name=='uniform' else 'roi')
            if name=='full':
                for key in ('mask_variant','mask_path','mask_sha256'):options.pop(key)
                patched=FullNode().apply(**options)[0];core=full_core
            else:
                patched=Node().apply(**options)[0];core=local_core
            state=patched.model_options['transformer_options']['patches_replace']['dit'][('double_block',0)].state
            original_plan=state.plan_for
            # Real production geometry is tested separately; tiny attention avoids N² CPU allocations.
            state.plan_for=lambda _:tiny_plan
            if name!='full':
                actual=state.query_gain.tensor.reshape(6,23,41)
                selected=actual[:,9,21].reshape(6,1,1).clone()
                if name=='zero':selected.zero_()
                if name=='one':selected.fill_(1)
                state.query_gain=local_mask.QueryGain(selected,(6,1,1))
            if name in ('roi','uniform'):
                patched=Readout().apply(patched,'cpu_'+name,str(Path(directory)/'x0'),1312,736,141)[0]
            clone=patched.clone()
            block_patches=clone.model_options['transformer_options']['patches_replace']['dit']
            assert all(block_patches[('double_block',i)].state is state for i in range(50))
            assert clone.model_options is not patched.model_options
            assert clone.model_options['transformer_options'] is not patched.model_options['transformer_options']
            if name!='full':
                options['model']=clone
                try:Node().apply(**options)
                except ValueError as error:assert 'another DiT block patch' in str(error)
                else:raise AssertionError('duplicate local block patch accepted')
            g=guider(clone);calls=[];callback_indices=[]
            def prediction(self,x,sigma,model_options=None,seed=None,**kwargs):
                calls.append(float(sigma[0]));out=None
                for i in range(50):
                    args={'layout':layout,'transformer_options':{'block_index':i,'minimax_h3_layout':layout,'sample_sigmas':sigmas}}
                    def original_block(a):
                        return {'img':a['transformer_options']['optimized_attention_override'](
                            h3.optimized_attention,q,k,v,1,skip_reshape=True)}
                    out=block_patches[('double_block',i)](args,{'original_block':original_block})['img']
                return x*.25+out.mean()*.001
            g.predict_noise=types.MethodType(prediction,g)
            run_options=create_model_options_clone(g.model_options)
            merge_nested_dicts(run_options['transformer_options'].setdefault('wrappers',{}),clone.wrappers,copy_dict1=False)
            run_options['transformer_options']['sample_sigmas']=sigmas
            wrappers=get_all_wrappers(WrappersMP.SAMPLER_SAMPLE,run_options,is_model_options=True)
            assert len(wrappers)==(1 if name in ('roi','uniform') else 0)
            # No predict-noise wrapper and no diagnostic branch NFE.
            assert not get_all_wrappers(WrappersMP.PREDICT_NOISE,run_options,is_model_options=True)
            def callback(index,x0,x,total):
                assert state.forward_index==index and state.next_block==0
                assert state.audit['completed_forward_calls']==index+1
                assert total==20;callback_indices.append(index)
            original_route=core.route_attention
            def cpu_route(*args,**kwargs):return original_route(*args,attention=dense,**kwargs)
            old=[t.clone() for t in (q,k,v,reference,noise,sigmas)];rng=torch.get_rng_state().clone();env=dict(os.environ)
            executor=WrapperExecutor.new_class_executor(sampler.sample,sampler,wrappers)
            with patch.object(core,'route_attention',cpu_route):
                result=executor.execute(g,sigmas,{'seed':2026101311,'model_options':run_options},
                    callback,noise,latent,None,True)
            assert len(calls)==20 and callback_indices==list(range(20))
            assert state.audit['completed_calls']==1000 and state.audit['completed_forward_calls']==20
            assert [i for i,n in enumerate(state.audit['routed_by_forward']) if n]==list(range(6,15))
            assert all(torch.equal(a,b) for a,b in zip(old,(q,k,v,reference,noise,sigmas)))
            assert torch.equal(rng,torch.get_rng_state()) and dict(os.environ)==env
            if name in ('roi','uniform'):
                manifest=json.loads((Path(directory)/'x0'/('cpu_'+name)/'manifest.json').read_text())
                assert manifest['status']=='complete' and manifest['callback_count']==20
                final=torch.load(Path(directory)/'x0'/('cpu_'+name)/'sampler_final.pt',weights_only=True,map_location='cpu')
                ready=model.process_latent_out(NestedTensor(unpack_latents(result,shapes))).unbind()
                assert torch.equal(final['video'],ready[0]) and torch.equal(final['audio'],ready[1])
            outputs[name]=result
            reports.append({'case':name,'NFE':len(calls),'Euler_updates':20,'callbacks':len(callback_indices),
                            'complete_blocks':1000,'state_shared_through_clone':True,
                            'QKV_reference_noise_sigmas_RNG_env_unchanged':True,
                            'independent_readout':name in ('roi','uniform')})
    assert torch.equal(outputs['zero'],baseline)
    assert torch.equal(outputs['one'],outputs['full'])
    assert not torch.cuda.is_initialized()
    print('H3_LOCAL_ROUTE_CPU_SMOKE='+json.dumps({'success':True,'CUDA_initialized':False,
        'actual_node_loader':True,'actual_MiniMax_patchify_row_order':True,
        'actual_clean_reference_hash_verified':True,'zero_native_bitwise':True,'one_Full_bitwise':True,
        'actual_graph_auxiliary_paths_and_four_reference_outputs':True,
        'actual_native_small_preprocessing_pair_snapshot_cached_noise':True,
        'no_predict_noise_wrapper':True,'cases':reports,'elapsed_seconds':time.monotonic()-started,
        'scope':'Real loader/clone/Guider/Euler/readout, synthetic small attention only; no GPU/weights/Flash claims'}))


if __name__=='__main__':main()
