import fcntl,os,subprocess,sys,time,json
from pathlib import Path
from contract import read,HERE,sha,require
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
def pending():
 for root in read(HERE/'PROTOCOL.json')['online_priority_roots']:
  for d in (Path(root)/'audit/observations').glob('step*'):
   if (d/'request.json').exists() and (d/'native.json').exists() and not (d/'pose_complete.json').exists() and not (d/'response.json').exists():return True
 return False
for name,want in read(HERE/'STAGE_MANIFEST.json').items():require(sha(HERE/name)==want,'staged code/asset changed '+name)
if pending():print('ONLINE_BUSY');raise SystemExit(75)
with Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a') as lock:
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:print('CPU_BUSY');raise SystemExit(75)
 if pending():print('ONLINE_BUSY');raise SystemExit(75)
 start=time.monotonic();r=subprocess.run([sys.executable,str(HERE/'presentation_smoke.py')],timeout=60);print(json.dumps({'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-start,'no_models':True,'CUDA_VISIBLE_DEVICES':os.environ['CUDA_VISIBLE_DEVICES']}));raise SystemExit(r.returncode)
