"""CPU-only actual R73 metadata/noise binding. Hash frozen parent payloads in place."""
import argparse,json,os,shutil,time
from pathlib import Path
from r86_contract import ROOT,RUN,read,sha,require,registry
from execution_gate import atomic

def walk_tensor_files(value):
 if isinstance(value,dict):
  if 'tensor_file' in value:yield 'audit/'+value['tensor_file']
  for v in value.values():yield from walk_tensor_files(v)
 elif isinstance(value,list):
  for v in value:yield from walk_tensor_files(v)

def verify_file(path,digest,size=None):
 require(path.is_file() and not path.is_symlink(),'parent file absent/symlink: '+str(path))
 if size is not None:require(path.stat().st_size==size,'parent size differs: '+str(path))
 require(sha(path)==digest,'parent bytes differ: '+str(path))
 return {'sha256':digest,'bytes':path.stat().st_size}

def materialize(root=ROOT):
 root=Path(root);registry(root);p=read(root/'configs/protocol.json');c=p['cases'][0];parent=Path(c['parent_root']);gate=read(root/'configs/PARENT_PAIR_GATE.json')
 require(root.resolve()==Path(read(root/'configs/runtime.json')['remote_root']),'exact remote root required')
 require(not read(root/'configs/PARENT_CLOSURE.json').get('ready'),'parent already materialized')
 require(gate['passed'] is True and all(gate['checks'].values()),'historical parent gate failed')
 native=gate['runs']['native'];require(native['run_id']==c['parent_run'] and native['NFE']==native['solver_updates']==20,'parent identity/count differs')
 folder=root/'prepared_parent';require(not list(folder.iterdir()),'refuse partial/previous parent materialization')
 captures=read(root/'configs/PARENT_CAPTURES.json');run=c['parent_run'];inventory={}
 for row in native['snapshots']:
  path=Path(row['file']);require(path.is_relative_to(parent),'snapshot outside fixed parent')
  rel=str(path.relative_to(parent));inventory[rel]=verify_file(path,row['sha256'],row['bytes'])
 expected={f'audit/x0/{run}/'+row['file'] for row in captures['captures']+[captures['final_sampler_result']]}
 require(expected<=set(inventory) and len(expected)==21 and len(inventory)==23,'actual normalized21 and rawprefix2 inventory differs')
 condition_path=parent/'audit'/f'{run}_conditioning.json';condition=read(condition_path)
 require(condition['run_id']==run and condition['prompt']==c['prompt'],'actual parent condition/prompt differs')
 tensor_set=set(walk_tensor_files(condition));bound={str(Path(x['file']).relative_to(parent)):x for x in gate['condition_tensor_files']}
 require(tensor_set==set(bound) and len(bound)==6,'six actual clean condition payloads differ')
 for rel,row in bound.items():inventory[rel]=verify_file(parent/rel,row['sha256'])
 for suffix,expected_sha in [('history',native['history_sha256']),('job',native['job_sha256'])]:
  rel=f'logs/{run}_{suffix}.json';inventory[rel]=verify_file(parent/rel,expected_sha)
 history=read(parent/'logs'/f'{run}_history.json');require(history['status']['completed'] is True and history['status']['status_str']=='success','parent history unsuccessful')
 require(history['prompt'][2]==read(root/'configs/PARENT_GRAPH.json'),'actual parent graph differs')
 for name,rel in [('conditioning.json',f'audit/{run}_conditioning.json'),('noise.json',f'audit/{run}_noise.json')]:
  source=parent/rel;require(source.is_file() and not source.is_symlink(),'parent metadata absent');shutil.copyfile(source,folder/name);inventory[rel]={'sha256':sha(source),'bytes':source.stat().st_size}
 noise=read(folder/'noise.json');cache=Path(noise['cache_file']);require(cache.is_relative_to(parent/'audit') and cache.name=='r113_short_0252_seed2026101703_noise.pt','noise origin differs')
 # Recompute actual cached tensor signatures on CPU; no CUDA initialization.
 import torch
 torch.set_num_threads(4);saved=torch.load(cache,map_location='cpu',weights_only=True)
 require(saved['signature']==noise['signature'] and noise['signature']['seed']==c['seed'],'actual noise signature differs')
 import sys;sys.path.insert(0,str(root/'extensions'))
 from H3X0Readout.core import tensor_signature
 actual=[{k:v for k,v in tensor_signature(v).items() if k in ('shape','dtype','sha256')} for v in saved['tensors']]
 require(actual==noise['actual_noise_streams'],'actual cached noise bytes differ')
 require(not torch.cuda.is_initialized(),'CPU materialization initialized CUDA')
 rel=str(cache.relative_to(parent));inventory[rel]={'sha256':sha(cache),'bytes':cache.stat().st_size}
 dest=root/'audit'/cache.name;require(not dest.exists(),'noise destination already exists');shutil.copyfile(cache,dest);verify_file(dest,inventory[rel]['sha256'],inventory[rel]['bytes'])
 atomic(folder/'FILE_INVENTORY.json',inventory)
 required=['prepared_parent/conditioning.json','prepared_parent/noise.json','prepared_parent/FILE_INVENTORY.json','configs/PARENT_CAPTURES.json','configs/PARENT_PAIR_GATE.json',c['source_pose_path']]
 closure={'schema':'r86-actual-parent-closure-v1','ready':True,'status':'READY','cases':{c['source_id']:{'ready':True,'parent_run':run,'required_actual_files':required,'actual_file_sha256':{r:sha(root/r) for r in required}}},'created_unix':time.time(),'noise_copy':{'file':str(dest),'sha256':sha(dest)},'GPU_launch_authorized':False}
 atomic(root/'configs/PARENT_CLOSURE.json',closure)
 # Local science/admin bytes are frozen separately; bind closure and independent external sources.
 bindings=read(root/'configs/observer_external_bindings.json');seal=read(root/'deploy_manifest.json')
 bindings['local_files']={r:v['sha256'] for r,v in seal['files'].items() if r.startswith(('scripts/','extensions/','configs/'))}
 bindings['local_files']['configs/PARENT_CLOSURE.json']=sha(root/'configs/PARENT_CLOSURE.json')
 atomic(root/'configs/observer_bindings.json',bindings)
 atomic(root/'audit/PARENT_MATERIALIZED.json',{'passed':True,'parent_gate_sha256':sha(root/'configs/PARENT_PAIR_GATE.json'),'closure_sha256':sha(root/'configs/PARENT_CLOSURE.json'),'bindings_sha256':sha(root/'configs/observer_bindings.json'),'parent_tensor_files':len(tensor_set)+21+1,'torch_cuda_initialized':False})
 return closure
if __name__=='__main__':print(json.dumps(materialize(),indent=2))
