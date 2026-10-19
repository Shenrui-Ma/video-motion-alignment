"""One real-case CPU smoke, nonblocking shared locks, no service or CUDA."""
import fcntl,hashlib,json,os,shlex,subprocess,sys,time
from pathlib import Path
r=Path(__file__).resolve().parents[1];attempt=int(sys.argv[1]);remote='/data5/researcher/h3_runs/r44_cpu_stage_attempt'+str(attempt)
log=r/'audit'/f'real_comfy_cpu_attempt{attempt}.log';start=time.monotonic()
if log.exists():raise FileExistsError(log)
lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:log.write_text('Mac CPU lock busy; no stage or computation\n');raise SystemExit(75)
folders=('scripts','extensions','tests','configs','inputs','audit/preparation')
top=('PROTOCOL.json','README.txt','COMPARABILITY.txt','FREEZE.json')
files={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in folders for p in (r/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
files.update({p:hashlib.sha256((r/p).read_bytes()).hexdigest() for p in top})
(r/'audit'/f'cpu_stage_attempt{attempt}_manifest.json').write_text(json.dumps({'remote':remote,'files':files},indent=2)+'\n')
subprocess.run(['ssh','H3_SERVER_A','mkdir -p '+shlex.quote(remote+'/audit')],check=True)
for folder in folders:
 dest=remote+'/'+str(Path(folder).parent)+'/'
 subprocess.run(['rsync','-a','--exclude=__pycache__','--exclude=*.pyc',str(r/folder),'H3_SERVER_A:'+dest],check=True)
subprocess.run(['rsync','-a',*[str(r/x) for x in top],'H3_SERVER_A:'+remote+'/'],check=True)
code='''import fcntl,subprocess,sys,os
from pathlib import Path
def pending():
 for name in ('timing_auto_source51310_r40_20261017','timing_auto_fresh_r32_20261017','timing_auto_bedside_r35_20261017','timing_auto_source28289_r44_20261017'):
  root=Path('/data5/researcher/h3_runs')/name/'audit/observations'
  if any((p/'request.json').exists() and (p/'native.json').exists() and not (p/'pose_complete.json').exists() and not (p/'response.json').exists() for p in root.glob('step*')):return True
 return False
if pending():raise SystemExit(75)
lock=open('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock','a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit(75)
if pending():raise SystemExit(75)
r=sys.argv[1];env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONPATH='/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps',PYTHONDONTWRITEBYTECODE='1')
py='/home/researcher/miniconda3/envs/comfyui/bin/python'
result=subprocess.run([py,'-m','unittest','discover','-s',r+'/tests','-p','test_*.py','-v'],env=env,timeout=90)
if result.returncode:raise SystemExit(result.returncode)
if pending():raise SystemExit(75)
cmd=[py,r+'/tests/real_comfy_cpu_smoke.py','--comfy-root','/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI','--compat-bootstrap',r+'/scripts/compatibility_bootstrap.py','--case','off_probe_first']
raise SystemExit(subprocess.run(cmd,env=env,timeout=180).returncode)
'''
try:
 result=subprocess.run(['ssh','H3_SERVER_A','python3 -c '+shlex.quote(code)+' '+shlex.quote(remote)],capture_output=True,text=True,timeout=300)
 log.write_text(result.stdout+'\nSTDERR\n'+result.stderr);record={'exit':result.returncode,'seconds':time.monotonic()-start,'remote':remote,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()}
except subprocess.TimeoutExpired as exc:
 log.write_text('BOUNDED CPU STAGE TIMEOUT\n'+str(exc.stdout)+'\n'+str(exc.stderr));record={'exit':'timeout','seconds':time.monotonic()-start,'remote':remote}
(r/'audit'/f'real_comfy_cpu_attempt{attempt}.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record));raise SystemExit(record['exit'] if isinstance(record['exit'],int) else 1)
