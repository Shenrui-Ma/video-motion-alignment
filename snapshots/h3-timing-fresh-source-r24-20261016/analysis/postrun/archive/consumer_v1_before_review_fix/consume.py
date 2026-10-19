"""One serialized completed-run consumer. Polling never holds compute locks."""
import fcntl,hashlib,json,os,shlex,subprocess,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];REMOTE='/data5/researcher/h3_runs/timing_fresh_source_r24_20261016/analysis/postrun';PYTHON='/home/researcher/miniconda3/envs/comfyui/bin/python';HOST='H3_SERVER_A'
CPU=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(x,indent=2)+'\n');tmp.replace(p)
def emit(x):print(json.dumps(x),flush=True)
def call(args):
 cmd=shlex.join(['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1',PYTHON,REMOTE+'/remote_consume.py',*args,'--binding',REMOTE+'/BINDING.json'])
 p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3',HOST,cmd],capture_output=True,text=True)
 return p

def verify_download(arc):
 d=read(arc/'FILE_INVENTORY.json')
 for rel,x in d.items():
  p=arc/rel
  if p.exists() and sha(p)!=x['sha256']:raise ValueError('downloaded archive SHA '+str(p))
 done=read(arc/'CPU_COMPLETE.json');p=arc/'output'/Path(done['video']).name
 if sha(p)!=done['video_sha256']:raise ValueError('downloaded MP4 SHA')
 probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','stream=width,height,r_frame_rate,avg_frame_rate,duration,time_base:frame=best_effort_timestamp_time','-of','json',str(p)]))
 s=probe['streams'][0]
 if not (s['width']==1312 and s['height']==736 and s['r_frame_rate']=='24/1' and s['avg_frame_rate']=='24/1' and abs(float(s['duration'])-5.875)<1e-6 and len(probe['frames'])==141):raise ValueError('playback geometry')
 if any(abs(float(v['best_effort_timestamp_time'])-i/24)>1e-6 for i,v in enumerate(probe['frames'])):raise ValueError('physical PTS mismatch')
 save(arc/'PLAYBACK_GATE.json',{'passed':True,'video_sha256':sha(p),'probe':probe,'big_pt_retained_remote':True})

