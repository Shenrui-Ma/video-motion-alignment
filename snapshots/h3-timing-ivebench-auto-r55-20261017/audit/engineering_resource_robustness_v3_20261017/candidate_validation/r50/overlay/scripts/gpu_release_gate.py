"""Bounded standalone-gate NVML tail wait; production resource guards are untouched."""
import subprocess,time

def wait_after_child(uuid,child,assert_idle,identity,timeout=10.0,clock=time.monotonic,sleep=time.sleep,compute_pids=None):
 if not 0<timeout<=10:raise ValueError('release wait must be positive and at most10seconds')
 if child['returncode']!=0:raise RuntimeError('decoder did not exit successfully')
 entry=child['process'];start=clock();attempts=[]
 def query():
  raw=subprocess.check_output(['nvidia-smi','--id='+uuid,'--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True,timeout=2)
  return [int(v.strip()) for v in raw.splitlines() if v.strip()]
 get=compute_pids or query
 while True:
  current=identity(entry['pid'])
  if current is not None:raise RuntimeError('original decoder PID still live or reused')
  pids=get()
  if any(pid!=entry['pid'] for pid in pids):raise RuntimeError('foreign GPU compute process appeared after decoder exit')
  try:
   result=assert_idle(uuid)
   return {'idle':result,'wait_seconds':clock()-start,'attempts':attempts,'decoder_identity_absent':True,'strict_original_idle_assertion_passed':True}
  except (RuntimeError,ValueError) as error:
   if str(error) not in ('GPU is not idle; refusing offline decode','GPU has a compute process; refusing offline decode','decoder GPU has active compute','decoder GPU lacks idle headroom'):raise
   attempts.append({'elapsed_seconds':clock()-start,'error':str(error),'compute_pids':pids})
   if clock()-start>=timeout:raise TimeoutError('strict GPU idle did not settle within10seconds') from error
   sleep(min(.25,timeout-(clock()-start)))


def wait_own_child_released(uuid,child,identity,*,timeout=10.0,clock=time.monotonic,sleep=time.sleep,compute_pids=None,audit_path=None):
 """Check our reaped generation and NVML tail; unrelated work may continue."""
 import json,os
 if not 0<timeout<=10:raise ValueError('release wait must be positive and at most10seconds')
 if child['returncode']!=0:raise RuntimeError('decoder did not exit successfully')
 entry=child['process'];start=clock();attempts=[]
 def query():
  raw=subprocess.check_output(['nvidia-smi','--id='+uuid,'--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True,timeout=2)
  return [int(v.strip()) for v in raw.splitlines() if v.strip()]
 def log(record):
  if audit_path is not None:
   with open(audit_path,'a') as handle:
    handle.write(json.dumps(record,sort_keys=True,allow_nan=False)+'\n');handle.flush();os.fsync(handle.fileno())
 while True:
  current=identity(entry['pid']);pids=(compute_pids or query)()
  snapshot={'gpu_uuid':uuid,'child_identity':entry,'current_identity':current,'compute_pids':pids,'elapsed_seconds':clock()-start}
  same_generation=current is not None and current['pid']==entry['pid'] and str(current['start_ticks'])==str(entry['start_ticks'])
  if same_generation:
   log(dict(snapshot,status='hard_failure',reason='original decoder generation remains'))
   raise RuntimeError('original decoder generation remains after successful child return')
  reused=current is not None
  if entry['pid'] not in pids or reused:
   result={'schema':'h3-own-decoder-release-v1','gpu_uuid':uuid,'child_identity':entry,'original_generation_absent':True,'nvml_pid_absent':entry['pid'] not in pids,'pid_reused':reused,'current_reused_identity':current if reused else None,'other_compute_pids':[pid for pid in pids if pid!=entry['pid'] or reused],'wait_seconds':clock()-start,'attempts':attempts}
   log(dict(snapshot,status='released',pid_reused=reused))
   return result
  attempts.append(snapshot);log(dict(snapshot,status='waiting_own_NVML_tail'))
  if clock()-start>=timeout:raise TimeoutError('original decoder NVML tail did not settle within bounded wait')
  sleep(min(.25,timeout-(clock()-start)))
