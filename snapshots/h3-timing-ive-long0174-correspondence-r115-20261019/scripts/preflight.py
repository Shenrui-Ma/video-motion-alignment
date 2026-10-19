"""CPU-only graph, kernel and deployment checks."""
import argparse,json
from pathlib import Path
from r115_contract import ROOT,read,sha,require,registry,validate_job,GEOMETRY

def check(root=ROOT,live=False):
 root=Path(root);s=read(root/'configs/scientific_contract.json');jobs,order=registry(root);rt=read(root/'configs/runtime.json')
 require(s['geometry']==GEOMETRY and s['NFE_per_job']==s['callback_count']==20 and s['online_observer'] is False,'shape/count changed')
 require(s['router']==dict(mode='case.arm',alpha=1.,blocks=[0,50],steps=[6,15],physical_frames='0..valid-1 per source',routed_calls=450),'route changed')
 require(s['continuous']['job_timeout_seconds']==14400 and s['continuous']['max_service_seconds']==32400 and s['continuous']['idle_hold_seconds']==300,'lifetime changed')
 for run in order:validate_job(run,root)
 for rel,d in read(root/'configs/input_hashes.json').items():require(sha(root/'inputs'/rel)==d,'input bytes changed')
 for rel,row in read(root/'configs/runtime_kernel_hashes.json').items():require(sha(root/rel)==row['current_sha256']==row['parent_sha256']==sha(root/row['source_file']) and row['byte_equal'],'frozen R112 numerical code changed: '+rel)
 require(rt['reserve_vram']==8 and rt['memory_mode']=='normal','memory profile changed')
 if live:
  from execution_gate import verify_seal,approval,atomic
  verify_seal(root);approval(root)
  from check_storage import check as storage
  atomic(root/'audit/STORAGE_STARTUP.json',storage(root))
  require(root.resolve()==Path(rt['remote_root']),'remote root required')
  import service;service.main_memory_profile()
  require(read(root/'configs/admission.json')['ready_for_launch'] is True,'admission pending')
  for rel,d in read(root/'configs/parent_core_hashes.json').items():require(sha(Path(rt['core'])/rel)==d,'actual H3 core changed')
 return {'passed':True,'jobs':order,'NFE_per_job':20,'routed_calls_per_job':450,'launch_admitted':live}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');a=p.parse_args();print(json.dumps(check(live=a.live),indent=2))
