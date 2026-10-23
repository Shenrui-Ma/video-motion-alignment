"""Finite real-job worker: waits for resources, runs queue, releases own service."""
import fcntl,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WAIT_HOST9='host9' in str(ROOT)

def log(event,**kw):
 row={'event':event,'unix':time.time(),**kw};print(json.dumps(row),flush=True)
 (ROOT/'worker_status.json').write_text(json.dumps(row,indent=2))

def select_gpu():
 # All allocations on .9 belonging to this UID count toward the user's two-card cap.
 with open('/tmp/h3-20261022-admission.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True,timeout=20)
  occupied=set();ours=set()
  for row in raw.splitlines():
   u,p=[x.strip() for x in row.split(',')];occupied.add(u)
   try:
    if (Path('/proc')/p).stat().st_uid==os.getuid():ours.add(u)
   except FileNotFoundError:pass
  for cp in Path('/tmp').glob('h3-20261022-claim-*.json'):
   try:
    c=json.loads(cp.read_text());actual=(Path('/proc')/str(c['pid'])/'stat').read_text().split()[21]
    if actual==c['start_ticks'] and time.time()-c['unix']<900:ours.add(cp.name[len('h3-20261022-claim-'):-5])
   except (FileNotFoundError,ValueError,KeyError):pass
  if len(ours)>=2:return False
  raw=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=20)
  for row in raw.splitlines():
   i,u,free,util=[x.strip() for x in row.split(',')]
   policy_path=ROOT/'shared_gpu_authorization.json'
   policy=json.loads(policy_path.read_text()) if policy_path.exists() else {}
   shared=(policy.get('gpu_uuid')==u and policy.get('allow_shared') is True)
   if shared:
    if float(free)<float(policy.get('minimum_free_mib',46000)):continue
   elif u in occupied or float(free)<70000 or float(util)>5:continue
   # A short CPU-side admission claim prevents two waiters choosing the same GPU.
   claim=Path('/tmp/h3-20261022-claim-'+u+'.json')
   if claim.exists():
    c=json.loads(claim.read_text())
    try:
     actual=(Path('/proc')/str(c['pid'])/'stat').read_text().split()[21]
     if actual==c['start_ticks'] and time.time()-c['unix']<900 and c['pid']!=os.getpid():continue
    except FileNotFoundError:pass
   ident=(Path('/proc')/str(os.getpid())/'stat').read_text().split()[21]
   claim.write_text(json.dumps({'pid':os.getpid(),'start_ticks':ident,'unix':time.time()}))
   (ROOT/'gpu.json').write_text(json.dumps({'gpu_uuid':u,'index':int(i)}));return True
  return False

def main():
 with open(ROOT/'worker.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  deadline=time.time()+48*3600
  while time.time()<deadline:
   try:
    existing=False
    try:
     rec=json.loads((ROOT/'service.json').read_text());proc=Path('/proc')/str(rec['pid'])
     existing=proc.stat().st_uid==os.getuid() and (proc/'stat').read_text().split()[21]==rec['start_ticks'] and str(ROOT).encode() in (proc/'cmdline').read_bytes()
    except (FileNotFoundError,KeyError,ValueError):pass
    if WAIT_HOST9 and not existing and not select_gpu():log('waiting_free_gpu');time.sleep(60);continue
    cmd=[sys.executable,str(ROOT/'scripts/manage_service.py'),'start']
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=650)
    if result.returncode:raise RuntimeError(result.stderr[-1800:])
    log('service_ready',output=result.stdout[-1200:]);break
   except Exception as e:log('admission_retry',error=str(e));time.sleep(60)
  else:log('resource_wait_expired');return
  port=8673 if str(ROOT).endswith('host9a') else 8674 if str(ROOT).endswith('host9b') else 8672
  command=[sys.executable,str(ROOT/'queue/durable_comfy_queue.py'),'--manifest',str(ROOT/'jobs.json'),'--state-dir',str(ROOT/'queue_state'),'--comfy-url',f'http://127.0.0.1:{port}','--output-root',str(ROOT/'output'),'--max-attempts','1','--max-service-restarts','6','--restart-command',json.dumps([sys.executable,str(ROOT/'scripts/manage_service.py'),'restart'])]
  code=None
  try:
   for attempt in range(3):
    log('queue_running',supervisor_attempt=attempt+1)
    code=subprocess.run(command,cwd=ROOT).returncode
    if code!=2:break
    log('queue_recovery_wait',exit_code=code);time.sleep(60)
  finally:
   # Touch only the exact task-owned PID verified by manage_service.
   r=subprocess.run([sys.executable,str(ROOT/'scripts/manage_service.py'),'stop'],capture_output=True,text=True,timeout=60)
   log('finished',queue_exit_code=code,cleanup_code=r.returncode,cleanup=r.stdout[-1200:])
if __name__=='__main__':main()
