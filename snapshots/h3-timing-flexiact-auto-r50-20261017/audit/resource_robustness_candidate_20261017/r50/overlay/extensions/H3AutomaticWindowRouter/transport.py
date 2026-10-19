"""Immutable request transport and exact owned-process supervision (stdlib only)."""
import hashlib,json,os,signal,subprocess,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PROTOCOL_SHA='e8058874b94bce9673fe82773d3b75aecb3cdc92d12f9469975afc56466c6d73'
DECODER_UUID='GPU-REDACTED'
MAIN_UUID='GPU-REDACTED'
SECOND_TASK_UUID='GPU-REDACTED'
REMOTE_ROOT=Path('/data5/researcher/h3_runs/timing_flexiact_auto_r50_20261017')
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
def run_child(command,env,directory,label,timeout,parent,*,execution_started_path=None,execution_timeout=None):
 directory=Path(directory);log=directory/(label+'.log');start=time.monotonic();proc=None;entry=None;execution_start=None
 marker=None
 if execution_started_path is not None:
  marker=inside(str(Path(execution_started_path).absolute()),ROOT/'audit/observations')
  require(not marker.exists(),'execution marker already exists')
  require(isinstance(execution_timeout,(int,float)) and 0<execution_timeout<=180,'invalid child execution timeout')
 def check_execution_budget():
  nonlocal execution_start
  if marker is None:return
  if execution_start is None and marker.exists():
   try:record=read_json(marker)
   except json.JSONDecodeError:return  # write_new may be between open and write
   require(record.get('schema')=='h3-child-execution-start-v1' and record.get('identity')==entry,'execution marker identity differs')
   started=record.get('started_monotonic')
   require(type(started) in (int,float) and start<=started<=time.monotonic(),'execution marker time invalid')
   execution_start=record
  if execution_start is not None and time.monotonic()-execution_start['started_monotonic']>execution_timeout:
   raise TimeoutError(label+' execution timeout')
 try:
  require(alive(parent),'parent exited before child launch')
  with log.open('xb') as handle:
   proc=subprocess.Popen(command,env=env,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
   deadline=time.monotonic()+3
   while entry is None and proc.poll() is None and time.monotonic()<deadline:
    entry=identity(proc.pid)
   require(entry is not None and entry['uid']==os.getuid(),'unable to bind own child')
   write_new(directory/(label+'.process.json'),dict(entry,command=command,parent=parent,timeout_seconds=timeout,execution_timeout_seconds=execution_timeout,execution_started_path=str(marker) if marker else None))
   while proc.poll() is None:
    require(alive(parent),'parent exited during child execution')
    check_execution_budget()
    if time.monotonic()-start>timeout:raise TimeoutError(label+' total timeout')
    time.sleep(.2)
   if proc.returncode:raise RuntimeError(label+' exit '+str(proc.returncode)+'; see '+str(log))
   check_execution_budget()
   if marker is not None:require(execution_start is not None,'successful child lacks execution start evidence')
 finally:
  if proc is not None:
   terminate_owned(proc,entry)
   write_new(directory/(label+'.exit.json'),{'pid':proc.pid,'returncode':proc.returncode,'identity_absent':not alive(entry),'wall_seconds':time.monotonic()-start,'execution_start':execution_start})
 return {'process':entry,'wall_seconds':time.monotonic()-start,'returncode':proc.returncode,'execution_start':execution_start}
def require_parent_closure(root=ROOT):
 root=Path(root);c=read_json(root/'configs/PARENT_CLOSURE.json')
 require(c.get('ready') is True and c.get('status')=='READY','R50 WAITING_R49_ACTUAL_ARCHIVES')
 cases=read_json(root/'configs/protocol.json')['cases']
 require(set(c['cases'])=={v['source_id'] for v in cases},'five-case parent closure incomplete')
 for case in cases:
  row=c['cases'][case['source_id']]
  require(row['ready'] is True and row['parent_run']==case['parent_run'],'parent closure case identity differs')
  expected=set(row['required_actual_files']);actual=row['actual_file_sha256']
  require(expected and set(actual)==expected,'actual parent inventory incomplete')
  for rel,digest in actual.items():
   p=inside(str((root/rel).absolute()),root)
   require(isinstance(digest,str) and len(digest)==64 and sha(p)==digest,'parent evidence changed: '+rel)
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
 geometry=geometry_for(r['run_id'])
 require(r.get('geometry')==geometry.video_geometry and r.get('observation_domain')==geometry.domain_record,'request geometry/domain mismatch')
 require(len(r['full_grid'])==21 and r['sigma']==r['full_grid'][r['physical_index']] and r['sigma_next']==r['full_grid'][r['physical_index']+1],'request grid')
 endpoint=inside(r['endpoint_file'],ROOT/'audit/counterfactual')
 require(sha(endpoint)==r['endpoint_file_sha256'],'request endpoint changed')
 require(r['request_id']==path.parent.name and r['run_id']==case['run_id'],'request identity')
 require(alive(r['parent']),'main sampler no longer live')
 return r

class ResourceUnavailable(ValueError):
 """A transient resource observation, distinct from identity/data failure."""
 def __init__(self,reason,snapshot):
  super().__init__(reason);self.snapshot=snapshot

class AdmissionIntegrityError(ValueError):
 def __init__(self,reason,snapshot):
  super().__init__(reason);self.snapshot=snapshot

def resource_process_identity(pid):
 # Ownership is enough for unrelated users; their command lines are not read.
 proc=Path('/proc')/str(pid)
 try:uid=proc.stat().st_uid
 except (FileNotFoundError,ProcessLookupError):return None
 return identity(pid) if uid==os.getuid() else {'pid':pid,'uid':uid}

def validate_separate_decoder(parent,uuid,gpu,processes,lookup=resource_process_identity):
 snapshot={'observed_unix':time.time(),'gpu':dict(gpu),'expected_parent':parent,'processes':[]}
 entries={}
 for row in processes:
  try:entry=lookup(row['pid'])
  except (PermissionError,ProcessLookupError,FileNotFoundError):entry=None
  entries[row['pid']]=entry
  snapshot['processes'].append(dict(row,identity=entry))
 actual=lookup(parent['pid'])
 snapshot['actual_parent']=actual
 if uuid!=DECODER_UUID or uuid==MAIN_UUID or gpu['uuid']!=DECODER_UUID:
  raise AdmissionIntegrityError('wrong isolated decoder GPU',snapshot)
 if parent['uid']!=os.getuid() or actual!=parent:
  raise AdmissionIntegrityError('stale/reused/missing main parent',snapshot)
 if any(row['gpu_uuid']==DECODER_UUID for row in processes):
  raise ResourceUnavailable('decoder GPU has active compute',snapshot)
 main=[row for row in processes if row['gpu_uuid']==MAIN_UUID]
 if len(main)!=1 or main[0]['pid']!=parent['pid']:
  raise ResourceUnavailable('foreign/duplicate/missing main compute',snapshot)
 if any(entry is None for entry in entries.values()):
  raise ResourceUnavailable('compute process ownership unavailable',snapshot)
 owned={row['gpu_uuid'] for row in processes if entries[row['pid']]['uid']==os.getuid()}
 if owned!={MAIN_UUID}:
  raise ResourceUnavailable('isolated decoder needs the second owned GPU slot',snapshot)
 if gpu['memory_used_mib']>1024 or gpu['memory_free_mib']<45000 or gpu['utilization_percent']!=0:
  raise ResourceUnavailable('decoder GPU lacks idle headroom',snapshot)
 return dict(gpu,main_compute_parent=parent,planned_owned_GPUs=sorted([MAIN_UUID,DECODER_UUID]),owned_GPU_cards=sorted(owned),resource_snapshot=snapshot)

def separate_decoder_admission(parent,uuid=DECODER_UUID):
 snapshot={'observed_unix':time.time(),'requested_gpu':uuid,'gpu_raw':None,'compute_raw':None}
 try:
  text=subprocess.check_output(['nvidia-smi','--id='+uuid,'--query-gpu=uuid,memory.used,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=10)
  snapshot['gpu_raw']=text
  raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True,timeout=10)
  snapshot['compute_raw']=raw
 except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:
  snapshot['query_error']=str(error)
  raise ResourceUnavailable('GPU query temporarily unavailable',snapshot) from error
 try:
  rows=[v.strip().split(',') for v in text.splitlines() if v.strip()]
  if len(rows)!=1 or len(rows[0])!=4:raise ValueError('GPU row shape')
  gpu={'uuid':rows[0][0].strip(),'memory_used_mib':int(rows[0][1]),'memory_free_mib':int(rows[0][2]),'utilization_percent':int(rows[0][3])}
  processes=[]
  for line in raw.splitlines():
   if line.strip():
    u,pid=[v.strip() for v in line.split(',')];processes.append({'gpu_uuid':u,'pid':int(pid)})
 except ValueError as error:
  raise AdmissionIntegrityError('unexpected GPU query schema',snapshot) from error
 try:return validate_separate_decoder(parent,uuid,gpu,processes)
 except (ResourceUnavailable,AdmissionIntegrityError) as error:
  error.snapshot.update(gpu_raw=text,compute_raw=raw)
  raise

def record_resource_event(path,record):
 if path is None:return
 path=inside(str(Path(path).absolute()),ROOT/'audit/observations')
 with path.open('a') as handle:
  handle.write(json.dumps(record,sort_keys=True,allow_nan=False)+'\n');handle.flush();os.fsync(handle.fileno())

def wait_decoder_admission(parent,uuid=DECODER_UUID,*,deadline=None,timeout=600,audit_path=None,clock=time.monotonic,sleep=time.sleep,check=None,is_alive=alive):
 start=clock()
 if not 0<timeout<=600:raise ValueError('resource wait must be positive and at most600seconds')
 deadline=start+timeout if deadline is None else deadline
 if not isinstance(deadline,(float,int)) or not 0<deadline-start<=600.001:
  raise TimeoutError('resource admission deadline expired or invalid')
 attempt=0
 while True:
  attempt+=1
  if not is_alive(parent):
   record_resource_event(audit_path,{'status':'hard_failure','reason':'sampler identity changed','expected_parent':parent,'elapsed_seconds':clock()-start})
   raise ValueError('sampler identity changed while waiting decoder admission')
  if clock()>=deadline:raise TimeoutError('resource admission deadline expired')
  try:
   result=(check or separate_decoder_admission)(parent,uuid)
  except ResourceUnavailable as error:
   record_resource_event(audit_path,{'status':'waiting','attempt':attempt,'reason':str(error),'snapshot':error.snapshot,'elapsed_seconds':clock()-start})
   if clock()>=deadline:raise TimeoutError('decoder resource unavailable within bounded wait') from error
   sleep(min(1,deadline-clock()))
  except Exception as error:
   record_resource_event(audit_path,{'status':'hard_failure','attempt':attempt,'reason':type(error).__name__+': '+str(error),'snapshot':getattr(error,'snapshot',None),'elapsed_seconds':clock()-start})
   raise
  else:
   if clock()>deadline:
    record_resource_event(audit_path,{'status':'timeout','attempt':attempt,'reason':'query completed after resource deadline','snapshot':result,'elapsed_seconds':clock()-start})
    raise TimeoutError('resource query completed after admission deadline')
   record_resource_event(audit_path,{'status':'admitted','attempt':attempt,'snapshot':result,'elapsed_seconds':clock()-start})
   return result

def validate_response(response,r,request_sha):
 require(response.get('status')=='complete' and response.get('request_sha256')==request_sha,'stale/incomplete response')
 for key in ('request_id','physical_index','nfe_index','endpoint_file_sha256','condition_sha256','reference_sha256','seed','sigma'):
  require(response.get(key)==r.get(key),'response identity differs: '+key)
 require(response.get('decoder_released_before_pose') is True,'decoder lifecycle incomplete')
 admission=response['decoder_admission']
 require(admission['uuid']==DECODER_UUID and admission['main_compute_parent']==r['parent'],'response decoder/main placement differs')
 require(admission['memory_free_mib']>=45000 and admission['memory_used_mib']<=1024 and admission['utilization_percent']==0,'response decoder admission invalid')
 released=response['after_decoder_release']
 require(released['schema']=='h3-own-decoder-release-v1' and released['gpu_uuid']==DECODER_UUID,'response release schema/device differs')
 require(released['child_identity']==response['decoder']['process'] and released['original_generation_absent'] is True,'response original decoder generation remains')
 require(released['nvml_pid_absent'] is True or released['pid_reused'] is True,'response original decoder NVML tail remains')
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


def geometry_for(run_id):
 # Imported by the standalone transport loader as well as the Comfy package.
 import importlib.util,sys
 path=ROOT/'extensions/H3AutomaticWindowRouter/geometry.py'
 name='_r50_geometry_contract'
 if name not in sys.modules:
  spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
 return sys.modules[name].Geometry.from_case(case_for(run_id))
