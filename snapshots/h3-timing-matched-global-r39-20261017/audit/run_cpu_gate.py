import fcntl,hashlib,json,os,shlex,subprocess,sys,time
from pathlib import Path
r=Path(__file__).resolve().parents[1];attempt=int(sys.argv[1]);remote='/data5/researcher/h3_runs/r39_cpu_stage_attempt'+str(attempt);t0=time.monotonic();log=r/'audit'/f'real_comfy_cpu_attempt{attempt}.log'
lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a')
mac_wait_seconds=float(sys.argv[2]) if len(sys.argv)>2 else 0
if not 0<=mac_wait_seconds<=120:raise ValueError('Mac lock wait must be bounded by120seconds')
mac_deadline=time.monotonic()+mac_wait_seconds
while True:
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
 except BlockingIOError:
  if time.monotonic()>=mac_deadline:log.write_text('Mac CPU lock busy; no staging or execution\n');raise SystemExit(75)
  time.sleep(min(.2,max(0,mac_deadline-time.monotonic())))
files={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('scripts','extensions','tests','configs') for p in (r/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
files.update({name:hashlib.sha256((r/name).read_bytes()).hexdigest() for name in ('SCIENCE_PROTOCOL.json','PROTOCOL.json','README.txt','COMPARABILITY.txt','FREEZE.json')})
(r/'audit'/f'cpu_stage_attempt{attempt}_manifest.json').write_text(json.dumps({'remote':remote,'files':files},indent=2)+'\n')
subprocess.run(['ssh','H3_SERVER_A','mkdir '+shlex.quote(remote)],check=True)
subprocess.run(['rsync','-a','--exclude=__pycache__','--exclude=*.pyc',*[str(r/folder) for folder in ('scripts','extensions','tests','configs')],'H3_SERVER_A:'+remote+'/'],check=True)
subprocess.run(['rsync','-a',*[str(r/name) for name in ('SCIENCE_PROTOCOL.json','PROTOCOL.json','README.txt','COMPARABILITY.txt','FREEZE.json')],'H3_SERVER_A:'+remote+'/'],check=True)
code='''import fcntl,subprocess,sys,os
from pathlib import Path
def pending():
 roots=['timing_auto_controller_r27_20261017','timing_auto_fresh_r32_20261017','timing_auto_bedside_r35_20261017']
 return any((d/'request.json').exists() and (d/'native.json').exists() and not (d/'pose_complete.json').exists() and not (d/'response.json').exists() for name in roots for d in (Path('/data5/researcher/h3_runs')/name/'audit/observations').glob('step*'))
if pending():print('R39_CPU_GATE_BUSY online_pose_pending',flush=True);raise SystemExit(75)
lock=open('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock','a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:print('R39_CPU_GATE_BUSY remote_cpu_lock',flush=True);raise SystemExit(75)
if pending():print('R39_CPU_GATE_BUSY online_pose_pending_after_lock',flush=True);raise SystemExit(75)
r=sys.argv[1];env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONPATH='/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps',PYTHONDONTWRITEBYTECODE='1')
cmd=['/home/researcher/miniconda3/envs/comfyui/bin/python',r+'/tests/real_comfy_cpu_smoke.py','--comfy-root','/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI','--compat-bootstrap',r+'/scripts/compatibility_bootstrap.py','--case','global_probe_first']
raise SystemExit(subprocess.run(cmd,env=env,timeout=240).returncode)
'''
p=subprocess.run(['ssh','H3_SERVER_A','python3 -c '+shlex.quote(code)+' '+shlex.quote(remote)],capture_output=True,text=True,timeout=270);log.write_text(p.stdout+'\nSTDERR\n'+p.stderr);result={'exit':p.returncode,'seconds':time.monotonic()-t0,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'remote':remote};(r/'audit'/f'real_comfy_cpu_attempt{attempt}.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(p.returncode)
