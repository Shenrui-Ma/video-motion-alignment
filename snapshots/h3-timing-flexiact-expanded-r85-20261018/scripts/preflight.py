"""CPU contracts; production requires new actual same-profile capacity evidence."""
import argparse,json
from pathlib import Path
from r85_contract import ROOT,read,sha,require,registry,validate_job,GEOMETRY

def check(root=ROOT,live=False):
 root=Path(root);s=read(root/'configs/scientific_contract.json');jobs,order=registry(root);runtime=read(root/'configs/runtime.json')
 require(s['geometry']==GEOMETRY and s['NFE_per_job']==s['callback_count']==20 and s['online_observer'] is False,'geometry/count/observer contract changed')
 require(s['router']=={'mode':'mass_preserve','alpha':1.0,'blocks':[0,50],'steps':[6,15],'physical_frames':[0,146],'query_support':'all44 temporal bins overlapping valid physical frames; all spatial queries'},'fixed scientific route changed')
 for path,digest in read(root/'configs/source_selection_hashes.json').items():require(sha(root/path)==digest,'source selection evidence changed')
 for run in order:validate_job(run,root)
 for path,digest in read(root/'configs/input_hashes.json').items():require(sha(root/'inputs'/path)==digest,'original input bytes changed')
 for path,row in read(root/'configs/runtime_kernel_hashes.json').items():require(sha(root/path)==row['current_sha256'],'R49 numerical kernel changed')
 require(runtime['reserve_vram']==8 and runtime['memory_mode']=='normal','memory profile differs')
 if live:
  from check_storage import check as check_storage
  from execution_gate import atomic
  atomic(root/'audit/STORAGE_STARTUP.json',check_storage(root))
  require(root.resolve()==Path(runtime['remote_root']),'exact remote root required')
  import service
  profile=service.main_memory_profile()
  require(read(root/'configs/admission.json')['ready_for_launch'] is True,'root live resource admission pending')
  require((root/'deploy_manifest.json').is_file(),'formal producer seal pending')
  for path,row in read(root/'deploy_manifest.json')['files'].items():require(sha(root/path)==row['sha256'],'sealed file changed: '+path)
  for path,digest in read(root/'configs/parent_core_hashes.json').items():require(sha(Path(runtime['core'])/path)==digest,'actual Comfy core differs')
 return {'passed':True,'jobs':order,'first_pair':order[:2],'pairs':3,'distinct_motion_sources':3,'new_motion_sources':0,'NFE_per_job':20,'Euler_updates':20,'online_observations':0,'route_steps':list(range(6,15)),'launch_admitted':live}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');a=p.parse_args();print(json.dumps(check(live=a.live),indent=2))
