import hashlib,json,os,tempfile,sys,math,subprocess,socket
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for c in iter(lambda:f.read(1048576),b''):h.update(c)
 return h.hexdigest()
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(dir=p.parent,prefix=p.name+'.')
 try:
  with os.fdopen(fd,'w')as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
  os.replace(tmp,p)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def bound(p):return dict(file=str(p),sha256=sha(p))
def case(name):
 assert name in read(ROOT/'configs/PLAN.json')['groups'];return ROOT/'cases'/name

def verify_seal():
 for rel,h in read(ROOT/'SEAL.json')['files'].items():assert sha(ROOT/rel)==h,'sealed file changed '+rel

def validate_case(c,role,check_pixels=True):
 m=read(c/'INPUTS.json');assert role=='source'or role in [x['role']for x in m['targets']]
 assert sha(c/'source_full.mp4')==m['source_full_sha256'];assert sha(c/'source_score.mp4')==m['source_score_sha256']
 if check_pixels:
  # These are pixel/time checks only; no torch or model import.
  import importlib.util
  p=ROOT/'runtime/ive/metric_runtime/ive_mf_adapter.py';s=importlib.util.spec_from_file_location('pixel_checks',p);a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
  info=a.media_info(c/'source_score.mp4','ffprobe');assert info['count']==m['evaluation_frames'];assert all(abs(t-i/m['evaluation_fps'])<1e-6 for i,t in enumerate(info['pts_s']));assert a.frame_hashes(c/'source_score.mp4','ffmpeg')==m['source_frame_md5']
 if role!='source':
  t=next(x for x in m['targets']if x['role']==role);assert sha(c/t['full_file'])==t['full_sha256'];assert sha(c/t['score_file'])==t['score_sha256']
  if check_pixels:
   info=a.media_info(c/t['score_file'],'ffprobe');assert info['count']==m['evaluation_frames'];assert all(abs(v-i/m['evaluation_fps'])<1e-6 for i,v in enumerate(info['pts_s']));assert a.frame_hashes(c/t['score_file'],'ffmpeg')==t['score_frame_md5']
 return m

def folder_for(c,role):
 m=read(c/'INPUTS.json')
 if role=='source'and m['source_cache']:return c/'tracks/source'
 p=ROOT/'state'/c.name/(role+'.json');v=read(p);folder=ROOT/v['folder'];assert sha(folder/'REPORT.json')==v['report_sha256'];return folder

def identity(pid):
 import process_identity
 row=process_identity.snapshot(pid);return None if row is None else dict(pid=int(pid),**process_identity.hashed_record(row))

def resource_check(gpu,allowed_pid=None):
 import capacity
 assert os.getuid()==1004 and socket.gethostname()=='H3_HOST'
 assert os.environ.get('CUDA_VISIBLE_DEVICES')==gpu
 mem=capacity.assess(capacity.snapshot(),'entry');assert mem['passed'],str(mem['failures'])
 rows=[]
 raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'],text=True,timeout=15)
 for line in raw.splitlines():
  if not line.strip():continue
  pid,dev=map(str.strip,line.split(','));p=Path('/proc')/pid
  try:uid=p.stat().st_uid
  except FileNotFoundError:continue
  assert uid!=1004 or int(pid)==allowed_pid,'unregistered own CUDA process'
  rows.append(dict(pid=int(pid),uid=uid,gpu_uuid=dev))
 raw=subprocess.check_output(['nvidia-smi','-i',gpu,'--query-gpu=uuid,name,memory.free,temperature.gpu','--format=csv,noheader,nounits'],text=True,timeout=15)
 uuid,name,free,temp=map(str.strip,raw.strip().split(','));assert uuid==gpu and float(free)>=40960 and float(temp)<85
 return dict(hostname=socket.gethostname(),gpu_name=name,gpu_uuid=gpu,memory_free_mib=float(free),processes=rows,capacity=mem)


def validate_flex_report(r,m,role,target=None):
 assert r['passed'] is True
 assert r['checkpoint_sha256']=='dbb9006c0dc89479c34993ac23d37ae0af13deac18be6028009d7483754b2fc3'
 assert r['metric_functions_sha256']==sha(ROOT/'runtime/flex/METRIC_FUNCTIONS.json')
 assert r['vendor_manifest_sha256']==sha(ROOT/'runtime/flex/VENDOR.json')
 assert r['grid_size']==55 and r['mask']is None and r['tracks_dtype']=='torch.float32'and r['tracks_shape']==[3025,49,2]
 assert [float(v['best_effort_timestamp_time'])for v in r['timebase']['frames']]==[i/8 for i in range(49)]
 assert r['case']['id']==m['canonical_id']
 if role=='source':assert r['case']['role']=='reference'and r['case']['sha256']==m['source_score_sha256']
 else:assert target is not None and r['case']['role']=='generated'and r['case']['sha256']==target['score_sha256']
