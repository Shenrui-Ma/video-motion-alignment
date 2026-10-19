#!/usr/bin/env python3
"""One bounded actual Comfy terminal-wrapper test per state; synthetic DiT only.

Uses official ModelPatcher, loader, Guider, process_conds, H3 PackedLayout,
MixedPrecisionOps FinalLayer. No checkpoint weights, VAE, Qwen or CUDA.
"""
import argparse,asyncio,hashlib,importlib.util,json,os,sys,tempfile,time,types
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--comfy-root',required=True);p.add_argument('--compat-bootstrap',required=True);a=p.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch
    torch.set_num_threads(1)
    assert not torch.cuda.is_initialized()
    root=Path(__file__).resolve().parents[1]
    sys.path[:0]=[a.comfy_root,str(root/'extensions'),str(root/'tests')]
    sys.argv=['r48_cpu','--cpu','--disable-dynamic-vram','--use-pytorch-cross-attention']
    import comfy.options
    comfy.options.enable_args_parsing()
    spec=importlib.util.spec_from_file_location('r48_frozen_compat',a.compat_bootstrap)
    compat=importlib.util.module_from_spec(spec);spec.loader.exec_module(compat);compat.install();compat.install_video_compat()
    import nodes
    saved=list(sys.path)
    try:
        sys.path.remove(str(root/'extensions'))
        assert asyncio.run(nodes.load_custom_node(str(root/'extensions/H3AttentionStateProbe')))
        node=nodes.NODE_CLASS_MAPPINGS['H3AttentionStateProbe'];module=sys.modules[node.__module__]
    finally:sys.path[:]=saved
    assert node.RETURN_TYPES==('STRING',) and node.OUTPUT_NODE
    core=sys.modules[module.__package__+'.core'];source_module=sys.modules[module.__package__+'.source']
    signatures=sys.modules[module.__package__+'.signatures'];probe=sys.modules[module.__package__+'.probe']
    from comfy.model_base import MiniMaxH3,ModelType,model_sampling
    from comfy.latent_formats import MiniMaxH3Video
    from comfy.model_patcher import ModelPatcher,create_model_options_clone
    from comfy.patcher_extension import merge_nested_dicts,WrappersMP
    from comfy.samplers import KSAMPLER
    from comfy.k_diffusion.sampling import sample_euler
    from comfy_extras.nodes_custom_sampler import Guider_Basic
    from comfy.utils import unpack_latents
    import comfy.ldm.minimax.model as h3
    import comfy.ops
    from unittest.mock import patch
    from test_probe import dense
    model=MiniMaxH3.__new__(MiniMaxH3);torch.nn.Module.__init__(model)
    diffusion=h3.MiniMaxH3Model.__new__(h3.MiniMaxH3Model);torch.nn.Module.__init__(diffusion)
    diffusion.patch_size=(1,2,2);diffusion.latents_dim=24;diffusion.blocks=torch.nn.ModuleList(torch.nn.Identity() for _ in range(50))
    model.diffusion_model=diffusion;model.model_sampling=model_sampling(None,ModelType.FLOW_AV)
    model.model_sampling.set_parameters(shift=12,audio_shift=3);model.latent_format=MiniMaxH3Video()
    shapes=source_module.SHAPES;model.latent_shapes=list(shapes);model.manual_cast_dtype=torch.float32;model.concat_keys=()
    diffusion.dtype=torch.float32;diffusion.hidden_size=8;model.current_patcher=None
    base=ModelPatcher(model,torch.device('cpu'),torch.device('cpu'),size=1)
    reference=torch.zeros(shapes[0]);portrait=torch.zeros((1,24,1,76,50))
    positive=[[torch.zeros(1,6960,8),{'minimax_token_tags':torch.zeros(6960,dtype=torch.int64),'pooled_output':None,
        'minimax_refs':[{'kind':'image','latent':portrait,'latent_h':76,'latent_w':50},
        {'kind':'video','latent':reference,'latent_t':42,'latent_h':46,'latent_w':82,'ref_audio_t':0,'audio_latent':None}]}]]
    sigmas=torch.tensor(json.loads((root/'configs/sources.json').read_text())['bad']['full_grid'],dtype=torch.float32)
    n=sum(torch.Size(s).numel() for s in shapes);noise=torch.arange(n,dtype=torch.float32).reshape(1,1,-1)/n
    latent=torch.zeros_like(noise);sampler=KSAMPLER(sample_euler)
    # Official mixed-precision output head: same unquantized shapes and loader path.
    final_ops=comfy.ops.mixed_precision_ops(compute_dtype=torch.bfloat16)
    final=h3.FinalLayer(5376,2,96,32,1e-6,dtype=torch.bfloat16,device=torch.device('cpu'),operations=final_ops)
    head_shapes={'norm.weight':(5376,),'adaln_proj.linear.weight':(10752,2),'adaln_proj.linear.bias':(10752,),
                 'video_out.weight':(96,5376),'video_out.bias':(96,),'audio_out.weight':(32,5376),'audio_out.bias':(32,)}
    head_dict={name:torch.ones(shape) if name=='norm.weight' else torch.zeros(shape) for name,shape in head_shapes.items()}
    final.load_state_dict(head_dict,strict=True);diffusion.final_layer=final
    head_x=torch.ones(6,5376,dtype=torch.bfloat16);head_t=torch.ones(2,2,dtype=torch.bfloat16)
    q=torch.arange(1*56*7*4,dtype=torch.float32).reshape(1,56,7,4)/1000
    def attention_pytorch():raise AssertionError('not the inherited Flash wrapper')
    # Historical CPU entities: verify raw PT inventory, original condition tree/UUID,
    # archived raw coordinates, noise and endpoint normalization without encoders.
    historical=[]
    for label in ('bad','normal'):
        actual_source=source_module.Source(label)
        actual_positive=actual_source.positive()
        actual_guider=Guider_Basic(base);actual_guider.set_conds(actual_positive)
        actual_source.restore_original_uuid(actual_guider)
        actual_x=actual_source.input();actual_noise=actual_source.noise();actual_endpoint=actual_source.endpoint()
        historical.append({'state':label,'bound_PT_files':len(actual_source.s['files']),
            'original_condition_tree_exact':True,'actual_raw_input_and_noise_verified':True,
            'actual_endpoint_normalization_verified':True,'processed_GPU_condition_and_endpoint_pending':True})
        del actual_source,actual_positive,actual_guider,actual_x,actual_noise,actual_endpoint
    rows=[];env=dict(os.environ)
    with tempfile.TemporaryDirectory(prefix='r48-real-comfy-') as tmp:
        for case in ('bad','normal','endpoint_mismatch'):
            label='bad' if case=='bad' else 'normal'
            i=0 if label=='bad' else 1
            seed=2026101311+2*i
            original=Guider_Basic(base);original.set_conds(positive)
            processed=model.extra_conds(cross_attn=positive[0][0],device=torch.device('cpu'),latent_shapes=list(shapes),
                minimax_refs=positive[0][1]['minimax_refs'],minimax_token_tags=positive[0][1]['minimax_token_tags'],noise=noise,seed=seed)
            assert type(processed['minimax_payload'].cond['layout']).__name__=='PackedLayout'
            original.conds={'positive':[dict(original.original_conds['positive'][0],model_conds=processed)]}
            condition=signatures.condition_signature(original)
            x=noise*0.125+i*0.03125;expected=x.clone()
            raw=[v.clone() for v in unpack_latents(expected,shapes)]
            src=types.SimpleNamespace(label=label,condition=condition,s={'source_run':'synthetic_'+label,'seed':seed,'full_grid':sigmas.tolist(),
                 'noise':{'packed_signature':core.readout.tensor_signature(noise)},
                 'endpoint':{'raw_stream_signatures':[core.readout.tensor_signature(v) for v in raw]}},
                 input=lambda x=x:x.clone(),endpoint=lambda raw=raw,case=case:[v.clone() if case!='endpoint_mismatch' else torch.zeros_like(v) for v in raw])
            patched,state=module.install(base,positive,src,Path(tmp)/case,require_cuda=False)
            assert not any(base.wrappers.values()) and not base.model_options.get('transformer_options',{}).get('patches_replace')
            # Additional clone verifies state references survive real cached ModelPatcher.clone.
            sampled=patched.clone()
            guider=Guider_Basic(sampled);guider.set_conds(positive)
            source_module.Source.restore_original_uuid(src,guider)
            guider.inner_model=model;guider.conds={'positive':[dict(guider.original_conds['positive'][0])]}
            options=create_model_options_clone(guider.model_options)
            merge_nested_dicts(options['transformer_options'].setdefault('wrappers',{}),sampled.wrappers,copy_dict1=False)
            guider.model_options=options
            calls=[];captured=[]
            def capture(this,cq,ck,cv,output,lse,plan,positions):
                # Production mapping against actual official H3 positions; only attention tensors tiny.
                m=probe.mapping(plan,positions);assert len(m['queries'])==1050
                before=[v.clone() for v in (cq,ck,cv,output,lse)]
                cq2=cq[:,:4,:3].clone();ck2=ck[:,:4,:6].clone();cv2=cv[:,:4,:6].clone()
                result=probe.read_distribution(cq2,ck2,cv2,lse[:,:4,:3].clone(),dense,bins=3,frame_rows=2,query_bins=[0,1,2])
                assert result['quality']['status']=='PASS'
                assert all(torch.equal(a,b) for a,b in zip((cq,ck,cv,output,lse),before))
                this.probe_calls+=1;captured.append(result['quality'])
            state.capture=types.MethodType(capture,state)
            def prediction(this,raw_x,sigma,model_options=None,seed=None):
                calls.append(core.readout.tensor_signature(raw_x))
                # Official BaseModel._apply_model performs the actual FLOW_AV timestep
                # conversion, then invokes the diffusion module and its entry hook.
                return model._apply_model(raw_x,sigma,c_crossattn=positive[0][0],
                    transformer_options=model_options['transformer_options'])
            def diffusion_prediction(this,raw_x,timestep,context=None,control=None,transformer_options=None,**kwargs):
                packed=guider.conds['positive'][0]['model_conds']['minimax_payload'].cond['layout']
                patches=transformer_options['patches_replace']['dit']
                for block in range(50):
                    args={'layout':packed,'transformer_options':dict(transformer_options,block_index=block,minimax_h3_layout=packed)}
                    def original_block(local):
                        return local['transformer_options']['optimized_attention_override'](attention_pytorch,q,q/2,q.cos(),56,skip_reshape=True)
                    patches[('double_block',block)](args,{'original_block':original_block})
                # Literal frozen MiniMaxH3Model._forward head mapping, not entry sigma.
                head_sigma=(timestep.flatten()[0]/1000.0).float().clamp(min=1e-6)
                final(head_x,head_t,(1,3,0),(4,6,1),head_sigma,transformer_options['sample_sigmas'],(12.,3.))
                return torch.zeros_like(raw_x)
            diffusion.forward=types.MethodType(diffusion_prediction,diffusion)
            guider.predict_noise=types.MethodType(prediction,guider)
            before=torch.random.get_rng_state().clone();started=time.perf_counter()
            caught=None
            try:
                with torch.inference_mode(),patch.object(core.router,'flash_attention_lse',dense),module.ModelAudit(model,state), \
                     patch.object(model.model_sampling,'noise_scaling',side_effect=AssertionError('noise_scaling called')), \
                     patch.object(sampler,'sample',side_effect=AssertionError('Euler/KSAMPLER called')):
                    result=guider.inner_sample(noise,latent,torch.device('cpu'),sampler,sigmas,None,None,True,seed,latent_shapes=list(shapes))
            except ValueError as error:
                caught=error;state.fail(error)
            if case=='endpoint_mismatch':
                assert caught and str(caught)=='actual Native4 AV endpoint not bitwise equal'
                saved=json.loads((state.output/'report.json').read_text())
                assert saved['status']=='failed' and saved['DiT_NFE']==saved['attempted_forwards']==saved['completed_forwards']==1
                assert saved['completed_blocks']==50 and saved['model_and_probe_seconds_synchronized']>0
                assert not (state.output/'endpoint_raw.pt').exists()
            else:
                assert caught is None
                assert torch.equal(result,model.process_latent_out(x)) and state.complete
            assert len(calls)==1 and len(captured)==1
            assert state.completed_blocks==state.attention_calls==50 and state.extra_conds_calls==state.output_head_calls==1
            assert signatures.condition_signature(guider)==condition and torch.equal(before,torch.random.get_rng_state())
            assert 'extra_conds' not in vars(model) and not final._forward_pre_hooks and not diffusion._forward_pre_hooks
            assert state.audit['sigma_path']['exact_official_timestep'] and state.audit['sigma_path']['exact_official_head_sigma']
            # Exception path restores official extra_conds and head hooks too.
            with patch.object(model,'extra_conds',model.extra_conds):
                saved=model.extra_conds
                try:
                    with module.ModelAudit(model,state):raise ValueError('intentional pre-forward failure')
                except ValueError:pass
                assert model.extra_conds==saved and not final._forward_pre_hooks and not diffusion._forward_pre_hooks
            rows.append({'case':case,'state':label,'DiT_NFE':1,'Euler_updates':0,'callbacks':0,'blocks':50,'probe_calls':1,'extra_conds':1,
                'actual_PackedLayout_rows':87592,'actual_model_head':'MixedPrecisionOps.Linear','Native_endpoint_exact':case!='endpoint_mismatch','intentional_mismatch_aborted_with_cost':case=='endpoint_mismatch',
                'actual_position_mapping':True,'original_UUID_and_processed_condition_exact':True,'RNG_unchanged':True,
                'official_BaseModel_apply_model_and_FLOW_AV_timestep':True,'sigma_path':state.audit['sigma_path'],
                'noise_scaling_not_called':True,'hook_exception_cleanup':True,'seconds':time.perf_counter()-started})
    assert dict(os.environ)==env and not torch.cuda.is_initialized()
    print('R48_REAL_COMFY_CPU='+json.dumps({'passed':True,'CUDA_initialized':False,'actual_directory_loader':True,'cases':rows,'historical_CPU_inputs':historical,
        'scope':'actual Comfy interfaces and H3 condition/head/position structures; synthetic QKV/DiT, no weights, no actual source endpoint GPU proof',
        'source_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for d in ('extensions','scripts','tests') for p in (root/d).rglob('*.py')}}))
if __name__=='__main__':main()
