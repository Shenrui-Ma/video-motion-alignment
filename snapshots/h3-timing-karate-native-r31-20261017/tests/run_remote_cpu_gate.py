"""CPU-only isolated staging; nonblocking Mac then shared remote lock, no service."""
import fcntl,hashlib,json,os,shlex,subprocess,sys,time
from pathlib import Path
r=Path(__file__).resolve().parents[1];attempt=int(sys.argv[1]);mode=sys.argv[2] if len(sys.argv)>2 else 'comfy';remote='/data5/researcher/h3_runs/r31_cpu_stage_attempt'+str(attempt)
lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
files={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('scripts','extensions','tests','configs','inputs') for p in (r/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
(r/'audit'/f'cpu_stage_attempt{attempt}_manifest.json').write_text(json.dumps({'remote':remote,'files':files},indent=2)+'\n')
subprocess.run(['ssh','H3_SERVER_A','mkdir '+shlex.quote(remote)],check=True)
subprocess.run(['rsync','-a','--exclude=__pycache__','--exclude=*.pyc',*[str(r/folder) for folder in ('scripts','extensions','tests','configs','inputs')],'H3_SERVER_A:'+remote+'/'],check=True)
remote_code="""import fcntl,subprocess,sys,os
lock=open('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock','a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit(75)
r=sys.argv[1];mode=sys.argv[2]
cmd=['/home/researcher/miniconda3/envs/comfyui/bin/python',r+'/tests/real_comfy_cached_queue_smoke.py','--core','/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI']
if mode=='unit':cmd=['/home/researcher/miniconda3/envs/comfyui/bin/python','-m','unittest','discover','-s',r+'/tests','-p','test_*.py','-v']
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONPATH='/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps',PYTHONDONTWRITEBYTECODE='1')
if mode=='all':
 unit=['/home/researcher/miniconda3/envs/comfyui/bin/python','-m','unittest','discover','-s',r+'/tests','-p','test_*.py','-v']
 rc=subprocess.run(unit,env=env,timeout=60).returncode
 if rc:raise SystemExit(rc)
raise SystemExit(subprocess.run(cmd,env=env,timeout=120).returncode)
"""
cmd='python3 -c '+shlex.quote(remote_code)+' '+shlex.quote(remote)+' '+shlex.quote(mode);t=time.monotonic();v=subprocess.run(['ssh','H3_SERVER_A',cmd],capture_output=True,text=True,timeout=150)
log=r/'audit'/f'real_comfy_cpu_attempt{attempt}.log';log.write_text(v.stdout+'\nSTDERR\n'+v.stderr)
(r/'audit'/f'real_comfy_cpu_attempt{attempt}.json').write_text(json.dumps({'exit':v.returncode,'seconds':time.monotonic()-t,'remote':remote,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()},indent=2)+'\n');print(v.stdout);print(v.stderr,file=sys.stderr);raise SystemExit(v.returncode)
