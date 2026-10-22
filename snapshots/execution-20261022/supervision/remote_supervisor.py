"""Bounded recovery for this study's remote CPU supervisors after host reboot."""
import fcntl,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
HOSTS=[('H3_SERVER_B','/data4/researcher/h3_runs/benchmark_schedule_20261022'),('H3_SERVER_A','/home/researcher/h3_runs/benchmark_schedule_20261022_host9a'),('H3_SERVER_A','/home/researcher/h3_runs/benchmark_schedule_20261022_host9b')]
REMOTE=r'''
from pathlib import Path
import fcntl,json,os,subprocess,sys
r=Path(sys.argv[1]); allow=sys.argv[2]=='yes'
def read(p):return json.loads(p.read_text()) if p.exists() else {}
def alive(rec):
 try:
  p=Path('/proc')/str(rec['pid'])
  return p.stat().st_uid==os.getuid() and (p/'stat').read_text().split()[21]==rec['start_ticks'] and str(r/'scripts/host_worker.py').encode() in (p/'cmdline').read_bytes()
 except (FileNotFoundError,KeyError):return False
rec=read(r/'worker_pid.json');status=read(r/'worker_status.json')
if not rec or not status:raise RuntimeError('Missing owned worker record')
result={'root':str(r),'status':status.get('event'),'alive':alive(rec),'restarted':False}
if result['alive'] or result['status'] in ('finished','resource_wait_expired') or not allow:
 print(json.dumps(result));sys.exit(0)
# An orphaned queue may still own the GPU job; let it finish before recovery.
locks=[]
for p in [r/'worker.lock',r/'queue_state/runner.lock']:
 if p.exists():
  f=open(p,'a')
  try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:
   result['status']='existing_queue_or_worker_lock';print(json.dumps(result));sys.exit(0)
  locks.append(f)
for f in locks:f.close()
with open(r/'logs/worker.log','ab') as log:
 child=subprocess.Popen(['python3','-u',str(r/'scripts/host_worker.py')],cwd=r,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
rec={'pid':child.pid,'start_ticks':(Path('/proc')/str(child.pid)/'stat').read_text().split()[21]}
p=r/'worker_pid.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(rec));os.replace(tmp,p)
result.update(restarted=True,worker=rec);print(json.dumps(result))
'''
def atomic(p,d):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(d,indent=2));os.replace(q,p)
def main():
 with open(ROOT/'supervisor.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  p=ROOT/'state.json';state=json.loads(p.read_text()) if p.exists() else {'started':time.time(),'restarts':{},'hosts':{}}
  while time.time()-state['started']<48*3600 and not (ROOT/'STOP').exists():
   terminal=0
   for host,path in HOSTS:
    key=host+':'+path;count=state['restarts'].get(key,0)
    try:
     res=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=2',host,'python3','-',path,'yes' if count<3 else 'no'],input=REMOTE,text=True,capture_output=True,timeout=40,check=True)
     row=json.loads(res.stdout.strip());row['checked']=time.time()
     if row['restarted']:state['restarts'][key]=count+1
     if row['status'] in ('finished','resource_wait_expired'):terminal+=1
     state['hosts'][key]=row
    except Exception as e:state['hosts'][key]={'checked':time.time(),'error':str(e)}
    atomic(p,state)
   if terminal==len(HOSTS):state['finished']=time.time();atomic(p,state);return
   time.sleep(60)
  state['ended']=time.time();atomic(p,state)
if __name__=='__main__':main()
