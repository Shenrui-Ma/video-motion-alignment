"""CPU contracts and actual runtime validation. No CUDA invocation."""
import argparse,json
from pathlib import Path
from r97_contract import ROOT,read,sha,require,registry,validate_job,GEOMETRY

def check(root=ROOT,live=False):
 root=Path(root);s=read(root/'configs/scientific_contract.json');jobs,order=registry(root);runtime=read(root/'configs/runtime.json')
 require(s['geometry']==GEOMETRY and s['NFE_per_job']==s['callback_count']==20 and s['online_observer'] is False,'geometry/count changed')
 require(s['router']==dict(mode='mass_preserve',alpha=1.,blocks=[0,50],steps=[6,20],physical_frames=[0,104],routed_calls=700),'extended route changed')
 require(s['continuous']['job_timeout_seconds']==14400 and s['continuous']['max_service_seconds']==18000,'bounded single-run lifetime changed')
 for run in order:validate_job(run,root)
 for path,digest in read(root/'configs/input_hashes.json').items():require(sha(root/'inputs'/path)==digest,'original input bytes changed')
 for path,row in read(root/'configs/runtime_kernel_hashes.json').items():require(sha(root/path)==row['current_sha256']==row['parent_sha256'] and row['byte_equal'],'R89 numerical kernel changed')
 require(runtime['reserve_vram']==8 and runtime['memory_mode']=='normal','memory profile differs')
 if live:
  from check_storage import check as check_storage
  from execution_gate import atomic
  atomic(root/'audit/STORAGE_STARTUP.json',check_storage(root))
  require(root.resolve()==Path(runtime['remote_root']),'actual remote root required')
  import service
  service.main_memory_profile()
  binding=read(root/'configs/parent_bindings.json');noise=root/'audit/r97_short_0358_seed2026101701_noise.pt'
  require(noise.is_file() and not noise.is_symlink() and sha(noise)==binding['noise_cache_sha256'],'actual original AV noise must be copied before CUDA')
  require(read(root/'configs/admission.json')['ready_for_launch'] is True,'root live admission pending')
  for path,row in read(root/'deploy_manifest.json')['files'].items():require(sha(root/path)==row['sha256'],'sealed file changed: '+path)
  for path,digest in read(root/'configs/parent_core_hashes.json').items():require(sha(Path(runtime['core'])/path)==digest,'actual Comfy core differs')
 return {'passed':True,'jobs':order,'NFE':20,'Euler_updates':20,'routed_calls':700,'online_observations':0,'launch_admitted':live}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');a=p.parse_args();print(json.dumps(check(live=a.live),indent=2))
