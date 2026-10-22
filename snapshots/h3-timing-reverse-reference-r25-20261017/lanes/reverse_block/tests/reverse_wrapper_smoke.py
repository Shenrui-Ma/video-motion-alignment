"""Real official loader/Guider/ModelPatcher/KSAMPLER Euler20, tiny CPU DiT fixtures.
No model weights/GPU. Production architecture metadata is meta, and actual H3
extra_conds uses tiny tensors. Fixture-only sampler shapes/parent005 are explicit.
"""
import argparse,asyncio,importlib.util,json,os,sys,tempfile,time,types
from pathlib import Path
from unittest.mock import patch

def main():
 p=argparse.ArgumentParser();p.add_argument('--comfy-root',required=True);p.add_argument('--compat-bootstrap',required=True);a=p.parse_args()
 root=Path(__file__).resolve().parents[1];start=time.monotonic();os.environ['CUDA_VISIBLE_DEVICES']=''
 import torch
 torch.set_num_threads(1);torch.set_num_interop_threads(1);assert not torch.cuda.is_initialized()
 sys.path[:0]=[str(root/'scripts'),a.comfy_root,str(root/'tests')]
 sys.argv=['reverse_cpu_smoke','--cpu','--disable-dynamic-vram','--use-pytorch-cross-attention']
 import comfy.options
 comfy.options.enable_args_parsing()
 spec=importlib.util.spec_from_file_location('r25_existing_compat',a.compat_bootstrap);compat=importlib.util.module_from_spec(spec);spec.loader.exec_module(compat);compat.install();compat.install_video_compat()
 import nodes
 for path,parent in [(Path(a.comfy_root)/'comfy_extras/nodes_custom_sampler.py','comfy_extras'),*[(root/'extensions'/n,'custom_nodes') for n in ('H3EventAudit','H3PairAudit','H3ReverseReferenceRouter','H3X0Readout')]]:
  assert asyncio.run(nodes.load_custom_node(str(path),module_parent=parent))
 Node=nodes.NODE_CLASS_MAPPINGS['H3ReverseReferenceRouter'];Readout=nodes.NODE_CLASS_MAPPINGS['H3X0Readout']
 node_module=sys.modules[Node.__module__];core=sys.modules[Node.__module__+'.core'];gate_module=sys.modules[Node.__module__+'.sampler_gate'];readout_core=sys.modules[Readout.__module__+'.core']
 from comfy.model_base import MiniMaxH3,ModelType,model_sampling
 from comfy.latent_formats import MiniMaxH3Video
 from comfy.model_patcher import ModelPatcher,create_model_options_clone
 from comfy.patcher_extension import WrapperExecutor,WrappersMP,merge_nested_dicts,get_all_wrappers
 from comfy.samplers import KSAMPLER
 from comfy.k_diffusion.sampling import sample_euler
 from comfy.nested_tensor import NestedTensor
 from comfy.utils import unpack_latents
 import comfy.ldm.minimax.model as h3
 from test_reverse import plan,dense
 import r25_contract as contract
 graph=contract.read(root/'configs/graphs'/f"{contract.run_name('reverse_block')}.json")
 assert graph['7']['class_type']=='BasicGuider'
 model=MiniMaxH3.__new__(MiniMaxH3);torch.nn.Module.__init__(model)
 with torch.device('meta'):diffusion=h3.MiniMaxH3Model(dtype=torch.float32,device='meta',operations=torch.nn)
 model.diffusion_model=diffusion;model.model_sampling=model_sampling(None,ModelType.FLOW_AV);model.model_sampling.set_parameters(shift=12,audio_shift=3)
 model.latent_format=MiniMaxH3Video();model.manual_cast_dtype=torch.float32;model.concat_keys=()
 shapes=((1,24,2,2,2),(1,32,2,8));model.latent_shapes=list(shapes)
 base=ModelPatcher(model,torch.device('cpu'),torch.device('cpu'),size=1)
 reference=torch.zeros((1,24,2,2,2));portrait=torch.zeros((1,24,1,2,2))
 positive=[[torch.zeros((1,2,5376)),{'minimax_refs':[{'kind':'image','latent':portrait,'latent_h':2,'latent_w':2},{'kind':'video','latent':reference,'latent_t':2,'latent_h':2,'latent_w':2,'ref_audio_t':0}]}]]
 # Node architecture/conditioning gate sees full production geometry without allocations.
 positive_meta=[[torch.empty((1,6960,5120),device='meta'),{'minimax_refs':[{'kind':'image','latent':torch.empty((1,24,1,38,100),device='meta'),'latent_h':38,'latent_w':100},{'kind':'video','latent':torch.empty((1,24,42,46,82),device='meta'),'latent_t':42,'latent_h':46,'latent_w':82,'ref_audio_t':0}]}]]
 count=sum(torch.Size(s).numel() for s in shapes);noise=torch.arange(count,dtype=torch.float32).reshape(1,1,-1)/count;latent=torch.zeros_like(noise)
 sigmas=torch.tensor([float(x) for x in graph['9']['inputs']['sigmas'].split(',')]);sampler=KSAMPLER(sample_euler)
 processed=model.extra_conds(cross_attn=positive[0][0],device=torch.device('cpu'),latent_shapes=list(shapes),minimax_refs=positive[0][1]['minimax_refs'],noise=noise,seed=2026101311)
 assert type(processed['minimax_payload'].cond['layout']).__name__=='PackedLayout'
 gen=torch.Generator().manual_seed(992);q,k,v=[torch.randn((1,56,31,128),generator=gen) for _ in range(3)]
 def setup(patcher):
  g=nodes.NODE_CLASS_MAPPINGS['BasicGuider'].execute(model=patcher,conditioning=positive)[0];g.inner_model=model
  g.conds={'positive':[dict(g.original_conds['positive'][0],model_conds=processed)]}
  options=create_model_options_clone(g.model_options);merge_nested_dicts(options['transformer_options'].setdefault('wrappers',{}),patcher.wrappers,copy_dict1=False);options['transformer_options']['sample_sigmas']=sigmas;g.model_options=options
  return g,options
 native_value=h3.optimized_attention(q,k,v,56,skip_reshape=True).mean();baseline_calls=[];parent={}
 ng,_=setup(base)
 def native_prediction(self,x,sigma,model_options=None,seed=None,**kw):baseline_calls.append(float(sigma[0]));return x*.25+native_value*.001
 ng.predict_noise=types.MethodType(native_prediction,ng)
 def native_cb(i,x0,x,n):
  if i==5:parent.update(gate_module.normalized_signature(x0,model,shapes))
 with torch.inference_mode():baseline=sampler.sample(ng,sigmas,{'seed':2026101311,'model_options':{}},native_cb,noise,latent,disable_pbar=True)
 assert len(baseline_calls)==20
 reports=[];outputs={};base_wrappers=dict(base.wrappers)
 with tempfile.TemporaryDirectory(prefix='r25-real-cpu-') as td:
  for mode,order in [('native','router_first'),('reverse_block','router_first'),('reverse_same','router_first'),('reverse_block','readout_first'),('reverse_same','readout_first'),('badprefix','router_first')]:
   name=mode+'_'+order;folder=Path(td)/name
   original_state=node_module.ReverseState
   def factory(metadata,_mode,run_id,audit_dir):return original_state(metadata,'reverse_block',run_id,str(folder/'router'),capture_features=False)
   def addreadout(patcher):
    obj=Readout().apply(patcher,graph['52']['inputs']['run_id'],graph['52']['inputs']['output_dir'],1312,736,141)[0]
    rec=obj.get_wrappers(WrappersMP.SAMPLER_SAMPLE,'H3X0Readout/passive-v1')[0]
    rec.config=readout_core.CaptureConfig(name,str(folder/'x0'),32,32,5)
    return obj
   initial=addreadout(base) if order=='readout_first' else base
   with patch.object(node_module,'ReverseState',factory):patched=Node().apply(initial,positive_meta,**{k:graph['50']['inputs'][k] for k in ('mode','run_id','audit_dir')})[0]
   if order=='router_first':patched=addreadout(patched)
   clone=patched.clone();patches=clone.model_options['transformer_options']['patches_replace']['dit'];s=patches[('double_block',0)].state
   s.mode='native' if mode=='native' else ('reverse_block' if mode=='badprefix' else mode);s.audit['mode']=s.mode;s.plan_for=lambda _:plan()
   gate=clone.get_wrappers(WrappersMP.SAMPLER_SAMPLE,gate_module.KEY)[0];gate.shapes=shapes;gate.parent=dict(parent)
   if mode=='badprefix':gate.parent['video']=dict(parent['video'],sha256='0'*64)
   assert gate.state is s and all(patches[('double_block',i)].state is s for i in range(50))
   assert clone.model_options is not patched.model_options and base.wrappers==base_wrappers
   assert not base.model_options['transformer_options'].get('patches_replace',{}).get('dit')
   g,options=setup(clone);calls=[];callbacks=[];layout=object()
   def prediction(self,x,sigma,model_options=None,seed=None,**kw):
    calls.append(float(sigma[0]));output=None
    for i in range(50):
     blockargs={'layout':layout,'transformer_options':{'block_index':i,'minimax_h3_layout':layout,'sample_sigmas':sigmas}}
     def original(a):return {'img':a['transformer_options']['optimized_attention_override'](h3.optimized_attention,q,k,v,56,skip_reshape=True)}
     output=patches[('double_block',i)](blockargs,{'original_block':original})['img']
    return x*.25+output.mean()*.001
   g.predict_noise=types.MethodType(prediction,g)
   wrappers=get_all_wrappers(WrappersMP.SAMPLER_SAMPLE,options,is_model_options=True);assert len(wrappers)==2
   assert not get_all_wrappers(WrappersMP.PREDICT_NOISE,options,is_model_options=True)
   def cb(i,x0,x,n):assert n==20 and s.next_block==0 and s.audit['completed_forward_calls']==i+1;callbacks.append(i)
   originals=[x.clone() for x in (q,k,v,noise,reference,portrait,sigmas)];rng=torch.get_rng_state().clone();env=dict(os.environ)
   executor=WrapperExecutor.new_class_executor(sampler.sample,sampler,wrappers)
   with torch.inference_mode(),patch.object(core,'flash_attention_lse',dense):
    try:result=executor.execute(g,sigmas,{'seed':2026101311,'model_options':options},cb,noise,latent,None,True)
    except ValueError as e:
     if mode!='badprefix' or 'prefix mismatch' not in str(e):raise
     assert len(calls)==6 and s.audit['routed_calls']==0 and not s.prefix_passed
     reports.append({'case':name,'expected_prefix_rejection':True,'NFE':6,'routed_calls':0});continue
   assert len(calls)==20 and callbacks==list(range(20)) and s.audit['completed_calls']==1000
   active=[] if mode=='native' else list(range(6,15));assert [i for i,n in enumerate(s.audit['routed_by_forward']) if n]==active
   assert s.audit['routed_calls']==len(active)*50 and s.audit['sampler_gate']['status']=='complete'
   assert all(torch.equal(x,y) for x,y in zip(originals,(q,k,v,noise,reference,portrait,sigmas))) and torch.equal(rng,torch.get_rng_state()) and env==dict(os.environ)
   manifest=json.loads((folder/'x0'/name/'manifest.json').read_text());assert manifest['status']=='complete' and manifest['callback_count']==20 and len(manifest['captures'])==8
   final=torch.load(folder/'x0'/name/'sampler_final.pt',weights_only=True,map_location='cpu');ready=model.process_latent_out(NestedTensor(unpack_latents(result,shapes))).unbind();assert torch.equal(final['video'],ready[0]) and torch.equal(final['audio'],ready[1])
   outputs[name]=result;reports.append({'case':name,'NFE':20,'Euler_updates':20,'callbacks':20,'blocks':1000,'routed':s.audit['routed_calls'],'state_shared_clone':True,'actual_processed_condition_tree':True,'input_noise_rng_environment_unchanged':True})
 assert torch.equal(outputs['native_router_first'],baseline)
 for mode in ('reverse_block','reverse_same'):assert torch.equal(outputs[mode+'_router_first'],outputs[mode+'_readout_first'])
 assert not torch.cuda.is_initialized()
 print('R25_REVERSE_CPU_SMOKE='+json.dumps({'success':True,'actual_node_loader':True,'actual_Euler20':True,'native_bitwise':True,'both_wrapper_orders_bitwise':True,'CUDA_initialized':False,'cases':reports,'seconds':time.monotonic()-start,'scope':'actual Comfy loader/meta official architecture/processed H3 conditions/Guider/clone/Euler/readout; tiny synthetic attention, no weight/GPU/backend claim; prefix fixture normalization tested, not actual historical sample replication'}))
if __name__=='__main__':main()
