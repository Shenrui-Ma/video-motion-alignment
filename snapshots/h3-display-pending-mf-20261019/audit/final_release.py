"""Read-only final audit after all planned official MF jobs and wrappers exit."""
import sys,os,math,argparse,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import read,sha,save,bound,identity,verify_seal
import capacity

def main(attempt):
 verify_seal();complete=read(ROOT/'audit'/attempt/'COMPLETE.json');assert complete['passed'] and complete['remaining']==[] and complete['all_spawned_trackers_released']
 states=[];targets=[]
 for row in read(ROOT/'configs/PLAN.json')['jobs']:
  p=ROOT/'state'/row['case']/(row['role']+'.json');state=read(p);release=read(state['release']['file']);assert sha(state['release']['file'])==state['release']['sha256'];assert release['passed'] and release['returncode']==0 and release['process_absent'] and release['CUDA_absent'];assert identity(release['identity']['pid'])!=release['identity'];states.append(bound(p))
  folder=ROOT/state['folder'];r=read(folder/'REPORT.json');assert sha(folder/'REPORT.json')==state['report_sha256'] and r['passed'];ext='tracks.pt' if read(ROOT/'cases'/row['case']/'INPUTS.json')['benchmark']=='FlexiAct' else 'tracks.npz';assert sha(folder/ext)==r['tracks_sha256']
  if row['role']!='source':
   result=ROOT/'results'/row['case']/(row['role']+'.json');value=read(result);score=value.get('score',value.get('motion_fidelity'));assert isinstance(score,(int,float)) and math.isfinite(score);targets.append(bound(result))
 assert len(states)==47 and len(targets)==34
 wrappers=[];all_releases=[];runtime=[];baselines=[]
 for folder in sorted((ROOT/'audit').glob('actual_pending_attempt*')):
  if not folder.is_dir() or not(folder/'STARTED.json').is_file():continue
  started=read(folder/'STARTED.json');owner=started['identity'];assert identity(owner['pid'])!=owner;wrappers.append(owner);baseline=read(folder/'OOM_BASE.json');old={x['path']:x for x in baseline['ancestors']};baselines.append(old)
  for p in folder.glob('jobs/*/*/RELEASED.json'):
   release=read(p);assert release['passed'] and release['process_absent'] and release['CUDA_absent'];assert identity(release['identity']['pid'])!=release['identity'];all_releases.append(bound(p))
   obs=read(p.parent/'RESOURCE_OBSERVATIONS.json')['samples'];peak=0
   for o in obs:
    for s in o['capacity']['ancestors']:
     assert s['path']in old
     for key in ('oom','oom_kill'):assert s['events'].get(key,0)==old[s['path']]['events'].get(key,0)
    if 'process_memory'in o:peak=max(peak,int(o['process_memory'].get('VmHWM','0 kB').split()[0]))
   runtime.append(dict(attempt=folder.name,case=p.parent.parent.name,role=p.parent.name,pid=release['identity']['pid'],returncode=release['returncode'],max_VmHWM_KiB=peak,release=bound(p)))
 raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader,nounits'],text=True,timeout=15);rows=[]
 for line in raw.splitlines():
  if not line.strip():continue
  pid,gpu,mem=map(str.strip,line.split(','));proc=Path('/proc')/pid
  if not proc.exists():continue
  uid=proc.stat().st_uid;assert uid!=1004;rows.append(dict(pid=int(pid),uid=uid,gpu_uuid=gpu,memory_mib=mem))
 fresh=capacity.snapshot();deltas=[]
 for old in baselines:
  delta={x['path']:{k:x['events'].get(k,0)-old[x['path']]['events'].get(k,0) for k in ('oom','oom_kill')}for x in fresh['ancestors']if x['path']in old};assert all(v==0 for d in delta.values()for v in d.values());deltas.append(delta)
 gpu=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.free','--format=csv,noheader,nounits'],text=True,timeout=15)
 result=dict(passed=True,wrapper_identities=wrappers,all_spawned_trackers_released=True,fresh_own_cuda_absent=True,completed_new_trackers=47,completed_generated_scores=34,failed_attempts_preserved=True,state_receipts=states,result_receipts=targets,child_release_receipts=all_releases,resource_observations=runtime,OOM_and_oom_kill_delta=deltas,fresh_capacity=fresh,fresh_short_MF_assessment=capacity.assess(fresh,'entry'),fresh_gpu_rows=gpu,other_users_cuda=rows,final_complete=bound(ROOT/'audit'/attempt/'COMPLETE.json'),seal=bound(ROOT/'SEAL.json'),unix=time.time())
 p=ROOT/'audit/FINAL_RELEASE_VERIFIED.json';assert not p.exists();save(p,result);print({'file':str(p),'sha256':sha(p),'completed_targets':34,'all_released':True})
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--attempt',required=True);main(a.parse_args().attempt)
