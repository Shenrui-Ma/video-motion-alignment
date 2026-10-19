"""Audited two-forward capacity experiment. It ends with a controlled exception."""
import importlib,json,os,time
from pathlib import Path
from .contract import sha,read,require,write_new,clean

class CapacityProbeComplete(RuntimeError):pass

def memory(torch,device,patcher):
 torch.cuda.synchronize(device);free,total=torch.cuda.mem_get_info(device)
 allocated=torch.cuda.memory_allocated(device);reserved=torch.cuda.memory_reserved(device)
 return {'allocated_bytes':allocated,'reserved_bytes':reserved,'reserved_minus_allocated_bytes':reserved-allocated,'driver_free_bytes':free,'driver_total_bytes':total,'loaded_weight_bytes':patcher.loaded_size(),'model_weight_bytes':patcher.model_size(),'lowvram_patch_count':patcher.lowvram_patch_counter(),'lifetime_max_allocated_bytes':torch.cuda.max_memory_allocated(device),'lifetime_max_reserved_bytes':torch.cuda.max_memory_reserved(device)}

class Probe:
 def __init__(self,state,patcher,cfg):self.state=state;self.patcher=patcher;self.cfg=cfg;self.started=False;self.sampler_ready=False;self.record={'schema':'h3-main-capacity-probe-v1','status':'prepared','inference_complete':False,'model_forward_calls':0,'forwards':[],'configuration':cfg}
 def sampler(self,executor,model_wrap,sigmas,extra_args,callback,noise,latent_image=None,denoise_mask=None,disable_pbar=False):
  import torch
  from H3X0Readout.core import tensor_signature
  require(not self.sampler_ready,'probe single-use')
  require(getattr(executor.class_obj.sampler_function,'__name__',None)=='sample_euler','Euler differs')
  cap=read(self.cfg['parent_manifest']);require(sigmas.detach().cpu().double().tolist()==cap['sigmas_video'],'full sigma grid differs')
  require(extra_args['seed']==cap['seed'] and tensor_signature(noise)==cap['noise'],'actual initial noise differs')
  self.record['noise_exact']=True;self.record['seed']=cap['seed'];self.record['full_sigmas']=cap['sigmas_video'];self.sampler_ready=True
  return executor(model_wrap,sigmas,extra_args,callback,noise,latent_image,denoise_mask,disable_pbar)
 def __call__(self,executor,x,timestep,model_options=None,seed=None):
  import torch
  from comfy.utils import unpack_latents
  from comfy.nested_tensor import NestedTensor
  from H3X0Readout.core import tensor_signature,split_streams
  from H3AutomaticWindowRouter.core import condition_signature,rng_state,assert_rng
  import comfy.cli_args
  require(not self.started and self.sampler_ready,'probe must enter first prediction once');self.started=True
  require(float(comfy.cli_args.args.reserve_vram)==8.0,'requires exact reserve-vram8GiB')
  require(x.device.type=='cuda' and x.dtype==torch.float32,'actual CUDA fp32 sampler input required')
  model=executor.class_obj.inner_model;shapes=tuple(tuple(v) for v in model.latent_shapes)
  require(shapes==((1,24,27,46,82),(1,32,2,150)),'full90 latent geometry differs')
  cap=read(self.cfg['parent_manifest']);require(seed==cap['seed'] and float(timestep.detach().cpu().reshape(()))==cap['sigmas_video'][0],'first sigma/seed differs')
  require(float(model.audio_scale())==4.0 and model.latent_format.scale_factor==1.0,'normalization differs')
  old=read(self.cfg['parent_conditioning']);current=read(Path(self.cfg['run_root'])/'audit/capacity_native_full_reserve8_conditioning.json')
  for key in ('prompt','input_video','native_vae_calls','qwen_presentation','tokenization_before_vision_expansion','conditioning_embedding','token_tags','target_latent_shapes','packed_layout'):
   require(clean(current[key])==clean(old[key]),'actual conditioning differs: '+key)
  self.record['condition_exact']=True;self.record['input_signature']=tensor_signature(x);self.record['condition_signature']=condition_signature(executor.class_obj)
  rng=rng_state(x.device);input_signature=tensor_signature(x);sigma=timestep.detach().cpu().clone();held=[]
  # First real forward starts after official Comfy loading/offload decisions.
  first_input=Path(self.cfg['run_root'])/'audit/first_input_raw.pt'
  require(not first_input.exists(),'first input already archived')
  torch.save({'packed':x.detach().to('cpu',copy=True).contiguous(),'seed':seed,'sigma':sigma,'signature':input_signature},first_input)
  self.record['first_input']={'file':str(first_input),'sha256':sha(first_input),'scope':'actual official Euler step0 packed input before any probe forward'}
  self.record['before_first_forward']=memory(torch,x.device,self.patcher)
  self.record['torch_version']=str(torch.__version__);self.record['cuda_device']=torch.cuda.get_device_name(x.device);self.record['pid']=os.getpid();self.record['reserve_vram_GiB']=8
  try:
   for branch in ('native','full27'):
    self.state.mode='native' if branch=='native' else 'mass_preserve'
    if branch=='full27':
     mask_module=importlib.import_module(self.state.__class__.__module__.rsplit('.',1)[0]+'.mask')
     self.state.query_gain=mask_module.QueryGain(torch.ones((27,23,41),dtype=torch.float32,device='cpu'),expected_shape=(27,23,41))
    else:self.state.query_gain=None
    before=memory(torch,x.device,self.patcher);torch.cuda.reset_peak_memory_stats(x.device);started=time.perf_counter()
    output=executor(x,timestep,model_options,seed)
    torch.cuda.synchronize(x.device);elapsed=time.perf_counter()-started
    # Capture peaks immediately at call boundary before CPU equality/finite checks.
    peak_allocated=torch.cuda.max_memory_allocated(x.device);peak_reserved=torch.cuda.max_memory_reserved(x.device);after=memory(torch,x.device,self.patcher)
    self.record['model_forward_calls']+=1
    summary=self.state.audit['forward_summaries'][-1]
    self.record['forwards'].append({'branch':branch,'before':before,'after':after,'peak_allocated_bytes':peak_allocated,'peak_reserved_bytes':peak_reserved,'peak_allocated_above_entry_bytes':peak_allocated-before['allocated_bytes'],'peak_reserved_above_entry_bytes':peak_reserved-before['reserved_bytes'],'seconds_synchronized':elapsed,'completed_blocks':summary['completed_blocks'],'routed_blocks':summary['routed_blocks'],'actual_plan':self.state.plan,'first_attention':self.state.audit.get('first_attention')})
    require(self.state.plan['seq_len']==self.cfg['seq_len'] and self.state.plan['latent_interval_half_open']==[0,27],'actual largest full27 layout differs')
    require(summary['completed_blocks']==50 and summary['routed_blocks']==(50 if branch=='full27' else 0),'actual branch execution differs')
    assert_rng(rng,x.device)
    require(tensor_signature(x)==input_signature and torch.equal(timestep.detach().cpu(),sigma) and condition_signature(executor.class_obj)==self.record['condition_signature'],'branch input/condition changed')
    raw=[v.detach().to('cpu',copy=True).contiguous() for v in split_streams(output,shapes,unpack_latents)]
    with torch.no_grad():ready=list(model.process_latent_out(NestedTensor(raw)).unbind())
    require(torch.equal(ready[0],raw[0]) and torch.equal(ready[1],raw[1]*.25),'official normalization differs')
    require(all(bool(torch.isfinite(v).all()) for v in ready),'nonfinite endpoint')
    self.record['forwards'][-1]['endpoint_signatures']=[tensor_signature(v) for v in ready]
    if branch=='native':
     expected=torch.load(self.cfg['parent_step0'],map_location='cpu',weights_only=True)
     require(sha(self.cfg['parent_step0'])==self.cfg['parent_step0_sha256'],'historical endpoint changed')
     require(all(torch.equal(ready[i],expected[k]) for i,k in enumerate(('video','audio'))),'reserve8 Native first endpoint differs from R54')
     first=next(v for v in cap['captures'] if v['step_zero_based']==0)
     require([tensor_signature(v) for v in ready]==[first['video'],first['audio']],'Native first endpoint signature differs')
     self.record['native_exact']=True
    held.append(output)  # Native stays live while Full executes, matching two-branch residency.
   self.record.update(status='capacity_measured_controlled_stop',controlled_stop=True,interpretation='Two same-state forward capacity measurements; no completed video inference; no whole-trajectory peak claim',safety_margin_bytes=None)
   write_new(Path(self.cfg['run_root'])/'audit/capacity_complete.json',self.record)
  except BaseException as error:
   self.record.update(status='failed',error=type(error).__name__+': '+str(error))
   try:self.record['failure_allocator']=memory(torch,x.device,self.patcher)
   except BaseException as memory_error:self.record['failure_allocator_error']=repr(memory_error)
   write_new(Path(self.cfg['run_root'])/'audit/capacity_failure.json',self.record);raise
  finally:self.state.mode='native'
  raise CapacityProbeComplete('Capacity measured; stop before Euler update and video decoding')

