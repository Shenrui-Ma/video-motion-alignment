"""R20 single read-only waiter plus existing-tool CPU consumer. No GPU/service/API."""
import argparse,fcntl,hashlib,importlib.util,json,os,shlex,subprocess,sys,time
from pathlib import Path,PurePosixPath
REMOTE='/data5/researcher/h3_runs/timing_cross_source_r20_20261016'
LOCAL='/Users/researcher/DevProjects/h3-timing-cross-source-r20-host9-20261016'
OLD='/data5/researcher/h3_runs/timing_autoresearch_20261016'
HOST='H3_SERVER_A'; PYTHON='/home/researcher/miniconda3/envs/comfyui/bin/python'
RUNS=('r20_s07_native','r20_s07_full_6to14')
PID=56411;TICKS='2619166090';CMD='646efaa87fcbcee32bf5bbd823cb2fd38e5c14e78f8432e07835ec293308a68f'
MANIFEST='4b3067f0fac7fdbe3debb66c8395bfa460618d1a6378e167b5ea1c2c5a1eca92'
GPU='GPU-REDACTED'
SOURCE_SHA='46637cac9d2aba836b96962b0ffcd62607f15264d8bf81b0886e82c552666a11'
FROZEN={'scripts/pose_probe.py':'04c6dd432ddf102300a4cd065f4de8b9c2bc0661ce1abb06d994330b32ae693f','scripts/timing_metrics.py':'eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e','analysis/pose/compare_runs.py':'1e725cd5063ae9e9e770f94c54c91dfa5d0473e951e92dfcebaa56619c844b33','analysis/pose/old_sam/07_real_ary_v.pose.json':'962d87b14a569515c01424e1b074dc8a827f02ee2b8cd8ca3fc7b23a534760bc'}
WINDOWS=('54:69','75:88','98:111');VISUAL=(60,63,81,105)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n');tmp.replace(p)
def check(cond,msg):
 if not cond:raise ValueError(msg)
