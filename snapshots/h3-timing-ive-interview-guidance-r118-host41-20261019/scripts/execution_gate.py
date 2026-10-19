"""Root admits one matched fixed-guidance output after predecessor release."""
import argparse,json,os,time
from pathlib import Path
from r118_contract import ROOT,read,sha,registry,require,SOURCES

def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,path)
def approval(root=ROOT):
 root=Path(root);a=read(root/'audit/ROOT_RUN_APPROVAL.json');runtime=read(root/'configs/runtime.json');_,order=registry(root)
 require(a.get('schema')=='r118-control-admission-v1' and a.get('root_approved') is True and a.get('parent_tasks_reviewed') is True,'root parent-task review/admission pending')
 require(a['runtime_profile_sha256']==sha(root/'configs/runtime.json') and a['parent_bindings_sha256']==sha(root/'configs/parent_bindings.json') and a['main_gpu_uuid']==runtime['gpu_uuid'],'runtime/parent/device changed')
 require(a['allowed_runs']==order and a['required_free_bytes']>=40*1024**3 and a['reserve_vram_gib']==8,'admission/headroom changed')

 return a
def admitted_job(run,root=ROOT):
 _,order=registry(root);require(run in order,'unregistered run');return run in approval(root)['allowed_runs']
def approve_first(root=ROOT,free_mib=40960,parent_tasks_reviewed=False):
 root=Path(root);runtime=read(root/'configs/runtime.json');_,order=registry(root)
 require(root==Path(runtime['remote_root']) and free_mib>=40960 and parent_tasks_reviewed,'actual root/task review/40GiB required')
 require(not(root/'audit/ROOT_RUN_APPROVAL.json').exists(),'approval already exists; explicit recovery required')
 a={'schema':'r118-control-admission-v1','root_approved':True,'parent_tasks_reviewed':True,'runtime_profile_sha256':sha(root/'configs/runtime.json'),'parent_bindings_sha256':sha(root/'configs/parent_bindings.json'),'main_gpu_uuid':runtime['gpu_uuid'],'allowed_runs':order[:1],'required_free_bytes':free_mib*1024**2,'reserve_vram_gib':8,'created_unix':time.time()}
 atomic(root/'audit/ROOT_RUN_APPROVAL.json',a);return a
def seal(root=ROOT):
 root=Path(root);require(not(root/'processes/service.json').exists(),'service registry exists; seal locked');paths=[]
 for folder in ('scripts','extensions','configs','design','source_snapshot','tests','analysis/postrun'):
  paths.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and (folder!='analysis/postrun' or p.suffix=='.py') and p.name!='admission.json')
 paths.extend(root/'audit'/name for name in ('root_run_control.py','check_cpu_imports.py','remote_cpu_validate.py','INHERITED_BYTE_BINDINGS.json'))
 value={'schema':'r118-producer-seal-v1','files':{str(p.relative_to(root)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(paths)},'mutable_root_owned':['configs/admission.json','audit/ROOT_RUN_APPROVAL.json'],'created_unix':time.time()};atomic(root/'deploy_manifest.json',value);return value
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['seal','approve-run']);p.add_argument('--root-admitted',action='store_true');p.add_argument('--parent-tasks-reviewed',action='store_true');p.add_argument('--free-mib',type=int,default=40960);a=p.parse_args()
 if a.action=='seal':v=seal()
 else:
  require(a.root_admitted,'explicit root admission required');v=approve_first(free_mib=a.free_mib,parent_tasks_reviewed=a.parent_tasks_reviewed)
 print(json.dumps({'action':a.action,'files':len(v.get('files',{})),'allowed_runs':v.get('allowed_runs')},indent=2))
