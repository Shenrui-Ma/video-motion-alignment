"""Root approves each individual submission; forced requires its reviewed Native."""
import argparse,json,os,time
from pathlib import Path
from r79_contract import ROOT,read,sha,registry,require

def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,path)

def approval(root=ROOT):
 root=Path(root);a=read(root/'audit/ROOT_SERVICE_APPROVAL.json');runtime=read(root/'configs/runtime.json')
 require(a.get('schema')=='r79-service-capacity-trial-v1' and a.get('root_approved') is True,'root service approval pending')
 require(a['runtime_profile_sha256']==sha(root/'configs/runtime.json') and a['main_gpu_uuid']==runtime['gpu_uuid'],'service runtime/device changed')
 require(a['required_free_bytes']>=40*1024**3 and a['reserve_vram_gib']==8,'service headroom differs')
 require(a['capacity_status']=='ACTUAL_FULL_TRAJECTORY_PENDING','trial falsely claims measured capacity')
 return a

def native_evidence(run,root=ROOT):
 root=Path(root);jobs,_=registry(root);row=jobs[run];require(row['arm']=='forced','Native evidence is for paired forced submission')
 native=run.removesuffix('_forced')+'_native';j=root/'logs'/f'{native}_job.json';h=root/'logs'/f'{native}_history.json';job=read(j);history=read(h)
 require(job.get('name')==native and job.get('status')=='success' and job.get('graph_sha256')==jobs[native]['graph_sha256'],'corresponding Native job has not completed')
 require(history.get('status',{}).get('completed') is True and history['status'].get('status_str')=='success','Native history has not completed')
 require(history.get('prompt',[None,None])[1]==job['prompt_id'],'Native history prompt identity differs')
 require(history['prompt'][2]==read(root/'configs/graphs'/f'{native}.json'),'Native actual graph differs')
 require(bool(history.get('outputs',{}).get('14',{}).get('images')),'Native output history missing')
 return {'run':native,'job_sha256':sha(j),'history_sha256':sha(h),'service_pid':job['service_pid'],'service_identity':job['service_identity']}

def approve_run(run,root=ROOT,native_reviewed=False):
 root=Path(root);a=approval(root);jobs,_=registry(root);require(run in jobs,'unregistered job');row=jobs[run]
 v={'schema':'r79-individual-job-approval-v1','root_approved':True,'run':run,'runtime_profile_sha256':a['runtime_profile_sha256'],'graph_sha256':row['graph_sha256'],'created_unix':time.time()}
 if row['arm']=='forced':
  require(native_reviewed is True,'root Native visual review required before forced submission');v['native_reviewed']=True;v['native_evidence']=native_evidence(run,root)
  owner=read(root/'processes/service.json');require(owner['pid']==v['native_evidence']['service_pid'] and owner['identity']==v['native_evidence']['service_identity'],'paired Native service generation changed')
 atomic(root/'audit/ROOT_JOB_APPROVALS'/f'{run}.json',v);return v

def admitted_job(run,root=ROOT):
 root=Path(root);a=approval(root);jobs,_=registry(root);require(run in jobs,'unregistered job')
 p=root/'audit/ROOT_JOB_APPROVALS'/f'{run}.json'
 if not p.exists():return False
 v=read(p);require(v.get('schema')=='r79-individual-job-approval-v1' and v.get('root_approved') is True and v.get('run')==run,'individual approval invalid')
 require(v['runtime_profile_sha256']==a['runtime_profile_sha256'] and v['graph_sha256']==jobs[run]['graph_sha256'],'individual approved graph/runtime changed')
 if jobs[run]['arm']=='forced':
  require(v.get('native_reviewed') is True and v.get('native_evidence')==native_evidence(run,root),'reviewed Native evidence changed')
  owner=read(root/'processes/service.json');e=v['native_evidence'];require(owner['pid']==e['service_pid'] and owner['identity']==e['service_identity'],'paired Native service generation changed')
 return True

def seal(root=ROOT):
 root=Path(root);require(not(root/'processes/service.json').exists(),'service registry exists; producer seal locked');paths=[]
 for folder in ('scripts','extensions','configs/graphs','configs/parent_graphs','configs/R54_evidence','configs/source_selection','configs/prompts','design','analysis/postrun','tests','source_snapshot'):
  paths.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
 paths.extend(root/'configs'/n for n in ('runtime.json','scientific_contract.json','input_hashes.json','runtime_kernel_hashes.json','parent_core_hashes.json','source_selection_hashes.json','expected_checkpoint_hashes.json','storage_policy.json'));paths.append(root/'PREPARED_INPUTS_MANIFEST.json')
 v={'schema':'r79-producer-seal-v1','files':{str(p.relative_to(root)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(paths)},'mutable_root_owned':['configs/admission.json','audit/ROOT_SERVICE_APPROVAL.json','audit/ROOT_JOB_APPROVALS/'],'created_unix':time.time()};atomic(root/'deploy_manifest.json',v);return v

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['seal','approve-service','approve-run']);p.add_argument('run',nargs='?');p.add_argument('--root-admitted',action='store_true');p.add_argument('--native-reviewed',action='store_true');p.add_argument('--free-mib',type=int,default=40960);a=p.parse_args()
 if a.action=='seal':v=seal()
 else:
  require(a.root_admitted,'root must admit actual resources');require(ROOT==Path(read(ROOT/'configs/runtime.json')['remote_root']),'actual remote root required')
  if a.action=='approve-service':
   require(a.free_mib>=40960,'capacity trial requires >=40GiB free');v={'schema':'r79-service-capacity-trial-v1','root_approved':True,'runtime_profile_sha256':sha(ROOT/'configs/runtime.json'),'main_gpu_uuid':read(ROOT/'configs/runtime.json')['gpu_uuid'],'required_free_bytes':a.free_mib*1024**2,'reserve_vram_gib':8,'capacity_status':'ACTUAL_FULL_TRAJECTORY_PENDING','created_unix':time.time()};atomic(ROOT/'audit/ROOT_SERVICE_APPROVAL.json',v)
  else:v=approve_run(a.run,native_reviewed=a.native_reviewed)
 print(json.dumps({'action':a.action,'files':len(v.get('files',{})),'run':v.get('run')},indent=2))
if __name__=='__main__':main()