def remote(argv):return subprocess.check_output(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2',HOST,shlex.join(argv)],text=True)
def snapshot():
 r=Path(REMOTE);m=r/'audit/deployment_manifest_v1.json';check(sha(m)==MANIFEST,'deployment manifest changed')
 rec=read(r/'processes/service.json');check(rec['pid']==PID and rec['identity']['start_ticks']==TICKS and rec['identity']['uid']==1016 and rec['gpu_uuid']==GPU and rec['port']==8480,'service binding mismatch')
 proc=Path('/proc')/str(PID);alive=proc.exists()
 if alive:
  try:
   uid=proc.stat().st_uid; fields=proc.joinpath('stat').read_text().split(') ',1)[1].split(); cmd=proc.joinpath('cmdline').read_bytes()
  except FileNotFoundError:
   if not proc.exists():alive=False
   else:raise
  if alive:
   check(uid==1016 and fields[19]==TICKS,'live service identity mismatch')
   # Reap/cleanup may race this read-only snapshot; a pinned zombie still waits.
   # A non-zombie must retain the exact registered command, never allow a new PID.
   if fields[0]!='Z':check(hashlib.sha256(cmd).hexdigest()==CMD,'live command identity mismatch')
 cpath=r/'logs/controller_state.json';c=read(cpath) if cpath.exists() else {}
 histories={};errors=[]
 for run in RUNS:
  p=r/'logs'/f'{run}_history.json'
  if p.exists():
   h=read(p);histories[run]=h.get('status',{})
   if h.get('status',{}).get('status_str')=='error':errors.append(run)
 if c.get('status') in ('failed','error'):errors.append('controller:'+str(c))
 cp=r/'processes/cleanup.json';cleanup=read(cp) if cp.exists() else None
 ready=all(histories.get(run,{}).get('status_str')=='success' and histories[run].get('completed') for run in RUNS)
 ready=ready and c.get('status')=='all_queued_jobs_complete' and c.get('completed')==list(RUNS)
 ready=ready and not alive and cleanup is not None and cleanup.get('service_record')==rec and cleanup.get('process_absent') is True and cleanup.get('own_compute_absent') is True
 auxiliaries={}
 for role in ('supervisor','watchdog','controller'):
  p=r/'processes'/f'{role}.json'
  if p.exists():
   row=read(p);auxiliaries[role]={'pid':row['pid'],'exists':(Path('/proc')/str(row['pid'])).exists()}
 if any(x['exists'] for x in auxiliaries.values()):ready=False
 if errors:status='failed'
 elif ready:status='ready'
 elif not alive and c.get('status')!='all_queued_jobs_complete':status='failed'
 else:status='waiting'
 result={'time':time.time(),'status':status,'service_alive':alive,'controller':c,'histories':histories,'auxiliaries':auxiliaries,'errors':errors}
 if ready:
  p=subprocess.run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True)
  result['compute_csv']=p.stdout;check(not any(line.split(',')[1].strip()==str(PID) for line in p.stdout.splitlines() if ',' in line),'service remains in compute listing')
  result['gpu_csv']=subprocess.check_output(['nvidia-smi','-i',GPU,'--query-gpu=uuid,memory.used,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip()
 print(json.dumps(result));return result

def exact_video(r,run):
 h=read(r/'logs'/f'{run}_history.json');g=read(r/'configs'/f'{run}.json')
 check(h['status']['status_str']=='success' and h['status']['completed'] and h['prompt'][2]==g,'actual success/config required')
 items=[i for k,n in g.items() if n['class_type']=='SaveVideo' for i in h['outputs'].get(k,{}).get('images',[]) if i.get('type')=='output' and i.get('filename','').endswith('.mp4')]
 check(len(items)==1,'one exact SaveVideo output required');item=items[0];rel=PurePosixPath(item.get('subfolder',''))/item['filename'];check(not rel.is_absolute() and '..' not in rel.parts,'unsafe video path')
 p=r/'output'/rel;check(not p.is_symlink(),'video symlink rejected');return p

def cpu():
 os.environ['CUDA_VISIBLE_DEVICES']=''
 for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='4'
 r=Path(REMOTE);out=r/'analysis/pose';out.mkdir(parents=True,exist_ok=True)
 lock=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:print('R20_CPU_LOCK_BUSY');return 75
 check(snapshot()['status']=='ready','producer not fully released')
 m=read(r/'audit/deployment_manifest_v1.json');check(len(m['files'])==61,'deployment requires61files')
 for rel,meta in m['files'].items():
  p=r/rel;check(not Path(rel).is_absolute() and '..' not in Path(rel).parts and p.resolve().is_relative_to(r) and not p.is_symlink(),'unsafe deployment path');check(sha(p)==meta['sha256'] and p.stat().st_size==meta['bytes'],'actual deployment mismatch:'+rel)
 save(out/'deployment_integrity.json',{'passed':True,'files':len(m['files']),'manifest_sha256':sha(r/'audit/deployment_manifest_v1.json')})
 start=time.time()
 with (out/'verify_pair.log').open('w') as log:
  subprocess.run([sys.executable,str(r/'scripts/verify_pair.py'),'--output',str(r/'audit/completed_pair_gate.json')],stdout=log,stderr=subprocess.STDOUT,check=True)
 check(read(r/'audit/completed_pair_gate.json')['passed'],'pair gate failed')
 integrity_seconds=time.time()-start
 for rel,digest in FROZEN.items():check(sha(Path(OLD)/rel)==digest,'frozen tool/source changed:'+rel)
 source=Path(OLD)/'analysis/pose/old_sam/07_real_ary_v.pose.json';check(read(source)['video']['sha256']==SOURCE_SHA,'wrong source pose')
 p=subprocess.check_output(['ps','-u',str(os.getuid()),'-o','pid=,args='],text=True)
 check(not any(any(s in line for s in ('pose_probe.py','timing_metrics.py')) for line in p.splitlines()),'existing pose CPU process; refuse overlap')
 import cv2
 cv2.setNumThreads(1)
 pilot=out/'pilot';pilot.mkdir(exist_ok=True);records={};poses={}
 for run in RUNS:
  v=exact_video(r,run);vs=sha(v);c=cv2.VideoCapture(str(v));frames=0;rgbhash=hashlib.sha256();first=[]
  fps=c.get(cv2.CAP_PROP_FPS);w=int(c.get(cv2.CAP_PROP_FRAME_WIDTH));h=int(c.get(cv2.CAP_PROP_FRAME_HEIGHT))
  while True:
   ok,im=c.read()
   if not ok:break
   check(im.shape==(736,1312,3),'bad decoded shape');rgbhash.update(im.tobytes());frames+=1
  c.release();check((frames,w,h)==(141,1312,736) and abs(fps-24)<1e-6,'decoded video geometry changed')
  pose=pilot/(v.stem+'.pose.json');extract_start=time.time();cached=pose.exists() and read(pose)['video']['sha256']==vs
  if not cached:
   cmd=[sys.executable,OLD+'/scripts/pose_probe.py','--video',str(v),'--output-dir',str(pilot),'--threads','4']
   for frame in VISUAL:cmd+=['--overlay-frame',str(frame)]
   with (pilot/(v.stem+'.extract.log')).open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
  check(read(pose)['video']['sha256']==vs,'pose source mismatch');poses[run]=pose
  records[run]={'video':str(v),'sha256':vs,'bytes':v.stat().st_size,'decoded_frames':frames,'fps':fps,'width':w,'height':h,'decoded_BGR_sha256':rgbhash.hexdigest(),'pose_sha256':sha(pose),'pose_seconds':time.time()-extract_start,'pose_cache_reused':cached}
  for threshold in (.3,.5):
   cmd=[sys.executable,OLD+'/scripts/timing_metrics.py','--source',str(source),'--edited',str(pose),'--confidence',str(threshold),'--output-dir',str(pilot)]
   for window in WINDOWS:cmd+=['--window',window]
   with (pilot/(v.stem+f'.threshold{threshold}.log')).open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
  check(sha(v)==vs,'raw video changed during evaluation')
 common=out/'common_support';common.mkdir(exist_ok=True)
 for threshold in (.3,.5):
  cmd=[sys.executable,OLD+'/analysis/pose/compare_runs.py','--source',str(source),'--confidence',str(threshold),'--output',str(common/f'threshold{threshold}.json')]
  for run,p in poses.items():cmd+=['--run',run+'='+str(p)]
  for window in (*WINDOWS,'0:140','0:51','52:72','73:140','112:140'):cmd+=['--window',window]
  with (common/f'threshold{threshold}.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
 result={'status':'CPU_complete','runs':records,'frozen':FROZEN,'source_video_sha256':SOURCE_SHA,'windows':WINDOWS,'visual_frames':VISUAL,'integrity_seconds':integrity_seconds,'total_CPU_consumer_seconds':time.time()-start,'no_GPU':True,'all_UNKNOWN_retained':True,'scope':'second development case; no new method/unseen/generalization claim'}
 save(out/'cpu_complete.json',result);print(json.dumps(result));return 0

def fetch(local):
 for folder in ('analysis/pose','logs','processes'):
  dst=local/folder;dst.mkdir(parents=True,exist_ok=True)
  subprocess.run(['rsync','-az','--exclude=*.lock',f'{HOST}:{REMOTE}/{folder}/',str(dst)+'/'],check=True)
 paths=['audit/completed_pair_gate.json','audit/deployment_manifest_v1.json','configs/runtime_provenance.json']
 for run in RUNS:
  paths += [f'audit/{run}_conditioning.json',f'audit/{run}_noise.json',f'audit/router/{run}.json',f'audit/x0/{run}/manifest.json']
 for rel in paths:
  dst=local/'analysis/pose/remote_evidence'/rel;dst.parent.mkdir(parents=True,exist_ok=True)
  subprocess.run(['scp','-q',f'{HOST}:{REMOTE}/{rel}',str(dst)],check=True)
 data=read(local/'analysis/pose/cpu_complete.json')
 for run,meta in data['runs'].items():
  dst=local/'analysis/pose/raw'/Path(meta['video']).name;dst.parent.mkdir(exist_ok=True)
  subprocess.run(['scp','-q',f'{HOST}:{meta["video"]}',str(dst)],check=True);check(sha(dst)==meta['sha256'],'local raw SHA mismatch')
 save(local/'analysis/pose/download_complete.json',{'passed':True,'time':time.time(),'raw_count':2})

def wait():
 local=Path(LOCAL);out=local/'analysis/pose';out.mkdir(parents=True,exist_ok=True)
 with (out/'coordinator.lock').open('a') as coord:
  fcntl.flock(coord,fcntl.LOCK_EX|fcntl.LOCK_NB);save(out/'consumer_identity.json',{'pid':os.getpid(),'started':time.time(),'service_pid':PID,'mode':'wait-no-CPU-lock'})
  deadline=time.monotonic()+3*3600
  while time.monotonic()<deadline:
   try:s=json.loads(remote(['python3',REMOTE+'/analysis/pose/consume_r20.py','--snapshot']).splitlines()[-1])
   except subprocess.CalledProcessError as e:
    save(out/'consumer_failure.json',{'stage':'snapshot','error':repr(e),'no_restart':True});raise
   save(out/'last_snapshot.json',s)
   with (out/'snapshot_history.jsonl').open('a') as log:log.write(json.dumps(s)+'\n')
   if s['status']=='failed':raise RuntimeError('R20 producer failure; preserve logs; no restart')
   if s['status']=='ready':
    with Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a') as lock:
     try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
     except BlockingIOError:time.sleep(61);continue
     cmd=['env','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1',PYTHON,REMOTE+'/analysis/pose/consume_r20.py','--cpu']
     with (out/'remote_cpu.log').open('w') as log:
      code=subprocess.call(['ssh','-o','BatchMode=yes','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2',HOST,shlex.join(cmd)],stdout=log,stderr=subprocess.STDOUT)
     if code==75:fcntl.flock(lock,fcntl.LOCK_UN);time.sleep(61);continue
     if code:save(out/'consumer_failure.json',{'stage':'remote_cpu','exit_code':code,'no_blind_reexecution':True});raise RuntimeError('CPU consumer failed; inspect log, no restart')
     fetch(local);save(out/'consumer_complete.json',{'passed':True,'time':time.time(),'service_pid':PID});return
   time.sleep(61)
  raise TimeoutError('R20 waiter timeout; no service changes')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--wait',action='store_true');p.add_argument('--snapshot',action='store_true');p.add_argument('--cpu',action='store_true');a=p.parse_args()
 if a.snapshot:snapshot()
 elif a.cpu:raise SystemExit(cpu())
 elif a.wait:wait()
 else:p.error('explicit read-only mode required')
