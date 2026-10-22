"""CPU-only isolated staging; uses shared evaluation locks and never starts Comfy."""
import fcntl,hashlib,json,os,shlex,subprocess,sys,time
from pathlib import Path
r=Path(__file__).resolve().parents[1];attempt=int(sys.argv[1]);remote='/data5/researcher/h3_runs/r25_cpu_stage_attempt'+str(attempt)
lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
files={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('scripts','extensions','tests','configs','inputs','parent_evidence') for p in (r/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
(r/'audit'/f'cpu_stage_attempt{attempt}_manifest.json').write_text(json.dumps({'remote':remote,'files':files},indent=2)+'\n')
subprocess.run(['ssh','H3_SERVER_A','mkdir '+shlex.quote(remote)],check=True)
subprocess.run(['rsync','-a','--exclude=__pycache__','--exclude=*.pyc',*[str(r/folder) for folder in ('scripts','extensions','tests','configs','inputs','parent_evidence')],'H3_SERVER_A:'+remote+'/'],check=True)
remote_code="""import fcntl,subprocess,sys,os
lock=open('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
r=sys.argv[1]
cmd=['/home/researcher/miniconda3/envs/comfyui/bin/python',r+'/tests/reverse_wrapper_smoke.py','--comfy-root','/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI','--compat-bootstrap',r+'/scripts/compatibility_bootstrap.py']
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONPATH='/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps',PYTHONDONTWRITEBYTECODE='1')
first=subprocess.run(cmd,env=env).returncode
if first:raise SystemExit(first)
cmd[1]=r+'/tests/auxiliary_cpu_smoke.py'
raise SystemExit(subprocess.run(cmd,env=env).returncode)
"""
cmd='python3 -c '+shlex.quote(remote_code)+' '+shlex.quote(remote)
t=time.monotonic();v=subprocess.run(['ssh','H3_SERVER_A',cmd],capture_output=True,text=True)
log=r/'audit'/f'real_comfy_cpu_attempt{attempt}.log';log.write_text(v.stdout+'\nSTDERR\n'+v.stderr)
(r/'audit'/f'real_comfy_cpu_attempt{attempt}.json').write_text(json.dumps({'exit':v.returncode,'seconds':time.monotonic()-t,'remote':remote,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()},indent=2)+'\n')
print(v.stdout);print(v.stderr,file=sys.stderr);raise SystemExit(v.returncode)
