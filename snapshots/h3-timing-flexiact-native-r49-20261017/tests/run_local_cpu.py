"""One nonblocking shared-lock CPU phase; no network or CUDA service."""
import argparse,fcntl,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LOCK=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
def main():
 p=argparse.ArgumentParser();p.add_argument('attempt',type=int);a=p.parse_args()
 with LOCK.open('a+') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:print('BUSY');return 75
  signal.alarm(120);t=time.perf_counter();out=ROOT/'audit'/f'local_cpu_attempt{a.attempt}.log'
  if out.exists():raise FileExistsError(out)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',PYTHONDONTWRITEBYTECODE='1')
  cmd=[sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-p','test_*.py','-v']
  r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=110)
  out.write_text(r.stdout+'\nSTDERR\n'+r.stderr)
  code={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for folder in ['scripts','extensions','tests'] for f in (ROOT/folder).rglob('*.py')}
  rec={'exit':r.returncode,'seconds':time.perf_counter()-t,'log':str(out),'log_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'code':code,'scope':'local synthetic metadata/lifecycle/archive tests, no actual Comfy core/model/GPU'}
  (ROOT/'audit'/f'local_cpu_attempt{a.attempt}.json').write_text(json.dumps(rec,indent=2)+'\n')
  print(json.dumps({k:v for k,v in rec.items() if k!='code'}));return r.returncode
if __name__=='__main__':raise SystemExit(main())

