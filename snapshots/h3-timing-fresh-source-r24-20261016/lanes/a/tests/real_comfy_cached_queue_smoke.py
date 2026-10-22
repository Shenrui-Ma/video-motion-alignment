"""Real cached ModelPatcher four-job isolation, CPU only; not neural Euler evidence."""
import argparse,hashlib,json,os,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

def main():
 p=argparse.ArgumentParser();p.add_argument('--core',required=True,type=Path);a=p.parse_args();root=Path(__file__).resolve().parents[1]
 os.environ['CUDA_VISIBLE_DEVICES']='';sys.path[:0]=[str(root/'extensions'),str(root/'scripts'),str(root/'tests'),str(a.core),str(a.core.parent/'runtime_deps')];sys.argv=['r24-cpu-cached-four']
 from compatibility_bootstrap import install
 install()
 import torch
 torch.set_num_threads(1)
 import comfy.cli_args
 comfy.cli_args.args.cpu=True;comfy.cli_args.args.disable_xformers=True;comfy.cli_args.args.use_pytorch_cross_attention=True
 import comfy.ldm.minimax.model as h3
 from comfy.ldm.modules.attention import attention_pytorch,AttentionTensorContainer
 from comfy.model_patcher import ModelPatcher
 from comfy.patcher_extension import WrappersMP
 from comfy.nested_tensor import NestedTensor
 from comfy.utils import unpack_latents
 import H3TemporalRouter as node
 from H3TemporalRouter import core
 import H3X0Readout as xnode
 from H3X0Readout.core import CaptureConfig
 from H3EventAudit import CachedNoise
 import r24_contract as c
 from test_contract import fixture
 from bind_cases import bind_case
 model=h3.MiniMaxH3Model(num_attention_heads=56,device='meta',dtype=torch.float32,operations=torch.nn)
 container=torch.nn.Module();container.diffusion_model=model;base=ModelPatcher(container,torch.device('cpu'),torch.device('cpu'))
 refs=[]
 for kind,shape in [('image',(1,24,1,76,50)),('video',(1,24,42,46,82))]:
  refs.append(dict(kind=kind,latent=torch.empty(shape,device='meta'),latent_t=shape[2],latent_h=shape[3],latent_w=shape[4],ref_audio_t=0))
 positive=[[torch.empty((1,6960,5120),device='meta'),{'minimax_refs':refs}]]
 gen=torch.Generator().manual_seed(20);q,k,v=[torch.randn(1,56,29,128,generator=gen) for _ in range(3)];before=[x.clone() for x in (q,k,v)]
 plan={'reference_video_segment':[3,15],'query_interval_half_open':[20,26],'latent_interval_half_open':[1,3],'frame_rows':3,'seq_len':29}
 route=core.route_attention
 def dense(q,k,v):
  z=q@k.transpose(-1,-2)/(q.shape[-1]**.5);return z.softmax(-1)@v,z.logsumexp(-1)
 def cpu_route(*args,**kw):return route(*args,**kw,attention=dense)
 native=cpu_route(q,k,v,56,plan,mode='native');full=cpu_route(q,k,v,56,plan,mode='mass_preserve')
 reports=[];states=[];recorders=[];noises=[]
 with tempfile.TemporaryDirectory(prefix='r24-cpu-') as folder:
  work=Path(folder);lane=work/'lane'
  with patch('bind_cases.video_probe',return_value={'nb_read_frames':'141','avg_frame_rate':'24/1'}):bind_case(fixture(work),lane,root)
  c.ROOT=lane
  # Default argument ROOT bindings are module-load constants; production lanes import their own path.
  original_validate=c.validate_job
  def validate(run,root=None):return original_validate(run,lane if root is None else root)
  with patch.object(c,'validate_job',side_effect=validate):
   for run,row in c.registry(lane)[0].items():
    g=c.read(lane/'configs/graphs'/f'{run}.json');ctor=node.RouterState
    def temp_state(*args,**kw):
     args=list(args);args[12]=str(work/'router');return ctor(*args,**kw)
    args={k:v for k,v in g['50']['inputs'].items() if k not in ('model','positive')}
    with patch.object(node,'RouterState',side_effect=temp_state):routed=node.H3TemporalRouter().apply(base,positive,**args)[0]
    outargs={k:v for k,v in g['52']['inputs'].items() if k!='model'}
    final=xnode.H3X0Readout().apply(routed,**outargs)[0]
    patches=final.model_options['transformer_options']['patches_replace']['dit'];state=patches[('double_block',0)].state;states.append(state)
    recorder=final.get_wrappers(WrappersMP.SAMPLER_SAMPLE,'H3X0Readout/passive-v1')[0];recorders.append(recorder)
    assert state.audit['completed_calls']==0 and state.audit['completed_forward_calls']==0
    state.plan_for=lambda _:plan;layout=object()
    def original(values):return attention_pytorch(*(AttentionTensorContainer(x) for x in (q,k,v)),56,mask=None,skip_reshape=True,transformer_options=values['transformer_options'])
    with patch.object(core,'route_attention',side_effect=cpu_route),patch.object(core,'temporal_readout',return_value={}):
     for index in range(20):
      for b in range(50):
       options={'block_index':b,'minimax_h3_layout':layout,'sample_sigmas':torch.linspace(1,0,21)}
       out=patches[('double_block',b)]({'layout':layout,'transformer_options':options},{'original_block':original})
       assert torch.equal(out,full if row['arm']=='full_6to14' and 6<=index<15 else native)
       assert 'optimized_attention_override' not in options
    assert state.audit['completed_calls']==1000 and state.audit['completed_forward_calls']==20
    assert state.audit['routed_calls']==(450 if row['arm']=='full_6to14' else 0)
    # Production recorder from real clone, executed with small CPU shapes. No model weights or neural sampler.
    recorder.config=CaptureConfig(run,str(work/'x0'),32,32,5);shapes=recorder.config.shapes
    model_stub=SimpleNamespace(latent_shapes=shapes,latent_format=SimpleNamespace(scale_factor=1.),audio_scale=lambda:4.,process_latent_out=lambda z:NestedTensor([z.unbind()[0],z.unbind()[1]/4]))
    sample=NestedTensor([torch.zeros(s) for s in shapes]);pair=g['6']['inputs']['pair_id'];noise=CachedNoise(row['seed'],work,run,pair).generate_noise({'samples':sample});noises.append([t.clone() for t in noise.unbind()]);packed=torch.cat([t.reshape(1,1,-1) for t in noise.unbind()],dim=-1)
    def sample_euler():pass
    class Executor:
     class_obj=SimpleNamespace(sampler_function=sample_euler,extra_options={})
     def __call__(self,m,s,args,cb,n,*rest):
      for i in range(20):cb(i,packed,packed,20)
      return packed
    rng=torch.get_rng_state().clone();result=recorder(Executor(),SimpleNamespace(inner_model=model_stub),torch.linspace(1,0,21),{'seed':row['seed']},None,packed)
    assert result is packed and torch.equal(rng,torch.get_rng_state())
    manifest=c.read(work/'x0'/run/'manifest.json');assert manifest['callback_count']==20 and manifest['status']=='complete'
    reports.append({'run':run,'seed':row['seed'],'arm':row['arm'],'blocks':1000,'forward_calls':20,'routed':state.audit['routed_calls'],'passive_callbacks':20})
  assert len({id(s) for s in states})==4 and len({id(s) for s in recorders})==4
  for a1,b1 in [(0,1),(2,3)]:assert all(torch.equal(a,b) for a,b in zip(noises[a1],noises[b1]))
  assert all(not torch.equal(a,b) for a,b in zip(noises[0],noises[2]))
 assert not base.model_options.get('transformer_options',{}).get('patches_replace',{}).get('dit')
 assert not base.get_wrappers(WrappersMP.SAMPLER_SAMPLE,'H3X0Readout/passive-v1')
 assert all(torch.equal(a,b) for a,b in zip(before,(q,k,v))) and not torch.cuda.is_initialized()
 print('R24_CACHED_QUEUE_CPU='+json.dumps({'passed':True,'CUDA_initialized':False,'cached_base_unmodified':True,'four_distinct_router_states':True,'four_distinct_readout_instances':True,'same_seed_pair_noise_equal':True,'different_seed_AV_noise_different':True,'runs':reports,'scope':'real H3 meta/ModelPatcher/attention and passive wrapper; manual20x50CPU blockcalls and synthetic20callbacks, not actual Euler integration or GPU inference','h3_sha256':hashlib.sha256(Path(h3.__file__).read_bytes()).hexdigest()}))
if __name__=='__main__':main()
