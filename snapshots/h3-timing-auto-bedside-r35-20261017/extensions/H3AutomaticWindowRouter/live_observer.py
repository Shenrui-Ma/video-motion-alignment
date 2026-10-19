"""Isolated full VAE/CPU pose observation; no model operations in this process."""
import os,sys,time,uuid
import torch
from . import transport as t
from .dependencies import readout

def parent_guard(s,x,sigma,native):
 from .core import condition_signature,rng_state
 params=[]
 for category,iterator in [('parameter',getattr(s.model,'named_parameters',lambda:[])()),('buffer',getattr(s.model,'named_buffers',lambda:[])())]:
  for name,value in iterator:
   params.append((category,name,id(value),tuple(value.shape),str(value.dtype),str(value.device),value.data_ptr()))
 patcher=s.guider.model_patcher
 return {'x':readout.tensor_signature(x),'native':readout.tensor_signature(native),'sigma':readout.tensor_signature(sigma),
  'grid':s.grid.tolist(),'actual_sampler_sigmas':readout.tensor_signature(s.original_sigmas),
  'actual_model_sigmas':readout.tensor_signature(s.sample_options['transformer_options']['sample_sigmas']),'conditions':condition_signature(s.guider),'rng':{k:readout.tensor_signature(v) for k,v in rng_state(x.device).items()},
  'model_id':id(s.model),'patcher_id':id(patcher),'params':params,'options_id':id(s.sample_options),
  'patches':[(str(k),id(v)) for k,v in s.sample_options['transformer_options'].get('patches_replace',{}).get('dit',{}).items()],
  'wrappers':[(str(k),str(key),tuple(id(v) for v in values)) for k,groups in s.sample_options['transformer_options'].get('wrappers',{}).items() for key,values in groups.items()],
  'residency':{k:repr(getattr(patcher,k,None)) for k in ('current_device','load_device','offload_device','model_loaded_weight_memory','lowvram_patch_counter')},
  'environment':dict(os.environ),'threads':torch.get_num_threads(),'interop_threads':torch.get_num_interop_threads()}

class LivePoseObserver:
 def __call__(self,s,row):
  t.require(t.ROOT==t.REMOTE_ROOT,'live observer only at admitted remote root')
  t.bindings()
  start=time.monotonic();n=row['physical_index'];request_id=f'step{n:03d}_'+uuid.uuid4().hex
  directory=t.ROOT/'audit/observations'/request_id;directory.mkdir(parents=True,exist_ok=False)
  parent=t.identity(os.getpid());t.require(parent is not None,'cannot bind main process')
  r={'schema':'r27-observer-request-v1','request_id':request_id,'run_id':s.config.run_id,'parent':parent,
   'protocol_sha256':t.PROTOCOL_SHA,'bindings_sha256':t.sha(t.ROOT/'configs/observer_bindings.json'),
   'physical_index':n,'nfe_index':row['nfe_index'],'branch':'native','seed':s.seed,'sigma':row['sigma'],'sigma_next':row['sigma_next'],
   'full_grid':s.grid.tolist(),'condition_sha256':s.initial_condition['sha256'],'reference_sha256':s.reference_signature['sha256'],
   'endpoint_file':row['file'],'endpoint_file_sha256':row['file_sha256'],'normalized_stream_signatures':row['normalized_stream_signatures'],
   'raw_stream_signatures':row['raw_stream_signatures'],'created_unix':time.time()}
  path=directory/'request.json';request_sha=t.write_new(path,r)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')
  process=t.run_child([sys.executable,str(t.ROOT/'scripts/run_observer.py'),'--request',str(path)],env,directory,'observer',1650,parent)
  t.require(t.sha(path)==request_sha and t.sha(row['file'])==row['file_sha256'],'observer altered request/endpoint')
  response_path=directory/'response.json';response=t.validate_response(t.read_json(response_path),r,request_sha)
  t.require(response['status']=='complete' and response['request_sha256']==request_sha and response['request_id']==request_id,'stale/incomplete observer response')
  t.require(response['physical_index']==n and response['nfe_index']==row['nfe_index'] and response['endpoint_file_sha256']==row['file_sha256'],'response endpoint identity')
  outputs={}
  for key in ('observer','pose','decode'):
   record=response[key];p=t.inside(record['file'],directory)
   t.require(t.sha(p)==record['sha256'],'response output changed: '+key);outputs[key]=t.read_json(p)
  observer,pose,decode=outputs['observer'],outputs['pose'],outputs['decode']
  t.require(decode['status']=='complete' and decode['snapshot_sha256']==row['file_sha256'] and decode['fallback_guard']['calls']==0,'invalid decode/fallback')
  t.require(decode['request_sha256']==request_sha and decode['fallback_guard']['installed'],'unbound/unguarded decode')
  t.require(pose['provenance']['providers']==['CPUExecutionProvider'] and pose['provenance']['device']=='cpu' and pose['provenance']['threads']==4,'pose placement')
  t.require(pose['extraction']=={'start':0,'end':None,'stride':1} and len(pose['frames'])==141,'pose full timebase')
  t.require(observer['edited_pose_sha256']==response['pose']['sha256'] and observer['source_pose_sha256']==t.read_json(t.ROOT/'configs/protocol.json')['observer']['source_pose_sha256'],'observer source binding')
  t.require(observer['schema']=='r27-whole-timeline-observation-v1' and observer['physical_index']==n,'current all-time scan identity')
  return {'status':'complete','physical_index':n,'request_sha256':request_sha,'response_sha256':t.sha(response_path),
   'request_file':str(path),'response_file':str(response_path),'observer':observer,'process':process,
   'wall_seconds':time.monotonic()-start,'parent_state_guard_pass':True}
