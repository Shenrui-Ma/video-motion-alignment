"""Run the transferred fixed-strength pilot, audit it, then release the remaining active real jobs."""
from pathlib import Path
import os,json,time,fcntl,hashlib,subprocess,math
R=Path('/data4/research-user/h3_inference_20261023/run');D=R/'handoff';D.mkdir(exist_ok=True)
def read(p,default=None):return json.loads(p.read_text()) if p.exists() else default
def atomic(p,x):
 t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,indent=2,allow_nan=False));t.replace(p)
def ident(pid):
 p=Path('/proc')/str(pid);v=(p/'stat').read_text().rsplit(')',1)[1].split();return {'pid':pid,'uid':p.stat().st_uid,'start_ticks':v[19],'state':v[0]}
def live(rec):
 if not rec:return False
 try:
  now=ident(rec['pid'])
  if now['uid']!=rec['uid'] or now['start_ticks']!=str(rec['start_ticks']):return False
  return now['state']!='Z'
 except FileNotFoundError:return False
def reap():
 try:
  while os.waitpid(-1,os.WNOHANG)[0]:pass
 except ChildProcessError:pass
def launch(label):
 rd,wr=os.pipe();cmd=['python3','-c','import os,sys;os.read(int(sys.argv[1]),1);os.execv(sys.executable,[sys.executable,sys.argv[2]])',str(rd),str(R/'scripts/host_worker.py')]
 with (R/'logs/worker.log').open('a') as log:p=subprocess.Popen(cmd,pass_fds=(rd,),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 os.close(rd);i=ident(p.pid);atomic(R/'worker_pid.json',i);receipt={'phase':label,'worker':i,'time':time.time()};atomic(D/'phase.json',receipt);os.write(wr,b'1');os.close(wr);return receipt

def audit_first(job,st):
 attempt=st['attempt_id'];result=read(Path(st['result']));assert result['job_id']==job['id']
 files=result['files'];assert files
 for row in files:
  p=Path(row['path']);assert p.is_file() and p.stat().st_size==row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
  stream=row['probe']['streams'][0];g=job['metadata']['geometry'];assert int(stream['nb_frames'])==g['frames'] and stream['width']==g['width'] and stream['height']==g['height']
 t=read(R/'audit/timing'/(attempt+'.json'));assert t['passed'] and len(t['per_step_seconds'])==20 and all(math.isfinite(x) and x>0 for x in t['per_step_seconds'])
 audit=R/'audit/feature_guidance'/(attempt+'.json');out=D/'first_audit.json'
 p=subprocess.run(['python3',str(R/'scripts/adaptive_audit.py'),str(audit),'--kind','feature','--output',str(out)],capture_output=True,text=True);assert p.returncode==0,p.stderr
 a=read(out);assert a['routed_calls']==1000 and a['status']=='passed'
 atomic(D/'FIRST_VERIFIED.json',{'job':job['id'],'audit':a,'files':files,'timing':t,'time':time.time()})

with (D/'guard.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);atomic(D/'guard_pid.json',ident(os.getpid()))
 transfer=read(D/'TARGET_OWNERSHIP.json');assert transfer['status']=='target_owned' and len(transfer['manifest']['jobs']) in (3,4)
 jobs=transfer['manifest']['jobs'];assert jobs[0]['id'].endswith('fixed0375') and all(j['max_attempts']==1 for j in jobs)
 while True:
  reap();phase=read(D/'phase.json',{});states=read(R/'queue_state/state.json',{}).get('jobs',{})
  if not phase:
   assert read(R/'jobs.json')['jobs']==jobs[:1];assert not states
   phase=launch('first_running')
  if phase['phase']=='remaining_running':
   atomic(D/'status.json',{'status':'remaining_submitted','worker':phase['worker'],'time':time.time()});break
  first=states.get(jobs[0]['id'],{})
  if live(phase['worker']):
   atomic(D/'status.json',{'status':'first_running','state':first.get('status','initializing'),'worker':phase['worker'],'time':time.time()});time.sleep(30);continue
  if first.get('status')!='completed':
   atomic(D/'status.json',{'status':'blocked_first_pilot','first_state':first,'remaining_submitted':False,'time':time.time()});break
  service=read(R/'service.json')
  if service:
   service['uid']=os.getuid()
   if live(service):time.sleep(10);continue
  for name in ['worker.lock','queue_state/runner.lock']:
   with (R/name).open('a') as gate:fcntl.flock(gate,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:audit_first(jobs[0],first)
  except Exception as e:
   atomic(D/'status.json',{'status':'blocked_first_audit','error':repr(e),'remaining_submitted':False,'time':time.time()});break
  actual=read(R/'jobs.json');assert actual['jobs'] in (jobs[:1],jobs)
  atomic(R/'jobs.json',transfer['manifest']);phase=launch('remaining_running')
