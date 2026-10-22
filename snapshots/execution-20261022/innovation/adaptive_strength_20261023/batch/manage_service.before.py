"""Own-service lifecycle, shared GPU admission, reconnectable remote execution."""
import argparse,fcntl,json,os,signal,socket,subprocess,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CORE='/data3/research-user/h3_runs/silverwolf_486_ref2va4_clean/ComfyUI'
PYTHON='/data3/research-user/ComfyUI/.venv/bin/python'
DEPS='/data3/research-user/h3_runs/closure_tutorials_53592/01-anime/runtime_deps'
MODELS='/data3/research-user/ComfyUI-H3/models'
PORT=8672
GPU='GPU-REPLACE_WITH_TARGET_UUID'
def read_record():
 p=ROOT/'service.json';return json.loads(p.read_text()) if p.exists() else None
def alive(r):
 if not r:return False
 try:
  st=Path('/proc')/str(r['pid']);return st.stat().st_uid==os.getuid() and (st/'stat').read_text().split()[21]==r['start_ticks'] and str(ROOT).encode() in (st/'cmdline').read_bytes()
 except FileNotFoundError:return False
def api(path):return json.load(urllib.request.build_opener(urllib.request.ProxyHandler({})).open(f'http://127.0.0.1:{PORT}/'+path,timeout=10))
def wait_ready(record, seconds):
 deadline=time.monotonic()+seconds
 while time.monotonic()<deadline:
  if not alive(record):return False
  try:api('system_stats');return True
  except Exception:
   remaining=deadline-time.monotonic()
   if remaining>0:time.sleep(min(2,remaining))
 return False
def stop(record=None):
 # Retain the inspected identity even if service.json changes during recovery.
 r=read_record() if record is None else record
 if alive(r):
  try:os.kill(r['pid'],signal.SIGTERM)
  except ProcessLookupError:pass
  deadline=time.monotonic()+30
  while alive(r) and time.monotonic()<deadline:time.sleep(.5)
  if alive(r):
   try:os.kill(r['pid'],signal.SIGKILL)
   except ProcessLookupError:pass
   deadline=time.monotonic()+5
   while alive(r) and time.monotonic()<deadline:time.sleep(.2)
 return {'stopped':not alive(r),'previous':r}
def start():
 r=read_record()
 if alive(r):
  if wait_ready(r,90):return {'state':'already_running',**r}
  result=stop(r)
  if not result['stopped']:raise RuntimeError('Unresponsive own service could not be stopped')
 # Advisory host lock held by the real model process, released on crash/reboot.
 lock=open('/tmp/h3-video-inference-research-user.lock','a')
 deadline=time.monotonic()+10
 while True:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
  except BlockingIOError:
   if time.monotonic()>=deadline:raise
   time.sleep(.25)
 for p in [CORE+'/main.py',PYTHON,DEPS,MODELS]:
  if not Path(p).exists():raise RuntimeError('Missing runtime '+p)
 rows=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True,timeout=20)
 if any(line.split(',')[0].strip()==GPU for line in rows.splitlines()):raise RuntimeError('Selected GPU has an existing compute process')
 # The user's longstanding interactive Comfy remains untouched; defer if active.
 try:q=json.load(urllib.request.urlopen('http://127.0.0.1:8189/queue',timeout=3))
 except Exception:q={}
 for job in q.get('queue_running',[])+q.get('queue_pending',[]):
  types=[n.get('class_type','') for n in job[2].values()]
  image_only='EmptyLatentImage' in types and 'SaveImage' in types and not any(any(w in t.lower() for w in ['video','h3','wan','hunyuan','ltx','mochi']) for t in types)
  if not image_only:raise RuntimeError('Existing interactive work may include video inference')
 with socket.socket() as s:
  s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
  s.bind(('127.0.0.1',PORT))
 env=dict(os.environ,CUDA_VISIBLE_DEVICES=GPU,PYTHONPATH=DEPS+os.pathsep+str(ROOT/'scripts'),OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',TOKENIZERS_PARALLELISM='false',PYTHONDONTWRITEBYTECODE='1',LC_ALL='C',LANG='C',NO_PROXY='*',no_proxy='*')
 for k in ['http_proxy','https_proxy','all_proxy','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY']:env.pop(k,None)
 args=[PYTHON,'-u',str(ROOT/'scripts/compatibility_bootstrap.py'),CORE+'/main.py','--listen','127.0.0.1','--port',str(PORT),'--base-directory',str(ROOT),'--models-directory',MODELS,'--disable-auto-launch','--disable-dynamic-vram','--disable-cuda-malloc','--use-pytorch-cross-attention','--reserve-vram','8','--enable-triton-backend','--preview-method','none','--disable-all-custom-nodes','--whitelist-custom-nodes','ComfyUI-KJNodes','H3Study','H3DirectionRuntime','H3TemporalCoverage','H3TemporalCoverageV2','H3PartialRoPE','H3TrustedConditionCache','--input-directory',str(ROOT/'input'),'--output-directory',str(ROOT/'output'),'--temp-directory',str(ROOT/'temp'),'--user-directory',str(ROOT/'user'),'--database-url','sqlite:///'+str(ROOT/'study.db')]
 for n in ['logs','input','output','temp','user']:(ROOT/n).mkdir(exist_ok=True)
 link=ROOT/'custom_nodes/ComfyUI-KJNodes'
 if not link.exists():link.symlink_to('/data3/research-user/h3_runs/closure_tutorials_53592/01-anime/custom_nodes/ComfyUI-KJNodes')
 with (ROOT/'logs/comfy.log').open('ab',buffering=0) as log:p=subprocess.Popen(args,cwd=CORE,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,pass_fds=(lock.fileno(),))
 rec={'pid':p.pid,'start_ticks':(Path('/proc')/str(p.pid)/'stat').read_text().split()[21],'gpu_uuid':GPU,'port':PORT,'started_unix':time.time(),'command':args}
 temporary=ROOT/('service.json.'+str(os.getpid())+'.tmp')
 temporary.write_text(json.dumps(rec,indent=2));os.replace(temporary,ROOT/'service.json');lock.close()
 if wait_ready(rec,420):return {'state':'ready',**rec}
 # Do not leave a failed cold start holding the host/GPU admission lock.
 stopped=stop(rec)
 raise RuntimeError('Service readiness timeout or early exit; cleanup='+str(stopped['stopped']))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('action',choices=['start','stop','restart','status']);o=a.parse_args()
 if o.action=='stop':print(json.dumps(stop()))
 elif o.action=='status':print(json.dumps({'alive':alive(read_record()),'record':read_record()}))
 else:
  if o.action=='restart':stop()
  print(json.dumps(start()))
