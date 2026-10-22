"""Bounded local relay for completed remote inference outputs; no model inference on Mac."""
import argparse, fcntl, hashlib, json, os, shlex, subprocess, sys, time, traceback
from pathlib import Path
from metric_worker import atomic
ROOT=Path(__file__).resolve().parent
REMOTE='/data/researcher/h3_metrics_20261022'
HOST='H3_SERVER'
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3']
PRODUCERS=[('H3_SERVER_B','/data4/researcher/h3_runs/benchmark_schedule_20261022'),('H3_SERVER_A','/home/researcher/h3_runs/benchmark_schedule_20261022_host9a'),('H3_SERVER_A','/home/researcher/h3_runs/benchmark_schedule_20261022_host9b')]

def ssh(host,cmd,timeout=90):
 return subprocess.run(SSH+[host,cmd],capture_output=True,text=True,timeout=timeout,check=True).stdout

def get_results(host,root):
 code='import json;from pathlib import Path;r=Path('+repr(root)+');print(json.dumps({"results":[json.loads(p.read_text()) for p in (r/"queue_state/results").glob("*.json")],"state":json.loads((r/"queue_state/state.json").read_text()) if (r/"queue_state/state.json").exists() else None}))'
 return json.loads(ssh(host,shlex.join(['python3','-c',code])))

def transfer(src_host,src,dst,digest):
 check='import hashlib;from pathlib import Path;p=Path('+repr(dst)+');print(hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "")'
 if ssh(HOST,shlex.join(['python3','-c',check])).strip()==digest:return
 cmd='mkdir -p '+shlex.quote(str(Path(dst).parent))+' && cat > '+shlex.quote(dst+'.partial')
 target=subprocess.Popen(SSH+[HOST,cmd],stdin=subprocess.PIPE)
 if src_host:
  source=subprocess.Popen(SSH+[src_host,shlex.join(['cat',src])],stdout=target.stdin);target.stdin.close();rc=source.wait(timeout=900)
  if rc:target.terminate();raise RuntimeError('Source transfer failed')
 else:
  with open(src,'rb') as f:
   while True:
    chunk=f.read(1024*1024)
    if not chunk:break
    target.stdin.write(chunk)
  target.stdin.close()
 if target.wait(timeout=900):raise RuntimeError('Destination transfer failed')
 verify='import hashlib;from pathlib import Path;p=Path('+repr(dst+'.partial')+');assert hashlib.sha256(p.read_bytes()).hexdigest()=='+repr(digest)+';p.replace('+repr(dst)+')'
 ssh(HOST,shlex.join(['python3','-c',verify]))

def metadata(m):
 if m['benchmark']=='IVEBench':return m.get('evaluation_metadata',m.get('original_task'))
 # Public FlexiAct target CSV mismatches the squat motion; explicit adapter records actual requested task.
 return dict(id=100001,src_video_name=m['task_id']+'.mp4',category='subject_editing',subcategory='external_reference_motion_transfer',source_prompt=m['original_task']['source_row']['caption'],edit_prompt=m.get('prompt',m['recommended_prompt']),target_prompt='A man is doing squats.',adapter='FlexiAct reference-image motion transfer; text-only IVEBench compliance cannot score reference-image identity')

def add_result(host,result,manifest):
 m=result['metadata'];sid=m['task_id'];method=m['method'];rid=result['job_id']
 if any(j['id']==rid for j in manifest['jobs']):return False
 file=next(f for f in result['files'] if f['path'].endswith('.mp4'));meta=metadata(m)
 src=m['reference_video'];source_dst=f'{REMOTE}/videos/{sid}/source.mp4'
 if Path(src).exists():digest=hashlib.sha256(Path(src).read_bytes()).hexdigest();src_host=None
 else:src=m['source_video'];src_host=host;digest=ssh(host,shlex.join(['sha256sum',src])).split()[0]
 transfer(src_host,src,source_dst,digest)
 dst=f'{REMOTE}/videos/{sid}/{rid}.mp4';transfer(host,file['path'],dst,file['sha256'])
 common=dict(task_id=sid,dataset=m['benchmark'],cohort='main' if rid.startswith('new_') else 'expansion',metadata=meta,metadata_file=f'{REMOTE}/metadata/{sid}.json',source_frames_parent=f'{REMOTE}/frames/source',valid_frames=m['valid_frames'],crop_xywh=m['evaluation_crop_xywh'],fps=m['fps'],seed=m.get('seed'),prompt=m.get('prompt',m.get('recommended_prompt')))
 if not any(j['task_id']==sid and j['method']=='source' for j in manifest['jobs']):manifest['jobs'].append(dict(common,id=sid+'__source',method='source',target_frames_parent=f'{REMOTE}/frames/source',video=source_dst,sha256=digest))
 manifest['jobs'].append(dict(common,id=rid,method=method,target_frames_parent=f'{REMOTE}/frames/by_run/{rid}',video=dst,sha256=file['sha256'],timing=result.get('timing',{}),producer_result=result))
 return True

