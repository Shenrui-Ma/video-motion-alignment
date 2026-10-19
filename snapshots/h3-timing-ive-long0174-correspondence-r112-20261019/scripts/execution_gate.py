"""Reviewed deployment plus exact same-service two-arm admission."""
import argparse,json,os,time
from pathlib import Path
from r112_contract import ROOT,read,sha,registry,require

def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,path)

def verify_seal(root=ROOT):
 root=Path(root);seal=read(root/'deploy_manifest.json')
 require(seal['source_cpu_seal_sha256']==sha(root/'CPU_PREPARATION_SEAL.json'),'CPU source seal differs')
 for rel,row in seal['files'].items():
  p=root/rel;require(not p.is_symlink() and sha(p)==row['sha256'],'deployment changed: '+rel)
 return seal

def reviewed(root=ROOT):
 root=Path(root);review=read(root/'audit/GPU_DEPLOYMENT_REVIEW.json')
 require(review.get('approved') is True and review.get('scope')=='r112-two-arm-gpu-execution' and review.get('producer_seal_sha256')==sha(root/'deploy_manifest.json'),'root deployment review absent/stale')
 verify_seal(root);return review

def approval(root=ROOT):
 root=Path(root);reviewed(root);a=read(root/'audit/ROOT_RUN_APPROVAL.json');runtime=read(root/'configs/runtime.json');_,order=registry(root)
 require(a.get('schema')=='r112-control-admission-v1' and a.get('root_approved') is True and a.get('parent_tasks_reviewed') is True,'root admission absent')
 require(a['runtime_profile_sha256']==sha(root/'configs/runtime.json') and a['parent_bindings_sha256']==sha(root/'configs/parent_bindings.json') and a['main_gpu_uuid']==runtime['gpu_uuid'],'runtime/parent/device changed')
 require(a['allowed_runs']==order and a['required_free_bytes']>=40*1024**3 and a['reserve_vram_gib']==8,'admission/headroom changed')
 return a

def admitted_job(run,root=ROOT):
 root=Path(root);_,order=registry(root);require(run in order,'unregistered run');approval(root)
 if run==order[1]:
  gate=read(root/'analysis/postrun'/order[0]/'RUNTIME_GATE.json');owner=read(root/'processes/service.json')
  require(gate['passed'] is True and all(gate['checks'].values()) and gate['service_owner']==owner and gate['run_id']==order[0],'first arm actual gate absent/different generation')
 return True

def approve_first(root=ROOT,free_mib=40960,parent_tasks_reviewed=False):
 root=Path(root);reviewed(root);runtime=read(root/'configs/runtime.json');_,order=registry(root)
 require(root==Path(runtime['remote_root']) and free_mib>=40960 and parent_tasks_reviewed,'actual root/task review/40GiB required')
 require(not(root/'audit/ROOT_RUN_APPROVAL.json').exists(),'approval exists; explicit recovery required')
 a={'schema':'r112-control-admission-v1','root_approved':True,'parent_tasks_reviewed':True,'runtime_profile_sha256':sha(root/'configs/runtime.json'),'parent_bindings_sha256':sha(root/'configs/parent_bindings.json'),'main_gpu_uuid':runtime['gpu_uuid'],'allowed_runs':order,'required_free_bytes':free_mib*1024**2,'reserve_vram_gib':8,'created_unix':time.time()}
 atomic(root/'audit/ROOT_RUN_APPROVAL.json',a);return a

def seal(root=ROOT):
 root=Path(root);require(not(root/'processes/service.json').exists(),'service registry exists; seal locked');paths=[]
 for folder in ('scripts','extensions','configs','design','source_snapshot','tests','inputs','analysis/postrun'):
  paths.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and (folder!='analysis/postrun' or p.suffix=='.py') and p.name!='admission.json')
 paths.extend((root/'audit/root_run_control.py',root/'CPU_PREPARATION_SEAL.json'))
 value={'schema':'r112-producer-deployment-seal-v1','source_cpu_seal_sha256':sha(root/'CPU_PREPARATION_SEAL.json'),'GPU_started':False,'files':{str(p.relative_to(root)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(paths)},'mutable_root_owned':['configs/admission.json','audit/ROOT_RUN_APPROVAL.json','audit/GPU_DEPLOYMENT_REVIEW.json'],'created_unix':time.time()}
 atomic(root/'deploy_manifest.json',value);return value
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['seal','approve-run']);p.add_argument('--root-admitted',action='store_true');p.add_argument('--parent-tasks-reviewed',action='store_true');p.add_argument('--free-mib',type=int,default=40960);a=p.parse_args()
 if a.action=='seal':v=seal()
 else:
  require(a.root_admitted,'explicit root admission required');v=approve_first(free_mib=a.free_mib,parent_tasks_reviewed=a.parent_tasks_reviewed)
 print(json.dumps({'action':a.action,'files':len(v.get('files',{})),'allowed_runs':v.get('allowed_runs')},indent=2))
