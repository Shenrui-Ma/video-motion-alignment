import hashlib,json,os,subprocess,tempfile,time,socket
from pathlib import Path
import process_identity
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def require(ok,message):
 if not ok:raise ValueError(message)
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix=p.name+'.',dir=p.parent)
 try:
  with os.fdopen(fd,'w') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
  os.replace(tmp,p)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def bound(p):return {'file':str(p),'sha256':sha(p)}
def case_root(name):
 require(name and name.replace('_','').isalnum(),'unsafe case name');c=ROOT/'cases'/name;require(c.is_dir(),'unknown case');return c

def gate_video(gate,keys):
 out=gate
 for k in keys:out=out[k]
 return out

def validate_gate(spec,gate):
 require(gate.get('schema')==spec['gate']['schema'] and gate.get('passed') is True,'actual gate schema/status differs')
 require(gate.get('checks') and all(x is True for x in gate['checks'].values()),'actual gate checks not all true')
 require(gate.get('source_id',gate.get('pair'))==spec['source_id'],'actual gate source differs')
 require(gate.get('valid_frames')==spec['valid_frames'],'actual gate valid frame count differs')
 require(gate.get('evaluation_crop_xywh',gate.get('crop_xywh'))==spec['crop_xywh'],'actual gate crop differs')
 for role,r in spec['targets'].items():
  v=gate_video(gate,r['gate_video_keys']);require(v['sha256']==r['full_sha256'],'actual target SHA differs')
  props=v['properties'];require((props['width'],props['height'],props['avg_frame_rate'],int(props['nb_read_frames']))==(1312,736,'24/1',spec['total_frames']),'actual video geometry differs')
  if len(spec['targets'])==1:require(gate['run_id']==r['run_id'],'actual run differs')

def validate_reuse(spec,manifest,report,report_sha,tracks_sha):
 u=spec['source_cache_reuse'];s=manifest['roles']['source'];count=spec['valid_frames']
 require(report_sha==u['source_report_sha256'] and tracks_sha==u['source_tracks_sha256'],'source cache bytes differ')
 expected={'passed':True,'method':'source','pair_id':spec['source_id'],'selection_sha256':u['selection_sha256'],'source_prepared_sha256':s['full_sha256'],'source_score_sha256':s['score_sha256'],'effective_frame_count':count,'score_frame_indices':list(range(count)),'tracker':{'grid_size':10,'grid_query_frame':0,'backward_tracking':False,'offline':True,'window_len':60},'checkpoint_sha256':'da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df','official_commit':'2dcf8900ee65197f43854c76f61c66a32bb8dbfc','torch_version':u['torch_version'],'cuda_version':u['cuda_version'],'tracks_sha256':tracks_sha}
 for k,v in expected.items():require(report.get(k)==v,'source reuse contract differs: '+k)
 for k,ek in [('hostname','host'),('gpu_name','gpu_name')]:require(report['admission_before_cuda'][k]==u[ek],'source runtime differs: '+k)
 require(report['decoded_frame_md5']==s['score_frame_md5'],'source cache decoded pixels differ')
 require(u['source_score_sha256']==s['score_sha256'],'source score artifact differs')

def identity(pid):
 r=process_identity.snapshot(pid);return None if r is None else {'pid':int(pid),**process_identity.hashed_record(r)}
def resource_check(gpu):
 cfg=read(ROOT/'configs/RUNTIME.json');require(gpu.startswith('GPU-') and os.environ.get('CUDA_VISIBLE_DEVICES')==gpu,'exact GPU binding required')
 require(socket.gethostname()==cfg['host'] and os.getuid()==cfg['uid'],'actual host/UID differs')
 text=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'],text=True,timeout=15);rows=[]
 for line in text.splitlines():
  if not line.strip():continue
  pid,device=map(str.strip,line.split(','));i=identity(int(pid));require(i is not None,'process disappeared during capacity query; retry fresh query');rows.append({'gpu_uuid':device,**i})
 require(len({r['gpu_uuid'] for r in rows if r['uid']==os.getuid()}|{gpu})<=cfg['maximum_own_gpu_cards'],'own GPU cap exceeded')
 raw=subprocess.check_output(['nvidia-smi','-i',gpu,'--query-gpu=uuid,name,memory.free,temperature.gpu','--format=csv,noheader,nounits'],text=True,timeout=15)
 uuid,name,free,temp=map(str.strip,raw.strip().split(','));require(uuid==gpu and float(free)>=cfg['minimum_gpu_free_mib'] and 0<=float(temp)<85,'fresh GPU capacity unavailable')
 cg=Path('/sys/fs/cgroup/user.slice');c={'current':int((cg/'memory.current').read_text()),'high':int((cg/'memory.high').read_text()),'events':(cg/'memory.events').read_text(),'pressure':(cg/'memory.pressure').read_text()};require(c['high']-c['current']>=cfg['minimum_cgroup_headroom_bytes'],'fresh cgroup headroom unavailable')
 return {'hostname':socket.gethostname(),'gpu_name':name,'gpu_uuid':gpu,'memory_free_mib':float(free),'temperature_c':float(temp),'processes':rows,'cgroup':c,'unix':time.time()}
def verify_runtime():
 for n,h in read(ROOT/'configs/RUNTIME_INHERITANCE.json')['files'].items():require(sha(ROOT/'runtime'/n)==h,'inherited numeric runtime changed: '+n)
def verify_seal():
 for n,h in read(ROOT/'SEAL.json')['files'].items():require(sha(ROOT/n)==h,'sealed file changed: '+n)