def main():
 exclusive=(HERE/'unique_consumer.lock').open('a');fcntl.flock(exclusive,fcntl.LOCK_EX|fcntl.LOCK_NB)
 frozen=read(HERE/'FREEZE.json')
 for name,d in frozen['files'].items():
  if sha(HERE/name)!=d:raise ValueError('consumer frozen file changed '+name)
 bind=read(HERE/'BINDING.json');statepath=HERE/'STATE.json';state=read(statepath) if statepath.exists() else {'processed':[],'pairs':[],'stable':{},'failures':{},'phase':'waiting'}
 save(HERE/'consumer_identity.json',{'pid':os.getpid(),'started_unix':time.time(),'binding_sha256':sha(HERE/'BINDING.json'),'freeze_sha256':sha(HERE/'FREEZE.json'),'scope':'CPU/file-only; no API/service/GPU control; no global cleanup barrier'})
 subprocess.run(['ssh',HOST,'mkdir -p '+REMOTE],check=True)
 subprocess.run(['rsync','-a',str(HERE/'remote_consume.py'),str(HERE/'BINDING.json'),str(HERE/'PROTOCOL.txt'),str(HERE/'FREEZE.json'),HOST+':'+REMOTE+'/'],check=True)
 last=None
 while True:
  for lane,b in bind['lanes'].items():
   snap=call(['snapshot','--lane',lane]);(HERE/f'latest_snapshot_{lane}.stderr').write_text(snap.stderr)
   if snap.returncode:raise RuntimeError('snapshot failed '+lane+': '+snap.stderr[-1600:])
   info=json.loads(snap.stdout);save(HERE/f'latest_snapshot_{lane}.json',info)
   for run,x in info['runs'].items():
    if run in state['processed'] or run in state['failures']:continue
    if x['status']=='failed':state['failures'][run]={'type':'producer_failed','status':x};emit({'failed':run,'status':x});continue
    if x['status']!='success_files_present':continue
    before=state['stable'].get(run);tok=x['stability_token']
    if not before or before['token']!=tok:state['stable'][run]={'token':tok,'first_observed':time.time()};continue
    if time.time()-before['first_observed']<60:continue
    with CPU.open('a') as lock:
     try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
     except BlockingIOError:continue
     state['phase']='consuming '+run;save(statepath,state);emit({'consume_started':run})
     p=call(['consume','--lane',lane,'--run',run,'--token',tok]);(HERE/(run+'_consume.log')).write_text(p.stdout+'\nSTDERR\n'+p.stderr)
     if p.returncode==75:state['phase']='waiting CPU lock';continue
     if p.returncode:raise RuntimeError('run CPU consumer failed '+run+'; preserved log; no automatic resubmission')
     done=json.loads(p.stdout);dest=HERE/'captured'/run;dest.mkdir(parents=True,exist_ok=True)
     subprocess.run(['rsync','-a','--include=*/','--include=*.json','--include=*.log','--include=*.jpg','--include=*.mp4','--exclude=*',HOST+':'+REMOTE+'/captured/'+run+'/',str(dest)+'/'],check=True);verify_download(dest)
     state['processed'].append(run);state['phase']='waiting';save(statepath,state);emit({'consume_complete':run,'elapsed_seconds':done['elapsed_seconds']})
   for seed in (2026101610,2026101611):
    cid=b['case_id'];key=cid+'_seed'+str(seed);names=[f'r24_{cid}_seed{seed}_{a}' for a in ('native','full_6to14')]
    if key in state['pairs'] or not all(n in state['processed'] for n in names):continue
    with CPU.open('a') as lock:
     try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
     except BlockingIOError:continue
     p=call(['pair','--lane',lane,'--seed',str(seed)]);(HERE/(key+'_pair.log')).write_text(p.stdout+'\nSTDERR\n'+p.stderr)
     if p.returncode==75:continue
     if p.returncode:raise RuntimeError('pair gate failed '+key+'; preserved log')
     dest=HERE/'pairs'/key;dest.mkdir(parents=True,exist_ok=True);subprocess.run(['rsync','-a',HOST+':'+REMOTE+'/pairs/'+key+'/',str(dest)+'/'],check=True)
     state['pairs'].append(key);save(statepath,state);emit({'pair_complete':key})
  state['phase']='waiting';state['updated_unix']=time.time();save(statepath,state)
  compact={'processed':state['processed'],'pairs':state['pairs'],'failures':list(state['failures'])}
  if compact!=last:emit(compact);last=compact
  if len(state['processed'])==8 and len(state['pairs'])==4:
   checks={}
   for lane,b in bind['lanes'].items():
    cid=b['case_id'];runs=[f'r24_{cid}_seed{s}_native' for s in (2026101610,2026101611)]
    noise=[read(HERE/'captured'/n/'audit'/(n+'_noise.json')) for n in runs]
    checks[cid+'_crossseed_noise_differs']=all(x['sha256']!=y['sha256'] for x,y in zip(noise[0]['actual_noise_streams'],noise[1]['actual_noise_streams']))
   save(HERE/'BATCH_CHECKS.json',{'passed':all(checks.values()),'checks':checks,'basis':'Actual tensors verified in per-run gates before comparing signatures; allfour pair gates complete'})
   if not all(checks.values()):raise ValueError('cross-seed noise gate failed')
   state['phase']='all_eight_CPU_complete';save(statepath,state);emit({'complete':True,'note':'No GPU/service cleanup requested or claimed.'});return
  if len(state['processed'])+len(state['failures'])==8:
   state['phase']='finished_with_producer_failures';save(statepath,state);return
  # No compute lock is held during wait; wake every61s, no service polling/API.
  time.sleep(61)
if __name__=='__main__':
 try:main()
 except Exception as e:
  save(HERE/'CONSUMER_FAILURE.json',{'time':time.time(),'error':repr(e),'traceback':traceback.format_exc(),'no_GPU_retry':True});raise
