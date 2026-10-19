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
  except RuntimeError as error:
   if str(error) not in ('GPU is not idle; refusing offline decode','GPU has a compute process; refusing offline decode'):raise
   attempts.append({'elapsed_seconds':clock()-start,'error':str(error),'compute_pids':pids})
   if clock()-start>=timeout:raise TimeoutError('strict GPU idle did not settle within10seconds') from error
   sleep(min(.25,timeout-(clock()-start)))
