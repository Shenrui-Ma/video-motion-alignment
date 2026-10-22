import hashlib,json,os,subprocess,tempfile,time
from pathlib import Path
import process_identity
ROOT=Path(__file__).resolve().parents[1]
GPU='GPU-REDACTED'
PEER=Path('/data4/researcher/h3_runs/timing_ive_native_screen_r96_20261018')
PYTHON='/data3/researcher/ComfyUI/.venv/bin/python'
CHECKPOINT=Path('/data3/researcher/h3_runs/ivebench_official_metric_20261017/weights/baseline_offline.pth')
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix=p.name+'.',dir=p.parent)
 try:
  with os.fdopen(fd,'w') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
  os.replace(tmp,p)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def require(ok,message):
 if not ok:raise RuntimeError(message)
def identity(pid):
 row=process_identity.snapshot(pid)
 return None if row is None else {'pid':int(pid),**process_identity.hashed_record(row)}
def bind_service_owner(owner):
 row=process_identity.snapshot(owner['pid'])
 require(row is not None and process_identity.service_record(row)==owner['identity'],'R96 recorded UID/start/command differs')
 return {'pid':owner['pid'],**process_identity.hashed_record(row)}
def compute():
 s=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'],text=True,timeout=15);rows=[]
 for line in s.splitlines():
  if not line.strip():continue
  pid,gpu=map(str.strip,line.split(','));i=identity(int(pid));require(i is not None,'compute PID disappeared; retry fresh observation')
  rows.append({'gpu_uuid':gpu,**i})
 return rows
def cgroup():
 p=Path('/sys/fs/cgroup/user.slice')
 return {'current':int((p/'memory.current').read_text()),'high':int((p/'memory.high').read_text()),'max':int((p/'memory.max').read_text()),'events':dict((a,int(b)) for a,b in (x.split() for x in (p/'memory.events').read_text().splitlines())),'pressure':(p/'memory.pressure').read_text(),'unix':time.time()}
def resource_check(gpu):
 require(gpu==GPU and os.environ.get('CUDA_VISIBLE_DEVICES')==GPU,'GPU binding differs')
 rows=compute();own={r['gpu_uuid'] for r in rows if r['uid']==os.getuid()};require(len(own|{GPU})<=2,'would exceed two own GPU cards')
 raw=subprocess.check_output(['nvidia-smi','-i',GPU,'--query-gpu=uuid,name,memory.free,temperature.gpu','--format=csv,noheader,nounits'],text=True,timeout=15)
 uuid,name,free,temp=map(str.strip,raw.strip().split(','));require(uuid==GPU and float(free)>=24576 and 0<=float(temp)<85,'GPU capacity/health unavailable')
 cg=cgroup();require(cg['high']-cg['current']>=8*1024**3,'cgroup headroom below8GiB')
 return {'hostname':__import__('socket').gethostname(),'gpu_name':name,'gpu_uuid':GPU,'memory_free_mib':float(free),'temperature_c':float(temp),'processes':rows,'cgroup':cg,'unix':time.time()}
def verify_seal():
 for name,d in read(ROOT/'SEAL.json')['files'].items():require(sha(ROOT/name)==d['sha256'],'sealed file changed: '+name)
