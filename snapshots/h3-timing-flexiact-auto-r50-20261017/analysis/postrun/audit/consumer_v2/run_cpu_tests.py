"""Bounded synthetic postrun tests. No producer/consumer invocation or pose."""
import argparse,fcntl,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
LOCK=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('attempt',type=int);a=ap.parse_args()
 with LOCK.open('a+') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:print('BUSY');return 75
  signal.alarm(120);start=time.perf_counter();log=HERE/'audit'/f'cpu_attempt{a.attempt}.log'
  if log.exists():raise FileExistsError(log)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4',PYTHONDONTWRITEBYTECODE='1')
  p=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(HERE),'-p','test_*.py','-v'],capture_output=True,text=True,env=env,timeout=100)
  log.write_text(p.stdout+'\nSTDERR\n'+p.stderr)
  code={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in HERE.glob('*.py')}
  r={'exit':p.returncode,'seconds':time.perf_counter()-start,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'code':code,'scope':'pure synthetic metadata/import/inventory/identity tests','consumer_started':False,'pose_computed':False,'GPU_started':False}
  (HERE/'audit'/f'cpu_attempt{a.attempt}.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='code'}));return p.returncode
if __name__=='__main__':raise SystemExit(main())

