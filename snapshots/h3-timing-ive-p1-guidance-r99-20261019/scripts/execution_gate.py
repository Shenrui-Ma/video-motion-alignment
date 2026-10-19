"""Root admits the first control, then reviews its actual pair before the other two."""
import argparse,json,os,time
from pathlib import Path
from r99_contract import ROOT,read,sha,registry,require,SOURCES

def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,path)
def approval(root=ROOT):
 root=Path(root);a=read(root/'audit/ROOT_RUN_APPROVAL.json');runtime=read(root/'configs/runtime.json');_,order=registry(root)
 require(a.get('schema')=='r99-control-admission-v1' and a.get('root_approved') is True and a.get('parent_tasks_reviewed') is True,'root parent-task review/admission pending')
 require(a['runtime_profile_sha256']==sha(root/'configs/runtime.json') and a['parent_bindings_sha256']==sha(root/'configs/parent_bindings.json') and a['main_gpu_uuid']==runtime['gpu_uuid'],'runtime/parent/device changed')
 require(a['allowed_runs'] in (order[:1],order) and a['required_free_bytes']>=40*1024**3 and a['reserve_vram_gib']==8,'admission/headroom changed')
 if a['allowed_runs']==order:
  gate=root/'analysis/postrun'/SOURCES[0]/'PAIR_RUNTIME_GATE.json';v=read(gate);owner=read(root/'processes/service.json')
  require(a.get('first_control_reviewed') is True and v['passed'] is True and a['first_gate_sha256']==sha(gate),'first control actual gate/review missing')
  require(a['service_owner']==v['service_owner']==owner,'first review service generation changed')
 return a
def admitted_job(run,root=ROOT):
 _,order=registry(root);require(run in order,'unregistered run');return run in approval(root)['allowed_runs']
def approve_first(root=ROOT,free_mib=40960,parent_tasks_reviewed=False):
 root=Path(root);runtime=read(root/'configs/runtime.json');_,order=registry(root)
 require(root==Path(runtime['remote_root']) and free_mib>=40960 and parent_tasks_reviewed,'actual root/task review/40GiB required')
 require(not(root/'audit/ROOT_RUN_APPROVAL.json').exists(),'approval already exists; explicit recovery required')
 a={'schema':'r99-control-admission-v1','root_approved':True,'parent_tasks_reviewed':True,'runtime_profile_sha256':sha(root/'configs/runtime.json'),'parent_bindings_sha256':sha(root/'configs/parent_bindings.json'),'main_gpu_uuid':runtime['gpu_uuid'],'allowed_runs':order[:1],'required_free_bytes':free_mib*1024**2,'reserve_vram_gib':8,'created_unix':time.time()}
 atomic(root/'audit/ROOT_RUN_APPROVAL.json',a);return a
def approve_rest(root=ROOT,reviewed=False):
 root=Path(root);a=approval(root);_,order=registry(root);require(reviewed and a['allowed_runs']==order[:1],'first control review required')
 import service
 owner=read(root/'processes/service.json');service.assert_owned(owner)
 gate=root/'analysis/postrun'/SOURCES[0]/'PAIR_RUNTIME_GATE.json';v=read(gate)
 require(v['passed'] is True and all(v['checks'].values()) and v['service_owner']==owner,'first actual paired gate differs')
 state=read(root/'logs/controller_state.json');require(state['completed']==order[:1] and state['status']=='awaiting_root_run_approval','controller is not holding after first control')
 a.update(allowed_runs=order,first_control_reviewed=True,first_gate_sha256=sha(gate),service_owner=owner,reviewed_unix=time.time());atomic(root/'audit/ROOT_RUN_APPROVAL.json',a);return a
def seal(root=ROOT):
 root=Path(root);require(not(root/'processes/service.json').exists(),'service registry exists; seal locked');paths=[]
 for folder in ('scripts','extensions','configs','design','source_snapshot','tests','analysis/postrun'):
  paths.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and (folder!='analysis/postrun' or p.suffix=='.py') and p.name!='admission.json')
 paths.append(root/'audit/root_run_control.py')
 value={'schema':'r99-producer-seal-v1','files':{str(p.relative_to(root)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(paths)},'mutable_root_owned':['configs/admission.json','audit/ROOT_RUN_APPROVAL.json'],'created_unix':time.time()};atomic(root/'deploy_manifest.json',value);return value
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['seal','approve-run','approve-rest']);p.add_argument('--root-admitted',action='store_true');p.add_argument('--parent-tasks-reviewed',action='store_true');p.add_argument('--first-control-reviewed',action='store_true');p.add_argument('--free-mib',type=int,default=40960);a=p.parse_args()
 if a.action=='seal':v=seal()
 else:
  require(a.root_admitted,'explicit root admission required');v=approve_first(free_mib=a.free_mib,parent_tasks_reviewed=a.parent_tasks_reviewed) if a.action=='approve-run' else approve_rest(reviewed=a.first_control_reviewed)
 print(json.dumps({'action':a.action,'files':len(v.get('files',{})),'allowed_runs':v.get('allowed_runs')},indent=2))
