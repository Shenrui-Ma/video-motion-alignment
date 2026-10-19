"""Explicit root-approved first-pair capacity trial, followed by measured-pair review."""
import argparse,json,os,time
from pathlib import Path
from r78_contract import ROOT,read,sha,registry,require

def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,path)

def approval(root=ROOT):
 root=Path(root);p=root/'audit/ROOT_FIRST_PAIR_APPROVAL.json';a=read(p);runtime=read(root/'configs/runtime.json');_,order=registry(root)
 require(a.get('schema')=='r78-first-pair-capacity-trial-v1' and a.get('root_approved') is True,'root first-pair trial approval pending')
 require(a['runtime_profile_sha256']==sha(root/'configs/runtime.json') and a['main_gpu_uuid']==runtime['gpu_uuid'],'first-pair runtime/device changed')
 require(a['allowed_runs']==order[:2] and a['required_free_bytes']>=40*1024**3 and a['reserve_vram_gib']==8,'first-pair scope/headroom differs')
 require(a['capacity_status']=='ACTUAL_FULL_TRAJECTORY_PENDING','trial status falsely claims measured capacity')
 return a

def admitted_job(run,root=ROOT):
 root=Path(root);a=approval(root);_,order=registry(root);require(run in order,'unregistered job')
 require(run in a['allowed_runs'],'outside the fixed prompt pair');return True

def seal(root=ROOT):
 root=Path(root);require(not(root/'processes/service.json').exists(),'service registry exists; producer seal locked')
 files={}
 paths=[]
 for folder in ('scripts','extensions','configs/graphs','configs/parent_graphs','configs/ancestors','configs/prompts','design','analysis/postrun','tests'):
  paths.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
 paths.extend(root/'configs'/n for n in ('runtime.json','scientific_contract.json','input_hashes.json','runtime_kernel_hashes.json','parent_core_hashes.json','prompt_ancestry.json','expected_checkpoint_hashes.json','historical_noise_binding.json'))
 paths.extend(root/p for p in ('audit/root_run_pair.py','audit/consumer/postrun.py'))
 for p in sorted(paths):files[str(p.relative_to(root))]={'sha256':sha(p),'bytes':p.stat().st_size}
 value={'schema':'r78-producer-seal-v1','files':files,'mutable_root_owned':['configs/admission.json','audit/ROOT_FIRST_PAIR_APPROVAL.json','configs/queue.json'],'created_unix':time.time()};atomic(root/'deploy_manifest.json',value);return value

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['seal','approve-first-pair']);p.add_argument('--root-admitted',action='store_true');p.add_argument('--free-mib',type=int,default=40960);a=p.parse_args();root=ROOT
 if a.action=='seal':v=seal(root)
 else:
  require(a.root_admitted,'root must explicitly admit actual hardware/process resources')
  require(root==Path(read(root/'configs/runtime.json')['remote_root']),'actual remote root required')
  _,order=registry(root)
  if a.action=='approve-first-pair':
   require(a.free_mib>=40960,'first capacity trial requires >=40GiB free')
   v={'schema':'r78-first-pair-capacity-trial-v1','root_approved':True,'runtime_profile_sha256':sha(root/'configs/runtime.json'),'main_gpu_uuid':read(root/'configs/runtime.json')['gpu_uuid'],'allowed_runs':order[:2],'required_free_bytes':a.free_mib*1024**2,'reserve_vram_gib':8,'capacity_status':'ACTUAL_FULL_TRAJECTORY_PENDING','created_unix':time.time()};atomic(root/'audit/ROOT_FIRST_PAIR_APPROVAL.json',v)

 print(json.dumps({'action':a.action,'files':len(v.get('files',{})),'allowed_runs':v.get('allowed_runs')},indent=2))
if __name__=='__main__':main()
