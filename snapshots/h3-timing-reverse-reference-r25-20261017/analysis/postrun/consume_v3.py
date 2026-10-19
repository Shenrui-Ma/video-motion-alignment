"""Single R25 CPU intake coordinator. Waits without global CPU locks."""
import fcntl,hashlib,json,os,shlex,subprocess,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
REMOTE='/data5/researcher/h3_runs/timing_reverse_reference_r25_20261017/analysis/postrun'
PYTHON='/home/researcher/miniconda3/envs/comfyui/bin/python'
HOST='H3_SERVER_A'
CPU=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def emit(d):print(json.dumps(d),flush=True)
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3']
def connect_check():
 for mode,extra in [('direct',[]),('jump',['-J','H3_SERVER_B'])]:
  p=subprocess.run(SSH+extra+[HOST,'/bin/true'],capture_output=True,text=True)
  with (HERE/'connections.jsonl').open('a') as f:f.write(json.dumps({'time':time.time(),'mode':mode,'exit':p.returncode,'stderr':p.stderr})+'\n')
  if p.returncode==0:return extra
 raise RuntimeError('Both recorded SSH transports failed; no duplicate remote CPU invocation')
def remote(args,extra):
 cmd=shlex.join(['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1',PYTHON,REMOTE+'/remote_consume_v3.py',*args])
 return subprocess.run(SSH+extra+[HOST,cmd],capture_output=True,text=True)
def sync(src,dst,extra,filter_output=False):
 cmd=['rsync','-a','-e',shlex.join(SSH+extra)]
 if filter_output:cmd+=['--include=*/','--include=*.json','--include=*.log','--include=*.jpg','--include=*.png','--include=*.mp4','--include=*.svg','--exclude=*']
 subprocess.run(cmd+[src,dst],check=True)
def verify_download(arc):
 inventory=read(arc/'FILE_INVENTORY.json')
 for rel,e in inventory.items():
  p=arc/rel
  if p.suffix=='.pt':continue
  if not p.is_file() or sha(p)!=e['sha256']:raise ValueError('archive download missing/changed '+rel)
 done=read(arc/'CPU_COMPLETE.json');video=arc/'output'/Path(done['video']).name;pose=arc/'pose'/Path(done['pose']).name
 if sha(video)!=done['video_sha256'] or sha(pose)!=done['pose_sha256']:raise ValueError('MP4/pose download SHA')
 probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','stream=width,height,r_frame_rate,avg_frame_rate,duration,time_base:frame=best_effort_timestamp_time','-of','json',str(video)]))
 s=probe['streams'][0]
 if not(s['width']==1312 and s['height']==736 and s['r_frame_rate']=='24/1' and s['avg_frame_rate']=='24/1' and len(probe['frames'])==141 and abs(float(s['duration'])-5.875)<1e-6):raise ValueError('playback geometry/rate')
 if any(abs(float(f['best_effort_timestamp_time'])-i/24)>1e-6 for i,f in enumerate(probe['frames'])):raise ValueError('physical PTS mismatch')
 save(arc/'PLAYBACK_GATE.json',{'passed':True,'video_sha256':sha(video),'probe':probe,'large_pt_retained_remote':True})
def main():
 unique=(HERE/'unique_consumer.lock').open('a');fcntl.flock(unique,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for rel,want in read(HERE/'FREEZE_v3.json')['files'].items():
  if sha(HERE/rel)!=want:raise ValueError('consumer file changed after freeze '+rel)
 statepath=HERE/'STATE.json';state=read(statepath) if statepath.exists() else {'processed':[],'failures':{},'stable':{},'comparison_complete':False,'phase':'waiting'}
 save(HERE/'consumer_identity.json',{'pid':os.getpid(),'started_unix':time.time(),'freeze_sha256':sha(HERE/'FREEZE_v3.json'),'binding_sha256':sha(HERE/'BINDING.json'),'scope':'CPU/file only; no GPU/API/service control'})
 extra=connect_check();subprocess.run(SSH+extra+[HOST,'mkdir -p '+REMOTE],check=True)
 for name in ('remote_consume_v3.py','BINDING.json','PROTOCOL.txt','FREEZE_v3.json','RECOVERY.json'):sync(str(HERE/name),HOST+':'+REMOTE+'/',extra)
 while True:
  for lane,b in read(HERE/'BINDING.json')['lanes'].items():
   run=b['run_id']
   if run in state['processed'] or run in state['failures']:continue
   p=remote(['snapshot','--lane',lane],extra)
   if p.returncode==255:
    extra=connect_check();p=remote(['snapshot','--lane',lane],extra)
   (HERE/f'latest_{lane}.stderr').write_text(p.stderr)
   if p.returncode:raise RuntimeError('read-only snapshot failed '+lane+': '+p.stderr[-2000:])
   x=json.loads(p.stdout);save(HERE/f'latest_{lane}.json',x)
   if x['status']=='failed':state['failures'][run]=x;save(statepath,state);emit({'producer_failed':run});continue
   if x['status']!='success_files_present':continue
   token=x['stability_token'];old=state['stable'].get(run)
   if not old or old['token']!=token:state['stable'][run]={'token':token,'time':time.time()};continue
   if time.time()-old['time']<60:continue
   with CPU.open('a') as lock:
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:continue
    state['phase']='consuming '+run;save(statepath,state);emit({'consume_started':run})
    p=remote(['consume','--lane',lane,'--token',token],extra);(HERE/(run+'_consume.log')).write_text(p.stdout+'\nSTDERR\n'+p.stderr)
    if p.returncode==75:state['phase']='waiting remote CPU lock';continue
    if p.returncode:raise RuntimeError('CPU consume failed; no automatic retry '+run)
    done=json.loads(p.stdout);dest=HERE/'captured'/run;dest.mkdir(parents=True,exist_ok=True)
    sync(HOST+':'+REMOTE+'/captured/'+run+'/',str(dest)+'/',extra,True);verify_download(dest)
    state['processed'].append(run);state['phase']='waiting';save(statepath,state);emit({'consume_complete':run,'elapsed':done['elapsed_seconds'],'compact':read(dest/'COMPACT_RESULTS.json')})
  if len(state['processed'])==2 and not state['comparison_complete']:
   with CPU.open('a') as lock:
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:pass
    else:
     p=remote(['compare'],extra);(HERE/'comparison.log').write_text(p.stdout+'\nSTDERR\n'+p.stderr)
     if p.returncode not in (0,75):raise RuntimeError('common-support comparison failed')
     if p.returncode==0:
      dest=HERE/'comparison';dest.mkdir(exist_ok=True);sync(HOST+':'+REMOTE+'/comparison/',str(dest)+'/',extra)
      for rel,want in read(dest/'FILES.json').items():
       if sha(dest/rel)!=want:raise ValueError('comparison download SHA')
      state['comparison_complete']=True;save(statepath,state)
  state['updated_unix']=time.time();save(statepath,state)
  if len(state['processed'])==2 and state['comparison_complete']:state['phase']='CPU_complete';save(statepath,state);emit({'complete':True,'no_cleanup_claim':True});return
  if len(state['processed'])+len(state['failures'])==2:state['phase']='finished_with_failures';save(statepath,state);return
  time.sleep(61)
if __name__=='__main__':
 try:main()
 except Exception as e:
  save(HERE/'CONSUMER_FAILURE_v3.json',{'time':time.time(),'error':repr(e),'traceback':traceback.format_exc(),'no_GPU_retry':True});raise
