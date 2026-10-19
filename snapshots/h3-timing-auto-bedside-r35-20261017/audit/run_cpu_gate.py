import fcntl,hashlib,json,os,shlex,subprocess,sys,time
from pathlib import Path
r=Path(__file__).resolve().parents[1];attempt=int(sys.argv[1]);remote='/data5/researcher/h3_runs/r35_cpu_stage_attempt'+str(attempt);t0=time.monotonic();log=r/'audit'/f'real_comfy_cpu_attempt{attempt}.log'
lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:log.write_text('Mac CPU lock busy; no staging or execution\n');raise SystemExit(75)
files={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('scripts','extensions','tests','configs') for p in (r/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
(r/'audit'/f'cpu_stage_attempt{attempt}_manifest.json').write_text(json.dumps({'remote':remote,'files':files},indent=2)+'\n')
subprocess.run(['ssh','H3_SERVER_A','mkdir '+shlex.quote(remote)],check=True)
subprocess.run(['rsync','-a','--exclude=__pycache__','--exclude=*.pyc',*[str(r/folder) for folder in ('scripts','extensions','tests','configs')],*[str(r/f) for f in ('PROTOCOL.json','README.txt','COMPARABILITY.txt','FREEZE.json')],'H3_SERVER_A:'+remote+'/'],check=True)
subprocess.run(['ssh','H3_SERVER_A','mkdir -p '+shlex.quote(remote+'/analysis')],check=True)
subprocess.run(['rsync','-a','--exclude=__pycache__','--exclude=*.pyc',str(r/'analysis/postrun'),'H3_SERVER_A:'+remote+'/analysis/'],check=True)
code='''import fcntl,subprocess,sys,os
from pathlib import Path
def pending():
 r=Path('/data5/researcher/h3_runs/timing_auto_fresh_r32_20261017/audit/observations')
 return any((d/'request.json').exists() and (d/'native.json').exists() and not (d/'pose_complete.json').exists() and not (d/'response.json').exists() for d in r.glob('step*'))
if pending():raise SystemExit(75)
lock=open('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock','a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit(75)
if pending():raise SystemExit(75)
r=sys.argv[1];env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONPATH='/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps',PYTHONDONTWRITEBYTECODE='1')
unit=['/home/researcher/miniconda3/envs/comfyui/bin/python','-m','unittest','discover','-s',r+'/tests','-p','test_*.py','-v']
u=subprocess.run(unit,env=env,timeout=120)
if u.returncode:raise SystemExit(u.returncode)
if pending():raise SystemExit(75)
unit[5]=r+'/analysis/postrun'
u=subprocess.run(unit,env=env,timeout=60)
if u.returncode:raise SystemExit(u.returncode)
if pending():raise SystemExit(75)
cmd=['/home/researcher/miniconda3/envs/comfyui/bin/python',r+'/tests/real_comfy_cpu_smoke.py','--comfy-root','/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI','--compat-bootstrap',r+'/scripts/compatibility_bootstrap.py','--case','off_probe_first']
result=subprocess.run(cmd,env=env,timeout=120)
if result.returncode:raise SystemExit(result.returncode)
if pending():raise SystemExit(75)
cmd[-1]='restart_probe_first'
raise SystemExit(subprocess.run(cmd,env=env,timeout=120).returncode)
'''
p=subprocess.run(['ssh','H3_SERVER_A','python3 -c '+shlex.quote(code)+' '+shlex.quote(remote)],capture_output=True,text=True,timeout=270);log.write_text(p.stdout+'\nSTDERR\n'+p.stderr);result={'exit':p.returncode,'seconds':time.monotonic()-t0,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'remote':remote};(r/'audit'/f'real_comfy_cpu_attempt{attempt}.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(p.returncode)
