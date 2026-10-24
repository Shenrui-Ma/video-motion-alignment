"""Native Ref2VA encoding, frozen R150 routing, passive synchronized timing."""
import json,os,re,time
from pathlib import Path
from .core import EventBlockPatch
from .layout import conditioning_metadata
from .schedule import ScheduleState,ScheduleBlockPatch,SCHEDULES

def atomic(path, value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_name(path.name+f'.{os.getpid()}.tmp');tmp.write_text(json.dumps(value,indent=2));os.replace(tmp,path)

class H3StudyReference:
 @classmethod
 def INPUT_TYPES(cls):
  return {'required':{'clip':('CLIP',),'vae':('VAE',),'ref_video':('IMAGE',),'prompt':('STRING',{'multiline':True}),'width':('INT',{'default':1312}),'height':('INT',{'default':736}),'length':('INT',{'default':107})},'optional':{'ref_image':('IMAGE',)}}
 RETURN_TYPES=('CONDITIONING','LATENT');FUNCTION='encode';CATEGORY='research/H3Study'
 def encode(self,clip,vae,ref_video,prompt,width,height,length,ref_image=None):
  from comfy_extras.nodes_minimax_h3 import MiniMaxH3ReferenceToVideo
  r=MiniMaxH3ReferenceToVideo.execute(clip=clip,vae=vae,prompt=prompt,width=width,height=height,length=length,ref_image_size='match',ref_images=None if ref_image is None else {'ref_image_0':ref_image},ref_videos={'ref_video_0':ref_video})
  return r[0],r[1]

class H3StudySchedule:
 @classmethod
 def INPUT_TYPES(cls):
  return {'required':{'model':('MODEL',),'positive':('CONDITIONING',),'schedule':(list(SCHEDULES),),'mode':(['native','mass_preserve'],),'alpha':('FLOAT',{'default':1.,'min':0.,'max':1.}),'radius':('INT',{'default':0}),'time_offset':('INT',{'default':0}),'start_frame':('INT',{'default':0}),'end_frame':('INT',{'default':60}),'block_start':('INT',{'default':0}),'block_end':('INT',{'default':50}),'step_start':('INT',{'default':0}),'step_end':('INT',{'default':20}),'run_id':('STRING',),'audit_dir':('STRING',)}}
 RETURN_TYPES=('MODEL',);FUNCTION='apply';CATEGORY='research/H3Study'
 def apply(self,model,positive,schedule,mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
  import comfy.ldm.minimax.model as h3
  d=model.get_model_object('diffusion_model')
  if not isinstance(d,h3.MiniMaxH3Model) or len(d.blocks)!=50:raise ValueError('Expected H3 50 DiT blocks')
  if tuple(h3.FRAME_PER_TOKEN)!=(1,4,4,4,4):raise ValueError('Changed temporal mapping')
  if getattr(h3.optimized_attention,'__name__',None)!='attention_pytorch':raise ValueError('Require PyTorch attention entry')
  if model.model_options.get('transformer_options',{}).get('patches_replace',{}).get('dit'):raise ValueError('Existing block patch')
  state=ScheduleState(conditioning_metadata(positive),mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir,schedule=schedule)
  c=model.clone()
  for i in range(50):c.set_model_patch_replace(ScheduleBlockPatch(state,i),'dit','double_block',i)
  return (c,)

class Timer:
 def __init__(self,path):self.path=path
 def __call__(self,executor,model_wrap,sigmas,extra_args,callback,noise,latent_image=None,denoise_mask=None,disable_pbar=False):
  import torch
  torch.cuda.synchronize();start=previous=time.perf_counter();steps=[];passed=False
  def cb(step,x0,x,total):
   nonlocal previous
   torch.cuda.synchronize();now=time.perf_counter();steps.append({'step':step+1,'seconds':now-previous});previous=now
   atomic(self.path,{'status':'sampling','steps':steps,'elapsed':now-start})
   if callback is not None:return callback(step,x0,x,total)
  try:
   r=executor(model_wrap,sigmas,extra_args,cb,noise,latent_image,denoise_mask,disable_pbar)
   torch.cuda.synchronize();passed=True;return r
  finally:
   elapsed=time.perf_counter()-start
   atomic(self.path,{'status':'complete' if passed else 'failed','passed':passed,'sampler_wall_seconds':elapsed,'per_step_seconds':[x['seconds'] for x in steps],'steps':steps,'mean_sampling_step_seconds':sum(x['seconds'] for x in steps)/len(steps) if steps else None,'scope':'synchronized KSAMPLER call; excludes model loading, reference encoding, final VAE decoding; first step includes sampler setup','no_intermediate_vae_decode':True})

class H3StudyTiming:
 @classmethod
 def INPUT_TYPES(cls):return {'required':{'model':('MODEL',),'run_id':('STRING',),'output_dir':('STRING',)}}
 RETURN_TYPES=('MODEL',);FUNCTION='apply';CATEGORY='research/H3Study'
 def apply(self,model,run_id,output_dir):
  from comfy.patcher_extension import WrappersMP
  if not re.fullmatch(r'[A-Za-z0-9_.-]+',run_id):raise ValueError('Invalid run id')
  c=model.clone();c.add_wrapper_with_key(WrappersMP.SAMPLER_SAMPLE,'H3StudyTiming',Timer(str(Path(output_dir)/(run_id+'.json'))));return (c,)
NODE_CLASS_MAPPINGS={c.__name__:c for c in [H3StudyReference,H3StudySchedule,H3StudyTiming]}
