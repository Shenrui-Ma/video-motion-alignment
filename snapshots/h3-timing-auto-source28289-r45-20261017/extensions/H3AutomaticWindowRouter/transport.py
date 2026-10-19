"""Immutable request transport and exact owned-process supervision (stdlib only)."""
import hashlib,json,os,signal,subprocess,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PROTOCOL_SHA='71e610e7dd90294e195c84890fdcd18beefe1fefabf68f63fa9a107c29291f93'
DECODER_UUID='GPU-REDACTED'
MAIN_UUID='GPU-REDACTED'
SECOND_TASK_UUID='GPU-REDACTED'
REMOTE_ROOT=Path('/data5/researcher/h3_runs/timing_auto_source28289_r45_20261017')
def require(ok,message):
 if not ok:raise ValueError(message)
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def read_json(path):
 return json.loads(Path(path).read_text(),parse_constant=lambda s:(_ for _ in ()).throw(ValueError('nonfinite JSON '+s)))
def write_new(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 data=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
 with path.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 return sha(path)
def inside(path,root):
 p=Path(path);r=Path(root).resolve()
 require(p.is_absolute() and not p.is_symlink() and p.resolve().is_relative_to(r),'path outside owned root or symlink')
 return p.resolve()
def identity(pid):
 p=Path('/proc')/str(pid)
 try:
  stat=(p/'stat').read_text(); tail=stat[stat.rindex(')')+2:].split()
  if tail[0]=='Z':return None
  return {'pid':pid,'uid':p.stat().st_uid,'start_ticks':int(tail[19]),'cmdline_sha256':hashlib.sha256((p/'cmdline').read_bytes()).hexdigest()}
 except (FileNotFoundError,ProcessLookupError):return None
def alive(entry):return entry is not None and identity(entry['pid'])==entry
def terminate_owned(process,entry,grace=8):
 if process.poll() is not None:return
 if alive(entry):
  require(entry['uid']==os.getuid() and os.getpgid(entry['pid'])==entry['pid'],'not an owned isolated process group')
  os.killpg(entry['pid'],signal.SIGTERM)
 try:process.wait(timeout=grace)
 except subprocess.TimeoutExpired:
  if alive(entry):os.killpg(entry['pid'],signal.SIGKILL)
  process.wait(timeout=10)
def install_lifetime_guard(parent):
 """No fork/preexec in CUDA parent. Each fresh exec watches its exact parent."""
 require(parent['uid']==os.getuid() and alive(parent),'parent identity is not live')
 own=os.getpid();require(os.getpgid(own)==own,'child must own its isolated process group')
 def abort(signum,frame):raise SystemExit(128+signum)
 signal.signal(signal.SIGTERM,abort);signal.signal(signal.SIGINT,abort)
 def watch():
  while alive(parent):time.sleep(.25)
  # Our process group contains only descendants created by this fresh exec.
  os.killpg(own,signal.SIGTERM)
  time.sleep(8)
  os.killpg(own,signal.SIGKILL)
 threading.Thread(target=watch,name='exact-parent-lifetime',daemon=True).start()
def run_child(command,env,directory,label,timeout,parent):
 directory=Path(directory);log=directory/(label+'.log');start=time.monotonic();proc=None;entry=None
 try:
  require(alive(parent),'parent exited before child launch')
  with log.open('xb') as handle:
   proc=subprocess.Popen(command,env=env,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
   deadline=time.monotonic()+3
   while entry is None and proc.poll() is None and time.monotonic()<deadline:
    entry=identity(proc.pid)
   require(entry is not None and entry['uid']==os.getuid(),'unable to bind own child')
   write_new(directory/(label+'.process.json'),dict(entry,command=command,parent=parent,timeout_seconds=timeout))
   while proc.poll() is None:
    require(alive(parent),'parent exited during child execution')
    if time.monotonic()-start>timeout:raise TimeoutError(label+' timeout')
    time.sleep(.2)
   if proc.returncode:raise RuntimeError(label+' exit '+str(proc.returncode)+'; see '+str(log))
 finally:
  if proc is not None:
   terminate_owned(proc,entry)
   write_new(directory/(label+'.exit.json'),{'pid':proc.pid,'returncode':proc.returncode,'identity_absent':not alive(entry),'wall_seconds':time.monotonic()-start})
 return {'process':entry,'wall_seconds':time.monotonic()-start,'returncode':proc.returncode}
def require_parent_closure(root=ROOT):
 root=Path(root);c=read_json(root/'configs/PARENT_CLOSURE.json')
 require(c.get('ready') is True and c.get('status')=='READY','R45 WAITING_R42_PARENT_CLOSURE; no source pose or actual parent evidence may be inferred')
 expected=set(c['required_actual_files']);actual=c.get('actual_file_sha256',{})
 require(expected and set(actual)==expected,'actual R42 parent closure inventory incomplete')
 for rel,digest in actual.items():
  require(isinstance(digest,str) and len(digest)==64 and sha(root/rel)==digest,'actual R42 parent closure changed: '+rel)
 case=read_json(root/'configs/protocol.json')['cases'][0]
 require(c['parent_run']==case['parent_run'] and c['parent_root']==case['parent_root'],'parent closure identity differs')
 return c

def bindings(external=False):
 require_parent_closure()
 b=read_json(ROOT/'configs/observer_bindings.json')
 require(sha(ROOT/'configs/protocol.json')==PROTOCOL_SHA,'scientific protocol changed')
 for p,s in b['local_files'].items():require(sha(ROOT/p)==s,'local frozen evidence changed: '+p)
 if external:
  for p,s in b['external_files'].items():require(sha(p)==s,'external frozen evidence changed: '+p)
 return b
def request(path):
 path=inside(path,ROOT/'audit/observations');r=read_json(path)
 require(path.name=='request.json' and r['schema']=='r27-observer-request-v1','request schema/path')
 require(r['protocol_sha256']==PROTOCOL_SHA and r['bindings_sha256']==sha(ROOT/'configs/observer_bindings.json'),'request frozen bindings')
 require(type(r['physical_index']) is int and 0<=r['physical_index']<=19,'request physical index')
 case=case_for(r['run_id']);require(r['branch']=='native' and r['seed']==case['seed'],'request source')
 require(len(r['full_grid'])==21 and r['sigma']==r['full_grid'][r['physical_index']] and r['sigma_next']==r['full_grid'][r['physical_index']+1],'request grid')
 endpoint=inside(r['endpoint_file'],ROOT/'audit/counterfactual')
 require(sha(endpoint)==r['endpoint_file_sha256'],'request endpoint changed')
 require(r['request_id']==path.parent.name and r['run_id']==case['run_id'],'request identity')
 require(alive(r['parent']),'main sampler no longer live')
 return r

def validate_co_resident(parent, uuid, gpu, processes, lookup=identity):
 require(uuid==MAIN_UUID and gpu['uuid']==MAIN_UUID,'wrong decoder GPU')
 require(parent['uid']==os.getuid() and lookup(parent['pid'])==parent,'stale/reused/missing parent')
 require(len(processes)==1 and processes[0]['pid']==parent['pid'] and processes[0]['gpu_uuid']==uuid,'foreign/duplicate/missing compute process')
 require(gpu['memory_free_mib']>=12288,'insufficient decoder memory headroom')
 return dict(gpu,only_compute_parent=parent)

def co_resident_admission(parent,uuid=MAIN_UUID):
 text=subprocess.check_output(['nvidia-smi','--id='+uuid,'--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'],text=True,timeout=10)
 rows=[v.strip().split(',') for v in text.splitlines() if v.strip()]
 require(len(rows)==1 and len(rows[0])==2,'unexpected GPU query schema')
 gpu={'uuid':rows[0][0].strip(),'memory_free_mib':int(rows[0][1])}
 raw=subprocess.check_output(['nvidia-smi','--id='+uuid,'--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True,timeout=10)
 processes=[]
 for line in raw.splitlines():
  if line.strip():
   u,pid=[v.strip() for v in line.split(',')];processes.append({'gpu_uuid':u,'pid':int(pid)})
 return validate_co_resident(parent,uuid,gpu,processes)

def validate_response(response,r,request_sha):
 require(response.get('status')=='complete' and response.get('request_sha256')==request_sha,'stale/incomplete response')
 for key in ('request_id','physical_index','nfe_index','endpoint_file_sha256','condition_sha256','reference_sha256','seed','sigma'):
  require(response.get(key)==r.get(key),'response identity differs: '+key)
 require(response.get('decoder_released_before_pose') is True,'decoder lifecycle incomplete')
 for key in ('decoder','pose_process'):
  require(response[key]['returncode']==0,'nonzero child exit')
 return response

def validate_owned_gpu_limit(rows,permitted,lookup=identity):
 """Global two-card user cap; exact separately admitted jobs may use card two."""
 owned=[]
 for row in rows:
  entry=lookup(row['pid'])
  if entry and entry['uid']==os.getuid():owned.append((row,entry))
 cards={row['gpu_uuid'] for row,entry in owned}
 require(MAIN_UUID in cards and len(cards)<=2,'own GPU count/missing main exceeds frozen resource rule')
 allowed={int(row['pid']):row['identity'] for row in permitted}
 for row,entry in owned:
  if row['gpu_uuid']==MAIN_UUID:continue
  require(row['gpu_uuid']==SECOND_TASK_UUID,'unapproved second GPU UUID')
  old=allowed.get(row['pid'])
  require(old is not None and old['uid']==entry['uid'] and str(old['start_ticks'])==str(entry['start_ticks']) and old['cmdline_sha256']==entry['cmdline_sha256'],'unregistered/reused second-GPU process')
 return sorted(cards)

def admission_document(approved=False):
 value=read_json(ROOT/'configs/admission.json')
 template=read_json(ROOT/'configs/admission_template.json')
 require(set(value)==set(template['fixed_fields'])|{'permitted_compute_processes','root_live_review_required'},'admission document has unreviewed fields')
 for key,expected in template['fixed_fields'].items():require(value[key]==expected,'frozen admission field differs: '+key)
 require(type(value['root_live_review_required']) is bool,'invalid root approval field')
 if approved:require(value['root_live_review_required'] is False,'root live admission not approved')
 require(isinstance(value['permitted_compute_processes'],list),'invalid permitted registry')
 for row in value['permitted_compute_processes']:
  require(set(row)=={'pid','identity'} and type(row['pid']) is int,'permitted PID schema')
  require(set(row['identity'])=={'uid','start_ticks','cmdline_sha256'},'permitted identity schema')
 return value

def case_for(run_id):
 rows=[r for r in read_json(ROOT/'configs/protocol.json')['cases'] if r['run_id']==run_id]
 require(len(rows)==1,'run outside frozen case registry');return rows[0]
