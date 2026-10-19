"""Root-only two-prediction capacity probe; always stops before an Euler update."""
import json,os,time
from pathlib import Path
class CapacityProbeComplete(RuntimeError):pass

def require(ok,message):
 if not ok:raise ValueError(message)
def read(p):return json.loads(Path(p).read_text())
def save(p,x):
 with Path(p).open('x') as f:json.dump(x,f,indent=2)
def memory(torch,device,patcher):
 torch.cuda.synchronize(device);free,total=torch.cuda.mem_get_info(device)
 return {'allocated_bytes':torch.cuda.memory_allocated(device),'reserved_bytes':torch.cuda.memory_reserved(device),
         'driver_free_bytes':free,'driver_total_bytes':total,'loaded_weight_bytes':patcher.loaded_size(),
         'model_weight_bytes':patcher.model_size(),'lowvram_patch_count':patcher.lowvram_patch_counter(),
         'lifetime_max_reserved_bytes':torch.cuda.max_memory_reserved(device)}

class Probe:
 def __init__(self,state,patcher,cfg):
  self.state=state;self.patcher=patcher;self.cfg=cfg;self.started=False;self.ready=False
  self.report={'schema':'r69-two-prediction-capacity-v1','status':'prepared','inference_complete':False,'Euler_updates':0,'configuration':cfg,'forwards':[]}
 def sampler(self,executor,model_wrap,sigmas,extra_args,callback,noise,latent_image=None,denoise_mask=None,disable_pbar=False):
  from H3X0Readout.core import tensor_signature
  require(getattr(executor.class_obj.sampler_function,'__name__',None)=='sample_euler','requires original Euler')
  old=read(self.cfg['parent_capture'])
  require(sigmas.detach().cpu().double().tolist()==old['sigmas_video'] and extra_args['seed']==old['seed'],'original20-step grid/seed changed')
  require(tensor_signature(noise)==old['noise'],'original actual packed initial noise changed')
  self.ready=True;self.report.update(initial_noise_equal_R54=True,full_sigmas=old['sigmas_video'],seed=old['seed'])
  return executor(model_wrap,sigmas,extra_args,callback,noise,latent_image,denoise_mask,disable_pbar)
 def __call__(self,executor,x,timestep,model_options=None,seed=None):
  import torch
  from H3X0Readout.core import tensor_signature
  from probe_guards import condition_signature,rng_state,assert_rng
  require(self.ready and not self.started,'probe must enter first prediction once');self.started=True
  require(x.device.type=='cuda','requires actual CUDA input')
  self.report.update(pid=os.getpid(),device_name=torch.cuda.get_device_name(x.device),before_first_forward=memory(torch,x.device,self.patcher))
  original=tensor_signature(x);sigma=timestep.detach().cpu().clone();cond=condition_signature(executor.class_obj);rng=rng_state(x.device)
  previous=[]
  try:
   for branch in ('native','forced'):
    self.state.mode='native' if branch=='native' else 'mass_preserve'
    before=memory(torch,x.device,self.patcher);torch.cuda.reset_peak_memory_stats(x.device);start=time.perf_counter()
    output=executor(x,timestep,model_options,seed)
    torch.cuda.synchronize(x.device);peak_reserved=torch.cuda.max_memory_reserved(x.device);peak_allocated=torch.cuda.max_memory_allocated(x.device)
    row={'branch':branch,'seconds':time.perf_counter()-start,'before':before,'after':memory(torch,x.device,self.patcher),'peak_reserved_bytes':peak_reserved,'peak_allocated_bytes':peak_allocated}
    summary=self.state.audit['forward_summaries'][-1]
    require(summary['completed_blocks']==50 and summary['routed_blocks']==(50 if branch=='forced' else 0),'actual 50-layer route differs')
    require(self.state.plan['latent_interval_half_open']==[0,27],'requires all27 bins')
    require(bool(torch.isfinite(output).all()),'prediction nonfinite')
    require(tensor_signature(x)==original and torch.equal(timestep.detach().cpu(),sigma) and condition_signature(executor.class_obj)==cond,'same-state input/sigma/conditioning changed')
    assert_rng(rng,x.device)
    row.update(completed_blocks=50,routed_blocks=50 if branch=='forced' else 0,finite=True,same_state=True,global_rng_unchanged=True,endpoint_signature=tensor_signature(output))
    self.report['forwards'].append(row);previous.append(output)
   self.report.update(status='pass',model_forward_calls=2,same_state_verified=True,actual_plan=self.state.plan,paired_fresh_Native_required=True,whole_trajectory_capacity_proven=False)
   save(Path(self.cfg['run_root'])/'audit/capacity_complete.json',self.report)
  except BaseException as error:
   self.report.update(status='failed',error=type(error).__name__+': '+str(error))
   try:self.report['failure_memory']=memory(torch,x.device,self.patcher)
   except BaseException:pass
   save(Path(self.cfg['run_root'])/'audit/capacity_failure.json',self.report);raise
  finally:self.state.mode='native'
  raise CapacityProbeComplete('Two predictions complete; intentional stop before Euler update/decode')

class H3CapacityProbe:
 @classmethod
 def INPUT_TYPES(cls):return {'required':{'model':('MODEL',),'config_file':('STRING',)}}
 RETURN_TYPES=('MODEL',);FUNCTION='apply';CATEGORY='research/capacity'
 def apply(self,model,config_file):
  from comfy.patcher_extension import WrappersMP
  from r69_contract import sha
  cfg=read(config_file)
  for path,digest in cfg['bound_files'].items():require(sha(path)==digest,'capacity dependency changed: '+path)
  patches=model.model_options['transformer_options']['patches_replace']['dit'];require(len(patches)==50,'requires50 router blocks');state=patches['double_block',0].state
  require(state.mode=='native' and state.step_start==0 and state.step_end==20,'capacity initial router differs')
  require(not model.get_all_wrappers(WrappersMP.PREDICT_NOISE),'prediction wrapper already present')
  cloned=model.clone();probe=Probe(state,cloned,cfg)
  cloned.add_wrapper_with_key(WrappersMP.SAMPLER_SAMPLE,'r69-capacity',probe.sampler)
  cloned.add_wrapper_with_key(WrappersMP.PREDICT_NOISE,'r69-capacity',probe)
  return (cloned,)
NODE_CLASS_MAPPINGS={'H3CapacityProbe':H3CapacityProbe}
