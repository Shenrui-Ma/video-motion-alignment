"""Actual Comfy loader/cached ModelPatcher/Guider/Euler20, two-source one-seed Native CPU fixture."""
import argparse,asyncio,hashlib,importlib.util,json,os,sys,tempfile,time,types
from pathlib import Path
from unittest.mock import patch

def main():
 p=argparse.ArgumentParser();p.add_argument('--core',required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];started=time.monotonic()
 os.environ['CUDA_VISIBLE_DEVICES']='';sys.path[:0]=[str(root/'scripts'),str(root/'tests'),a.core,str(Path(a.core).parent/'runtime_deps')];sys.argv=['r38-cpu','--cpu','--disable-dynamic-vram','--use-pytorch-cross-attention']
 import torch
 torch.set_num_threads(1);torch.set_num_interop_threads(1)
 import comfy.options
 comfy.options.enable_args_parsing()
 from compatibility_bootstrap import install,install_video_compat
 install();install_video_compat()
 import nodes
 for path,parent in [(Path(a.core)/'comfy_extras/nodes_custom_sampler.py','comfy_extras'),*[(root/'extensions'/n,'custom_nodes') for n in ('H3EventAudit','H3PairAudit','H3TemporalRouter','H3X0Readout')]]:
  assert asyncio.run(nodes.load_custom_node(str(path),module_parent=parent))
 Pair=nodes.NODE_CLASS_MAPPINGS['H3PairConditionSnapshot'];pair_module=sys.modules[Pair.__module__]
 Node=nodes.NODE_CLASS_MAPPINGS['H3TemporalRouter'];Readout=nodes.NODE_CLASS_MAPPINGS['H3X0Readout'];node=sys.modules[Node.__module__];core=sys.modules[Node.__module__+'.core'];readout_core=sys.modules[Readout.__module__+'.core'];aux=sys.modules[nodes.NODE_CLASS_MAPPINGS['H3EventAuditNoise'].__module__]
 from comfy.model_base import MiniMaxH3,ModelType,model_sampling
 from comfy.latent_formats import MiniMaxH3Video
 from comfy.model_patcher import ModelPatcher,create_model_options_clone
 from comfy.patcher_extension import WrapperExecutor,WrappersMP,merge_nested_dicts,get_all_wrappers
 from comfy.samplers import KSAMPLER
 from comfy.k_diffusion.sampling import sample_euler
 from comfy.nested_tensor import NestedTensor
 from comfy.utils import unpack_latents
 from comfy.ldm.modules.attention import AttentionTensorContainer,attention_pytorch
 import comfy.ldm.minimax.model as h3
 import r38_contract as c
 model=MiniMaxH3.__new__(MiniMaxH3);torch.nn.Module.__init__(model)
 with torch.device('meta'):diffusion=h3.MiniMaxH3Model(num_attention_heads=56,device='meta',dtype=torch.float32,operations=torch.nn)
 model.diffusion_model=diffusion;model.model_sampling=model_sampling(None,ModelType.FLOW_AV);model.model_sampling.set_parameters(shift=12,audio_shift=3);model.latent_format=MiniMaxH3Video();model.manual_cast_dtype=torch.float32;model.concat_keys=()
 shapes=((1,24,2,2,2),(1,32,2,8));model.latent_shapes=list(shapes);base=ModelPatcher(model,torch.device('cpu'),torch.device('cpu'),size=1)
 reference=torch.zeros((1,24,2,2,2));portrait=torch.zeros((1,24,1,2,2));positive=[[torch.zeros((1,2,5376)),{'minimax_token_tags':torch.zeros((1,2),dtype=torch.int64),'minimax_refs':[{'kind':'image','latent':portrait,'latent_h':2,'latent_w':2},{'kind':'video','latent':reference,'latent_t':2,'latent_h':2,'latent_w':2,'ref_audio_t':0}]}]]
 positive_meta=[[torch.empty((1,6960,5120),device='meta'),{'minimax_refs':[{'kind':'image','latent':torch.empty((1,24,1,76,50),device='meta'),'latent_h':76,'latent_w':50},{'kind':'video','latent':torch.empty((1,24,42,46,82),device='meta'),'latent_t':42,'latent_h':46,'latent_w':82,'ref_audio_t':0}]}]]
 gen=torch.Generator().manual_seed(20);q,k,v=[torch.randn(1,56,29,128,generator=gen) for _ in range(3)];originals=[t.clone() for t in (q,k,v,reference,portrait)]
 plan={'reference_video_segment':[3,15],'query_interval_half_open':[17,29],'latent_interval_half_open':[0,2],'frame_rows':6,'seq_len':29};route=core.route_attention
 def dense(q,k,v):
  z=q@k.transpose(-1,-2)/(q.shape[-1]**.5);return z.softmax(-1)@v,z.logsumexp(-1)
 def cpu_route(*args,**kw):return route(*args,**kw,attention=dense)
 native=cpu_route(q,k,v,56,plan,mode='native');full=cpu_route(q,k,v,56,plan,mode='mass_preserve');sampler=KSAMPLER(sample_euler);reports=[];states=[];recorders=[];noises=[];outputs=[]
 with tempfile.TemporaryDirectory(prefix='r38-real-cpu-') as td:
  work=Path(td);lane=root
  c.ROOT=lane;validate_original=c.validate_job
  def validate(run,root=None):return validate_original(run,lane if root is None else root)
  with patch.object(c,'validate_job',side_effect=validate):
   for run,row in c.registry(lane)[0].items():
    graph=c.read(lane/'configs/graphs'/f'{run}.json');sigmas=torch.tensor([float(x) for x in graph['9']['inputs']['sigmas'].split(',')]);state_ctor=node.RouterState
    def factory(*args,**kw):
     args=list(args);args[12]=str(work/'router');return state_ctor(*args,**kw)
    args={k:v for k,v in graph['50']['inputs'].items() if k not in ('model','positive')}
    with patch.object(node,'RouterState',side_effect=factory):routed=Node().apply(base,positive_meta,**args)[0]
    final=Readout().apply(routed,**{k:v for k,v in graph['52']['inputs'].items() if k!='model'})[0].clone()
    patches=final.model_options['transformer_options']['patches_replace']['dit'];state=patches[('double_block',0)].state;states.append(state);state.plan_for=lambda _:plan
    recorder=final.get_wrappers(WrappersMP.SAMPLER_SAMPLE,'H3X0Readout/passive-v1')[0];recorders.append(recorder);recorder.config=readout_core.CaptureConfig(run,str(work/'x0'),32,32,5)
    assert state.audit['completed_calls']==0 and all(patches[('double_block',i)].state is state for i in range(50))
    sample=NestedTensor([torch.zeros(s) for s in shapes])
    # Actual graph registration and official PackedLayout; only the small tensors are synthetic.
    pair_args={k:v for k,v in graph['51']['inputs'].items() if k not in ('positive','target')}
    layout=h3.PackedLayout(positive[0][0].shape[1],*shapes[0][2:],shapes[1][-1],refs=positive[0][1]['minimax_refs'])
    info=pair_module._tensor_info
    common={'schema':'h3-event-audit-v1','run_id':pair_args['source_run_id'],'conditioning_embedding':info(positive[0][0]),'token_tags':info(positive[0][1]['minimax_token_tags']),'native_vae_calls':[{'latent':info(x['latent'])} for x in positive[0][1]['minimax_refs']],'target_latent_shapes':[list(s) for s in shapes],'packed_layout':{'seq_len':layout.seq_len,'segments':[list(x) for x in layout.segments],'position_ids':info(layout.position_ids)}}
    pair_work=work/'pairs';pair_work.mkdir(exist_ok=True);(pair_work/(pair_args['source_run_id']+'_conditioning.json')).write_text(json.dumps(common));pair_target={'samples':sample};before_pair_rng=torch.get_rng_state().clone()
    with patch.object(c,'audit_dir',return_value=pair_work):
     pair_result=Pair().snapshot(positive,pair_target,**pair_args)
     assert pair_result[0] is positive and pair_result[1] is pair_target
     assert json.loads((pair_work/(run+'_conditioning.json')).read_text())['pair_snapshot']['verified'] is True
     for wrong in ('r26_'+row['case']['source_id']+'_shared','r38_source_wrong_shared'):
      try:Pair().snapshot(positive,pair_target,**dict(pair_args,source_run_id=wrong))
      except ValueError as exc:assert 'source-conditioning identity' in str(exc)
      else:raise AssertionError('wrong source registration accepted')
    assert torch.equal(before_pair_rng,torch.get_rng_state())
    noise_obj=aux.CachedNoise(row['seed'],work,run,graph['6']['inputs']['pair_id']);noise_nested=noise_obj.generate_noise({'samples':sample});noises.append([t.clone() for t in noise_nested.unbind()]);noise=torch.cat([t.reshape(1,1,-1) for t in noise_nested.unbind()],-1);latent=torch.zeros_like(noise)
    # Identical shape and seed intentionally give identical AV noise across sources; cache IDs stay source-specific.
    cached=noise_obj.generate_noise({'samples':sample});assert all(torch.equal(a,b) for a,b in zip(cached.unbind(),noise_nested.unbind()))
    processed=model.extra_conds(cross_attn=positive[0][0],device=torch.device('cpu'),latent_shapes=list(shapes),minimax_refs=positive[0][1]['minimax_refs'],noise=noise,seed=row['seed']);assert type(processed['minimax_payload'].cond['layout']).__name__=='PackedLayout'
    def setup(patcher):
     guider=nodes.NODE_CLASS_MAPPINGS['BasicGuider'].execute(model=patcher,conditioning=positive)[0];guider.inner_model=model;guider.conds={'positive':[dict(guider.original_conds['positive'][0],model_conds=processed)]}
     options=create_model_options_clone(guider.model_options);merge_nested_dicts(options['transformer_options'].setdefault('wrappers',{}),patcher.wrappers,copy_dict1=False);options['transformer_options']['sample_sigmas']=sigmas;guider.model_options=options;return guider,options
    baseline_calls=[];baseline_x0=[];ng,_=setup(base)
    def baseline_prediction(self,x,sigma,model_options=None,seed=None,**kwargs):
     i=len(baseline_calls);baseline_calls.append(1);out=native;return x*.25+out.mean()*.001
    ng.predict_noise=types.MethodType(baseline_prediction,ng)
    with torch.inference_mode():baseline=sampler.sample(ng,sigmas,{'seed':row['seed'],'model_options':{}},lambda i,x0,x,n:baseline_x0.append(x0.clone()),noise,latent,disable_pbar=True)
    guider,options=setup(final);calls=[];callbacks=[]
    def prediction(self,x,sigma,model_options=None,seed=None,**kwargs):
     i=len(calls);calls.append(1)
     for block in range(50):
      opts={'block_index':block,'minimax_h3_layout':object(),'sample_sigmas':sigmas}
      def original(a):return attention_pytorch(*(AttentionTensorContainer(t) for t in (q,k,v)),56,mask=None,skip_reshape=True,transformer_options=a['transformer_options'])
      out=patches[('double_block',block)]({'layout':opts['minimax_h3_layout'],'transformer_options':opts},{'original_block':original});assert torch.equal(out,native)
     return x*.25+out.mean()*.001
    guider.predict_noise=types.MethodType(prediction,guider)
    def cb(i,x0,x,n):assert n==20 and state.audit['completed_forward_calls']==i+1;callbacks.append(i)
    rng=torch.get_rng_state().clone();env=dict(os.environ);noise_before=noise.clone();wrappers=get_all_wrappers(WrappersMP.SAMPLER_SAMPLE,options,is_model_options=True);assert len(wrappers)==1
    executor=WrapperExecutor.new_class_executor(sampler.sample,sampler,wrappers)
    with torch.inference_mode(),patch.object(core,'route_attention',side_effect=cpu_route),patch.object(core,'temporal_readout',return_value={}):result=executor.execute(guider,sigmas,{'seed':row['seed'],'model_options':options},cb,noise,latent,None,True)
    assert torch.equal(result,baseline) and len(baseline_calls)==20 and len(calls)==20 and callbacks==list(range(20));outputs.append(result)
    assert torch.equal(noise,noise_before) and torch.equal(rng,torch.get_rng_state()) and env==dict(os.environ)
    manifest=c.read(work/'x0'/run/'manifest.json');assert manifest['status']=='complete' and manifest['callback_count']==20 and [x['step_zero_based'] for x in manifest['captures']]==list(range(20));assert len(list((work/'x0'/run).glob('*.pt')))==21
    for i in range(20):
     snap=torch.load(work/'x0'/run/f'x0_step{i:03d}.pt',weights_only=True);assert snap['metadata']['seed']==row['seed'] and snap['metadata']['step_zero_based']==i
     reference_x0=model.process_latent_out(NestedTensor(unpack_latents(baseline_x0[i],shapes))).unbind();assert torch.equal(snap['video'],reference_x0[0]) and torch.equal(snap['audio'],reference_x0[1])
    saved=torch.load(work/'x0'/run/'sampler_final.pt',weights_only=True);ready=model.process_latent_out(NestedTensor(unpack_latents(result,shapes))).unbind();assert torch.equal(saved['video'],ready[0]) and torch.equal(saved['audio'],ready[1])
    assert state.audit['completed_calls']==1000 and state.audit['completed_forward_calls']==20 and state.audit['routed_calls']==0 and state.audit['routed_by_forward']==[0]*20
    reports.append({'run':run,'actual_Euler_updates':20,'NFE':20,'callbacks':20,'blocks':1000,'routes':0,'snapshots':21,'actual_graph_pair_snapshot_and_wrong_source_rejection':True,'Native_no_readout_chosen20_and_final_bitwise':True})
  assert len({id(s) for s in states})==2 and len({id(r) for r in recorders})==2
  assert all(torch.equal(a,b) for ns in noises[1:] for a,b in zip(noises[0],ns));assert all(torch.equal(outputs[0],z) for z in outputs[1:])
 assert not base.model_options['transformer_options'].get('patches_replace',{}).get('dit') and not base.get_wrappers(WrappersMP.SAMPLER_SAMPLE,'H3X0Readout/passive-v1')
 assert all(torch.equal(a,b) for a,b in zip(originals,(q,k,v,reference,portrait))) and not torch.cuda.is_initialized()
 print('R38_CACHED_NATIVE_CPU='+json.dumps({'passed':True,'actual_node_loader':True,'actual_Euler20':True,'two_distinct_states_and_recorders':True,'cached_base_unmodified':True,'same_seed_shape_noise_equal_and_source_caches_isolated':True,'CUDA_initialized':False,'runs':reports,'seconds':time.monotonic()-started,'scope':'actual Comfy loader/Guider/clone/Euler20/readout and official H3 meta/processed-condition interfaces; tiny synthetic attention/conditions; no neural video quality/GPU equivalence claim'}))
if __name__=='__main__':main()