class H3MainCapacityProbe:
 @classmethod
 def INPUT_TYPES(cls):return {'required':{'model':('MODEL',),'config_file':('STRING',)}}
 RETURN_TYPES=('MODEL',);FUNCTION='apply';CATEGORY='research/capacity'
 def apply(self,model,config_file):
  from comfy.patcher_extension import WrappersMP
  cfg=read(config_file)
  for path,digest in cfg['bound_files'].items():require(sha(path)==digest,'probe binding changed: '+path)
  patches=model.model_options['transformer_options']['patches_replace']['dit'];require(len(patches)==50,'requires original50block router')
  state=patches['double_block',0].state
  require(all(patches['double_block',i].state is state for i in range(50)),'router state differs')
  require(state.mode=='native' and (state.start_frame,state.end_frame,state.block_start,state.block_end,state.step_start,state.step_end)==(0,89,0,50,0,20),'original full90 router bounds differ')
  require(not model.get_all_wrappers(WrappersMP.PREDICT_NOISE),'unexpected prediction wrapper')
  cloned=model.clone();probe=Probe(state,cloned,cfg)
  cloned.add_wrapper_with_key(WrappersMP.SAMPLER_SAMPLE,'capacity_probe',probe.sampler)
  cloned.add_wrapper_with_key(WrappersMP.PREDICT_NOISE,'capacity_probe',probe)
  return (cloned,)
NODE_CLASS_MAPPINGS={'H3MainCapacityProbe':H3MainCapacityProbe}