def expected_jobs(manifest):
 out={j['id']:{k:j[k] for k in ['id','task_id','dataset','method']}|{'cohort':j.get('cohort','main')} for j in manifest['jobs']}
 for package in ['package','host9a','host9b']:
  p=ROOT.parent/'inference'/package/'jobs.json'
  if not p.exists():continue
  for job in json.loads(p.read_text())['jobs']:
   m=job['metadata'];cohort='main' if job['id'].startswith('new_') else 'expansion'
   out[job['id']]=dict(id=job['id'],task_id=m['task_id'],dataset=m['benchmark'],method=m['method'],cohort=cohort)
   sid=m['task_id']+'__source'
   out.setdefault(sid,dict(id=sid,task_id=m['task_id'],dataset=m['benchmark'],method='source',cohort=cohort))
 return list(out.values())

def synchronize(manifest):
 atomic(ROOT/'manifest.json',manifest)
 subprocess.run(['rsync','-az','-e',shlex.join(SSH),str(ROOT/'manifest.json'),HOST+':'+REMOTE+'/code/manifest.json'],check=True,timeout=120)
 python=REMOTE+'/venv/bin/python';code=REMOTE+'/code'
 ssh(HOST,shlex.join([python,code+'/prepare_frames.py','--manifest',code+'/manifest.json','--ffmpeg','/data3/researcher/vsr11/bin/ffmpeg']),timeout=1800)
 ensure_metric_service()

def ensure_metric_service():
 # CPU supervisor is safe to recreate after a metrics-host reboot; lock prevents duplicates.
 args=[REMOTE+'/venv/bin/python',REMOTE+'/code/metric_service.py','--root',REMOTE,'--hours','48']
 ssh(HOST,'nohup '+shlex.join(args)+' >> '+shlex.quote(REMOTE+'/logs/service.log')+' 2>&1 < /dev/null &')

def enrich_historical_timing(manifest):
 p=ROOT.parent/'timing/historical_six_cases_timing.json'
 if not p.exists():return
 rows={(r['case_id'],r['method']):r for r in json.loads(p.read_text())['records']}
 for j in manifest['jobs']:
  r=rows.get((j['task_id'],j['method']))
  if r is None or j['id'].startswith(('new_','extra_')):continue
  j['timing']=dict(sampling_seconds=r.get('sampler_wall_seconds') or r.get('sampler_elapsed_seconds_rounded'),mean_sampling_step_seconds=r['mean_step_seconds'],scope='historical_with_x0_capture',measurement_basis=r['measurement_basis'],measurement_resolution=r.get('measurement_resolution'),host=r['host'],gpu_uuid=r['gpu_uuid'],original_record=r)

def main(a):
 lock=open(ROOT/'watcher.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 deadline=time.time()+a.hours*3600
 while time.time()<deadline:
  manifest=json.loads((ROOT/'manifest.json').read_text());enrich_historical_timing(manifest);manifest['expected_jobs']=expected_jobs(manifest);added=[];errors=[];terminal=[]
  for host,root in PRODUCERS:
   try:
    batch=get_results(host,root)
    for result in batch['results']:
     try:
      if add_result(host,result,manifest):added.append(result['job_id']);atomic(ROOT/'manifest.json',manifest)
     except Exception as exc:errors.append({'job':result.get('job_id'),'error':str(exc)})
    state=batch['state'] or {};statuses=[v.get('status') for v in state.get('jobs',{}).values()]
    terminal.append(bool(statuses) and all(s in ['completed','failed','failed_exhausted','blocked'] for s in statuses))
   except Exception as exc:errors.append({'host':host,'root':root,'error':str(exc)});terminal.append(False)
  atomic(ROOT/'manifest.json',manifest)
  digest=hashlib.sha256((ROOT/'manifest.json').read_bytes()).hexdigest()
  marker=ROOT/'last_synchronized.sha256'
  if added or not marker.exists() or marker.read_text()!=digest:
   try:
    synchronize(manifest);marker.write_text(digest)
   except Exception as exc:errors.append({'synchronize':str(exc)})
  try:
   ensure_metric_service()
   ssh(HOST,shlex.join([REMOTE+'/venv/bin/python',REMOTE+'/code/aggregate.py','--results',REMOTE+'/evaluation/results','--output',REMOTE+'/evaluation/summary.json','--manifest',REMOTE+'/code/manifest.json']))
  except Exception as exc:errors.append({'metric_service':str(exc)})
  atomic(ROOT/'watcher_status.json',{'time':time.time(),'deadline':deadline,'jobs':len(manifest['jobs']),'added':added,'errors':errors,'producer_terminal':terminal})
  if a.once or (all(terminal) and not errors):break
  time.sleep(a.poll)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--hours',type=float,default=48);p.add_argument('--poll',type=int,default=90);p.add_argument('--once',action='store_true');main(p.parse_args())
