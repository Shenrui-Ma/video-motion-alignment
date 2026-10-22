"""CPU and live contracts for the two frozen-bank controls."""
import argparse,json
from pathlib import Path
from r112_contract import ROOT,read,sha,require,registry,validate_job,GEOMETRY,ARMS

def check(root=ROOT,live=False):
 root=Path(root);s=read(root/'configs/scientific_contract.json');jobs,order=registry(root);runtime=read(root/'configs/runtime.json')
 require(s['geometry']==GEOMETRY and s['NFE_per_job']==s['callback_count']==20 and s['online_observer'] is False,'shape/count changed')
 require(s['router']==dict(mode='case.arm',alpha=1.,blocks=[0,50],steps=[6,15],physical_frames='0..valid-1 per source',routed_calls=450),'routing changed')
 require(s['continuous']['job_timeout_seconds']==14400 and s['continuous']['max_service_seconds']==32400 and s['continuous']['idle_hold_seconds']==1800,'bounded lifetimes changed')
 for run in order:validate_job(run,root)
 for path,digest in read(root/'configs/input_hashes.json').items():require(sha(root/'inputs'/path)==digest,'input bytes changed')
 for path,row in read(root/'configs/runtime_kernel_hashes.json').items():require(sha(root/path)==row['current_sha256']==row['parent_sha256'] and row['byte_equal'],'numerical kernel changed')
 require(runtime['reserve_vram']==8 and runtime['memory_mode']=='normal','memory profile changed')
 archived=root/'source_snapshot/cpu_preparation';old=read(archived/'CPU_PREPARATION_SEAL.json')
 require(sha(archived/'CPU_PREPARATION_SEAL.json')==sha(root/'CPU_PREPARATION_SEAL.json'),'CPU source seal changed')
 for rel,row in old['files'].items():require(sha(archived/rel)==row['sha256'],'archived CPU source changed: '+rel)
 if live:
  from execution_gate import atomic,approval,verify_seal
  verify_seal(root);approval(root)
  from check_storage import check as storage
  atomic(root/'audit/STORAGE_STARTUP.json',storage(root));require(root.resolve()==Path(runtime['remote_root']),'actual remote required')
  import service;service.main_memory_profile()
  from fixed_comparison import verify as fixed
  fixed(root,require_released=True)
  for src,b in read(root/'configs/parent_bindings.json').items():
   noise=root/b['new_noise_relative'];require(noise.is_file() and not noise.is_symlink() and sha(noise)==b['noise']['current_file']['sha256'],'original AV noise not materialized')
  require(read(root/'configs/admission.json')['ready_for_launch'] is True,'resource admission pending')
  for path,digest in read(root/'configs/parent_core_hashes.json').items():require(sha(Path(runtime['core'])/path)==digest,'actual Comfy core changed')
 return {'passed':True,'jobs':order,'NFE_per_job':20,'routed_calls_per_job':450,'online_observations':0,'launch_admitted':live}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');a=p.parse_args();print(json.dumps(check(live=a.live),indent=2))
