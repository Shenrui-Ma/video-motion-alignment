"""CPU contracts and actual runtime validation. No CUDA invocation."""
import argparse,json
from pathlib import Path
from r113_contract import ROOT,read,sha,require,registry,validate_job,GEOMETRY

def check(root=ROOT,live=False):
 root=Path(root);s=read(root/'configs/scientific_contract.json');jobs,order=registry(root);runtime=read(root/'configs/runtime.json')
 require(s['geometry']==GEOMETRY and s['NFE_per_job']==s['callback_count']==20 and s['online_observer'] is False,'geometry/count changed')
 require(s['router']==dict(mode_by_arm={'native':'native','fixed':'mass_preserve'},alpha=1.,blocks=[0,50],steps=[6,15],physical_frames=[0,97],routed_calls={'native':0,'fixed':450}),'fixed route changed')
 require(s['continuous']['job_timeout_seconds']==14400 and s['continuous']['max_service_seconds']==64800,'bounded four-run lifetime changed')
 for run in order:validate_job(run,root)
 for path,digest in read(root/'configs/input_hashes.json').items():require(sha(root/'inputs'/path)==digest,'original input bytes changed')
 for path,row in read(root/'configs/runtime_kernel_hashes.json').items():require(sha(root/path)==row['current_sha256']==row['parent_sha256'] and row['byte_equal'],'unchanged numerical kernel differs')
 binding=read(root/'configs/readout_revision.json');require(sha(root/'extensions/H3X0Readout/core.py')==binding['current_sha256'],'passive readout revision changed')
 require(runtime['reserve_vram']==8 and runtime['memory_mode']=='normal','memory profile differs')
 if live:
  from check_storage import check as check_storage
  from execution_gate import atomic
  atomic(root/'audit/STORAGE_STARTUP.json',check_storage(root))
  require(root.resolve()==Path(runtime['remote_root']),'actual remote root required')
  import service
  service.main_memory_profile()
  require(read(root/'configs/admission.json')['ready_for_launch'] is True,'root live admission pending')
  for path,row in read(root/'deploy_manifest.json')['files'].items():require(sha(root/path)==row['sha256'],'sealed file changed: '+path)
  for path,digest in read(root/'configs/parent_core_hashes.json').items():require(sha(Path(runtime['core'])/path)==digest,'actual Comfy core differs')
 return {'passed':True,'jobs':order,'NFE':20,'solver_updates_per_run':20,'routed_calls':{'native':0,'fixed':450},'online_observations':0,'launch_admitted':live}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');a=p.parse_args();print(json.dumps(check(live=a.live),indent=2))
