"""Explicit root-authorized temporary CPU staging, no production/service/CUDA."""
import fcntl,hashlib,json,os,shlex,signal,subprocess,sys,time
from pathlib import Path
r=Path(__file__).resolve().parents[1];attempt=int(sys.argv[1])
remote='/data5/researcher/h3_runs/r47_cpu_stage_attempt'+str(attempt)
lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a+')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:print('BUSY MacCPU');raise SystemExit(75)
signal.alarm(120);started=time.monotonic()
dest=r/'audit'/f'remote_cpu_attempt{attempt}.json'
if dest.exists():raise FileExistsError(dest)
files={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('scripts','extensions','tests','configs','inputs','design') for p in (r/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
files['INPUTS_READY.json']=hashlib.sha256((r/'INPUTS_READY.json').read_bytes()).hexdigest()
(r/'audit'/f'cpu_stage_attempt{attempt}_manifest.json').write_text(json.dumps({'remote':remote,'files':files},indent=2)+'\n')
subprocess.run(['ssh','-o','ConnectTimeout=15','H3_SERVER_A','mkdir '+shlex.quote(remote)],check=True,timeout=20)
subprocess.run(['rsync','-a','--exclude=__pycache__','--exclude=*.pyc',*[str(r/folder) for folder in ('scripts','extensions','tests','configs','inputs','design')],'H3_SERVER_A:'+remote+'/'],check=True,timeout=30)
subprocess.run(['rsync','-a',str(r/'INPUTS_READY.json'),'H3_SERVER_A:'+remote+'/'],check=True,timeout=15)
remote_code="""
import fcntl,subprocess,sys,os,signal
from pathlib import Path
def pending():
 root=Path('/data5/researcher/h3_runs/timing_auto_source28289_r45_20261017/audit/observations')
 return any((d/'request.json').exists() and (d/'native.json').exists() and not (d/'pose_complete.json').exists() and not (d/'response.json').exists() for d in root.glob('step*'))
if pending():print('R47_CPU_BUSY R45online_pose_pending',flush=True);raise SystemExit(75)
lock=open('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock','a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:print('R47_CPU_BUSY remote_cpu_lock',flush=True);raise SystemExit(75)
if pending():print('R47_CPU_BUSY R45online_pose_pending_after_lock',flush=True);raise SystemExit(75)
signal.alarm(90);r=sys.argv[1];python='/home/researcher/miniconda3/envs/comfyui/bin/python'
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONPATH='/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps',PYTHONDONTWRITEBYTECODE='1')
unit=[python,'-m','unittest','discover','-s',r+'/tests','-p','test_*.py','-v']
rc=subprocess.run(unit,env=env,timeout=30).returncode
if rc:raise SystemExit(rc)
cmd=[python,r+'/tests/real_comfy_cached_queue_smoke.py','--core','/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI']
raise SystemExit(subprocess.run(cmd,env=env,timeout=55).returncode)
"""
cmd='python3 -c '+shlex.quote(remote_code)+' '+shlex.quote(remote)
v=subprocess.run(['ssh','-o','ConnectTimeout=15','H3_SERVER_A',cmd],capture_output=True,text=True,timeout=95)
log=r/'audit'/f'remote_cpu_attempt{attempt}.log';log.write_text(v.stdout+'\nSTDERR\n'+v.stderr)
rec={'exit':v.returncode,'seconds':time.monotonic()-started,'remote':remote,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'input_manifest_sha256':hashlib.sha256((r/'audit'/f'cpu_stage_attempt{attempt}_manifest.json').read_bytes()).hexdigest(),'production_deployed':False,'CUDA_visible_devices':'','scope':'Linux unit tests and actual Comfy tiny fixture, no model weights or service'}
dest.write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps(rec));raise SystemExit(v.returncode)

