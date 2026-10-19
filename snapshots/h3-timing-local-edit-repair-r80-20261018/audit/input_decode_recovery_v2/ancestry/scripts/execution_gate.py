"""Root-only 30GiB capacity trial: first Native, task review, then second Native."""
import argparse,json,os,time
from pathlib import Path
from r80_contract import ROOT,read,sha,registry,require

def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,path)

def approval(root=ROOT):
 root=Path(root);a=read(root/'audit/ROOT_FIRST_NATIVE_APPROVAL.json');runtime=read(root/'configs/runtime.json');_,order=registry(root)
 require(a.get('schema')=='r80-first-native-capacity-trial-v1' and a.get('root_approved') is True,'root first Native capacity approval pending')
 require(a['runtime_profile_sha256']==sha(root/'configs/runtime.json') and a['main_gpu_uuid']==runtime['gpu_uuid'],'runtime/device changed')
 require(a['allowed_runs']==order[:1] and a['required_free_bytes']>=30*1024**3 and a['reserve_vram_gib']==8,'first Native scope/headroom differs')
 require(a['capacity_status']=='ACTUAL_FULL_TRAJECTORY_PENDING','actual capacity status falsely certified')
 return a

def admitted_job(run,root=ROOT):
 root=Path(root);a=approval(root);_,order=registry(root);require(run in order,'unregistered run')
 if run in a['allowed_runs']:return True
 p=root/'audit/CONTINUE_AFTER_FIRST_NATIVE.json'
 if not p.exists():return False
 c=read(p);gate=root/'analysis/postrun/short_0230/NATIVE_RUNTIME_GATE.json'
 require(c.get('root_approved') is True and c.get('task_fidelity_reviewed') is True and c.get('schema')=='r80-second-native-approval-v1','root task review missing')
 require(c['runtime_profile_sha256']==a['runtime_profile_sha256'] and c['native_gate_sha256']==sha(gate) and read(gate)['passed'] is True,'actual first Native evidence changed')
 require(c['allowed_runs']==order[1:],'second Native scope differs');return True

def seal(root=ROOT):
 root=Path(root);require(not(root/'processes/service.json').exists(),'service registry exists; producer locked');files={};paths=[]
 for folder in ('scripts','extensions','configs/graphs','configs/parent_graphs','configs/prompts','design','analysis/postrun','tests'):
  paths.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
 paths.extend(root/'configs'/n for n in ('runtime.json','scientific_contract.json','input_hashes.json','runtime_kernel_hashes.json','parent_core_hashes.json','expected_input_pixels.json','expected_checkpoint_hashes.json'))
 paths.extend(root/p for p in ('audit/root_run_pair.py','audit/consumer/collect.py','audit/capacity_evidence/REPORT.txt','audit/capacity_evidence/SUMMARY.json'))
 for p in sorted(paths):files[str(p.relative_to(root))]={'sha256':sha(p),'bytes':p.stat().st_size}
 v={'schema':'r80-producer-seal-v1','files':files,'mutable_root_owned':['configs/admission.json','audit/ROOT_FIRST_NATIVE_APPROVAL.json','audit/CONTINUE_AFTER_FIRST_NATIVE.json'],'created_unix':time.time()};atomic(root/'deploy_manifest.json',v);return v

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['seal','approve-first-native','approve-second-native']);p.add_argument('--root-admitted',action='store_true');p.add_argument('--task-fidelity-reviewed',action='store_true');p.add_argument('--free-mib',type=int,default=30720);a=p.parse_args();root=ROOT
 if a.action=='seal':v=seal(root)
 else:
  require(a.root_admitted,'root must admit actual resources');require(root==Path(read(root/'configs/runtime.json')['remote_root']),'actual remote root required');_,order=registry(root)
  if a.action=='approve-first-native':
   require(a.free_mib>=30720,'30GiB minimum trial margin')
   v={'schema':'r80-first-native-capacity-trial-v1','root_approved':True,'runtime_profile_sha256':sha(root/'configs/runtime.json'),'main_gpu_uuid':read(root/'configs/runtime.json')['gpu_uuid'],'allowed_runs':order[:1],'required_free_bytes':a.free_mib*1024**2,'reserve_vram_gib':8,'capacity_status':'ACTUAL_FULL_TRAJECTORY_PENDING','created_unix':time.time()};atomic(root/'audit/ROOT_FIRST_NATIVE_APPROVAL.json',v)
  else:
   approval(root);require(a.task_fidelity_reviewed,'root must review the first Native edit');gate=root/'analysis/postrun/short_0230/NATIVE_RUNTIME_GATE.json';require(read(gate)['passed'] is True,'actual first Native gate pending')
   v={'schema':'r80-second-native-approval-v1','root_approved':True,'task_fidelity_reviewed':True,'runtime_profile_sha256':sha(root/'configs/runtime.json'),'native_gate_sha256':sha(gate),'allowed_runs':order[1:],'created_unix':time.time()};atomic(root/'audit/CONTINUE_AFTER_FIRST_NATIVE.json',v)
 print(json.dumps({'action':a.action,'files':len(v.get('files',{})),'allowed_runs':v.get('allowed_runs')},indent=2))
if __name__=='__main__':main()
