"""Bounded task-owned GPU check; exact child registration and release."""
from pathlib import Path
import os,sys,subprocess,time,signal,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import service,process_identity,cgroup_memory
from r111_contract import require,read,sha

def main():
 require(str(ROOT)==service.RUNTIME['remote_root'] and os.getuid()==1004,'wrong host/root owner')
 result=ROOT/'audit/GPU_SMOKE_RESULT.json';receipt=ROOT/'audit/GPU_SMOKE_RELEASE.json';registration=ROOT/'audit/GPU_SMOKE_OWNER.json'
 require(not result.exists() and not receipt.exists() and not registration.exists(),'smoke evidence already exists')
 rows=service.compute_processes()
 for row in rows:
  uid=service.proc_uid(row['pid']);require(uid is not None and uid!=os.getuid(),'existing own or unidentified CUDA task')
 gpu=subprocess.check_output(['nvidia-smi','--id='+service.GPU,'--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'],text=True).strip().split(',')
 require(gpu[0].strip()==service.GPU and float(gpu[1])>=40960,'selected GPU lacks40GiB')
 memory=cgroup_memory.check(ROOT);service.write_json(ROOT/'audit/GPU_SMOKE_CAPACITY.json',memory)
 env=dict(os.environ,CUDA_VISIBLE_DEVICES=service.GPU,PYTHONPATH=service.DEPENDENCIES,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1')
 command=[service.PYTHON,'-u',str(ROOT/'scripts/gpu_spatial_marginal_smoke.py'),'--actual-shape','--output',str(result)]
 with (ROOT/'logs/gpu_smoke.log').open('xb') as log:
  proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=log)
  owner=process_identity.hashed_record(process_identity.bind_or_reap(proc,command),include_pid=True)
  service.write_json(registration,{'owner':owner,'command':command,'gpu_uuid':service.GPU,'created_unix':time.time()})
  try:code=proc.wait(timeout=900)
  except BaseException:
   actual=process_identity.hashed_record(process_identity.snapshot(proc.pid),include_pid=True)
   if actual==owner and proc.poll() is None:
    proc.terminate()
    try:proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
     require(process_identity.hashed_record(process_identity.snapshot(proc.pid),include_pid=True)==owner,'smoke generation changed');proc.kill();proc.wait(timeout=10)
   raise
  deadline=time.monotonic()+20
  while any(x['pid']==proc.pid for x in service.compute_processes()) and time.monotonic()<deadline:time.sleep(.3)
  absent=not Path('/proc',str(proc.pid)).exists();released=not any(x['pid']==proc.pid for x in service.compute_processes())
  service.write_json(receipt,{'passed':code==0 and absent and released,'owner':owner,'gpu_uuid':service.GPU,'exit_code':code,'process_absent':absent,'CUDA_allocation_absent':released,'result_sha256':sha(result) if result.exists() else None,'unix':time.time()})
  require(code==0 and absent and released,'GPU smoke failed or cleanup incomplete')
 from spatial_smoke_gate import verify
 print(json.dumps(verify(ROOT)))
if __name__=='__main__':main()
