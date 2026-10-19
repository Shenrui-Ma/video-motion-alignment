"""Root admits a single Native prompt control after exact predecessor release."""
import argparse,json,os,time
from pathlib import Path
from r90_contract import ROOT,read,sha,registry,require,RUN_ID

def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,path)
def approval(root=ROOT):
 root=Path(root);a=read(root/'audit/ROOT_NATIVE_APPROVAL.json');runtime=read(root/'configs/runtime.json');registry(root)
 require(a.get('schema')=='r90-native-admission-v1' and a.get('root_approved') is True,'root Native approval pending')
 require(a['runtime_profile_sha256']==sha(root/'configs/runtime.json') and a['main_gpu_uuid']==runtime['gpu_uuid'],'runtime/device changed')
 require(a['allowed_runs']==[RUN_ID] and a['required_free_bytes']>=40*1024**3 and a['reserve_vram_gib']==8,'single Native admission/headroom changed')
 return a
def admitted_job(run,root=ROOT):
 require(run==RUN_ID,'unregistered run');return run in approval(root)['allowed_runs']
def seal(root=ROOT):
 root=Path(root);require(not(root/'processes/service.json').exists(),'service registry exists; seal locked')
 paths=[]
 for folder in ('scripts','extensions','configs','design','source_snapshot','tests','analysis/postrun'):
  paths.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and (folder!='analysis/postrun' or p.suffix=='.py') and p.name!='admission.json')
 paths.append(root/'audit/root_run_native.py')
 value={'schema':'r90-producer-seal-v1','files':{str(p.relative_to(root)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(paths)},'mutable_root_owned':['configs/admission.json','audit/ROOT_NATIVE_APPROVAL.json'],'created_unix':time.time()}
 atomic(root/'deploy_manifest.json',value);return value
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['seal','approve-native']);p.add_argument('--root-admitted',action='store_true');p.add_argument('--free-mib',type=int,default=40960);a=p.parse_args()
 if a.action=='seal':v=seal()
 else:
  require(a.root_admitted and ROOT==Path(read(ROOT/'configs/runtime.json')['remote_root']),'explicit root actual remote admission required')
  require(a.free_mib>=40960,'require40GiBfree');registry()
  v={'schema':'r90-native-admission-v1','root_approved':True,'runtime_profile_sha256':sha(ROOT/'configs/runtime.json'),'main_gpu_uuid':read(ROOT/'configs/runtime.json')['gpu_uuid'],'allowed_runs':[RUN_ID],'required_free_bytes':a.free_mib*1024**2,'reserve_vram_gib':8,'created_unix':time.time()};atomic(ROOT/'audit/ROOT_NATIVE_APPROVAL.json',v)
 print(json.dumps({'action':a.action,'files':len(v.get('files',{})),'allowed_runs':v.get('allowed_runs')},indent=2))
