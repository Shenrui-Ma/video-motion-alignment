"""Finite two-arm lane; no retries, restarts, inherited queue, or scheduler."""
import fcntl,json,os,signal,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import manage_service
from admission import preflight
from verify_result import verify

def atomic(path,data):
 path=Path(path);tmp=path.with_name(path.name+'.tmp.'+str(os.getpid()));tmp.write_text(json.dumps(data,indent=2));os.replace(tmp,path)
def identity(pid):
 p=Path('/proc')/str(pid);s=(p/'stat').read_text().rsplit(')',1)[1].split()
 return {'pid':pid,'uid':p.stat().st_uid,'start_ticks':s[19],'state':s[0],'cmdline':(p/'cmdline').read_bytes().replace(b'\0',b' ').decode()}
def interrupted(signum,frame):raise RuntimeError('Worker stop signal '+str(signum))

def main():
 cfg=json.loads((ROOT/'CONFIG.json').read_text());lock=(ROOT/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if (ROOT/'worker_pid.json').exists():raise RuntimeError('This lane has already been launched; inspect existing evidence')
 preflight(ROOT)
 atomic(ROOT/'worker_pid.json',{**identity(os.getpid()),'boot_id':cfg['boot_id'],'created_unix':time.time()})
 signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
 child=None;completed=[];failure=None;service=None
 try:
  atomic(ROOT/'worker_status.json',{'event':'starting','time':time.time()})
  service=manage_service.start()
  schema=manage_service.api('object_info');needed=['H3StudyReference','H3StudySchedule','H3StudyTiming','MiniMaxH3SigmaShift','UNETLoader','CLIPLoader','LoadVideo','GetVideoComponents','SaveVideo']
  assert all(n in schema for n in needed), 'Missing required node schema'
  atomic(ROOT/'SCHEMA_CHECK.json',{'passed':True,'required':needed,'at':time.time(),'service':service})
  for arm in cfg['arms']:
   assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==cfg['boot_id']
   assert manage_service.alive(service), 'Service exited before arm'
   q=manage_service.api('queue');assert not q.get('queue_running') and not q.get('queue_pending'), 'Unexpected active prompt'
   atomic(ROOT/'worker_status.json',{'event':'running','arm':arm,'completed':completed,'time':time.time()})
   args=[sys.executable,str(ROOT/'queue/durable_comfy_queue.py'),'--manifest',str(ROOT/'manifests'/f'{arm}.json'),'--state-dir',str(ROOT/'queue_state'),'--comfy-url',f'http://127.0.0.1:{cfg["port"]}','--output-root',str(ROOT/'output'),'--max-attempts','1','--max-service-restarts','0','--poll-seconds','2','--stall-timeout','900','--recovery-seconds','60','--request-timeout','15']
   with (ROOT/'logs/queue.log').open('ab',buffering=0) as log:child=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=log,stderr=log)
   result=child.wait(timeout=7200);child=None
   assert result==0, 'Queue failed: '+str(result)
   checked=verify(ROOT,arm);atomic(ROOT/(arm+'_VERIFIED.json'),checked);completed.append(arm)
 except BaseException as error:
  failure={'type':type(error).__name__,'error':str(error),'traceback':traceback.format_exc()}
 finally:
  if child is not None and child.poll() is None:
   child.terminate()
   try:child.wait(timeout=10)
   except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
  cleanup=manage_service.stop(service) if service else manage_service.stop()
  atomic(ROOT/'worker_status.json',{'event':'finished' if failure is None else 'failed','completed':completed,'failure':failure,'cleanup':cleanup,'time':time.time(),'no_retry':True})
 return 0 if failure is None and cleanup['stopped'] else 1
if __name__=='__main__':sys.exit(main())
