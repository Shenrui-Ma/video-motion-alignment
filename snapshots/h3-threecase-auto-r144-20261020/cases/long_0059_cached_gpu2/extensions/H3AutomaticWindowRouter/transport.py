"""Immutable request transport and exact owned-process supervision (stdlib only)."""
import hashlib,importlib.util,json,os,signal,subprocess,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
_query_spec=importlib.util.spec_from_file_location('_r144_gpu_query_'+hashlib.sha256(str(ROOT).encode()).hexdigest()[:12],ROOT/'scripts/gpu_query.py')
gpu_query=importlib.util.module_from_spec(_query_spec)
_query_spec.loader.exec_module(gpu_query)
PROTOCOL_SHA='57f42c3958bc913a988164503c7dff91514da79bee0e59ba7842016a9826b540'
DECODER_UUID='GPU-REDACTED'
MAIN_UUID='GPU-REDACTED'
SECOND_TASK_UUID=DECODER_UUID
REMOTE_ROOT=Path('/data4/researcher/h3_runs/threecase_auto_r144_20261020/cases/long_0059_cached_gpu2')
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
  command=(p/'cmdline').read_bytes()
  # /proc can expose an empty cmdline during process startup. Bind only after
  # exec has published the actual command; the existing launch deadline applies.
  if not command:return None
  return {'pid':pid,'uid':p.stat().st_uid,'start_ticks':int(tail[19]),'cmdline_sha256':hashlib.sha256(command).hexdigest()}
 except (FileNotFoundError,ProcessLookupError):return None
def alive(entry):return entry is not None and identity(entry['pid'])==entry
def bind_launched_child(process,command,*,timeout=3,lookup=None,clock=time.monotonic,sleep=time.sleep):
 expected=hashlib.sha256(b'\0'.join(os.fsencode(v) for v in command)+b'\0').hexdigest()
 deadline=clock()+timeout;generation=None
 while process.poll() is None and clock()<deadline:
  candidate=(lookup or identity)(process.pid)
  if candidate is not None:
   current=(candidate['pid'],candidate['uid'],candidate['start_ticks'])
   require(candidate['uid']==os.getuid(),'launched child owner differs')
   if generation is None:generation=current
   require(current==generation,'child generation changed before command binding')
   if candidate['cmdline_sha256']==expected:return candidate
  sleep(.01)
 raise ValueError('unable to bind launched child to complete expected argv')
def bind_or_reap_launched_child(process,command):
 try:return bind_launched_child(process,command)
 except BaseException as primary:
  # This is our newly created, still-unregistered direct Popen child.
  try:
   if process.poll() is None:process.terminate()
   try:process.wait(timeout=8)
   except subprocess.TimeoutExpired:
    if process.poll() is None:process.kill()
    process.wait(timeout=10)
  except BaseException as cleanup:
   if hasattr(primary,'add_note'):primary.add_note('unregistered child cleanup: '+repr(cleanup))
  raise
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
  require(isinstance(execution_timeout,(int,float)) and 0<execution_timeout<=780,'invalid child execution timeout')
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
   entry=bind_or_reap_launched_child(proc,command)
   write_new(directory/(label+'.process.json'),dict(entry,command=command,parent=parent,timeout_seconds=timeout,execution_timeout_seconds=execution_timeout,execution_started_path=str(marker) if marker else None))
   while proc.poll() is None:
    require(alive(parent),'parent exited during child execution')
    check_execution_budget()
    if time.monotonic()-start>timeout:raise TimeoutError(label+' total timeout')
    time.sleep(.2)
   if proc.returncode:raise ChildExitError(label+' exit '+str(proc.returncode)+'; see '+str(log),{'process':entry,'wall_seconds':time.monotonic()-start,'returncode':proc.returncode,'execution_start':execution_start})
   check_execution_budget()
   if marker is not None:require(execution_start is not None,'successful child lacks execution start evidence')
 finally:
  if proc is not None:
   primary_error=sys.exc_info()[1];cleanup_error=None
   try:terminate_owned(proc,entry)
   except Exception as error:
    cleanup_error=type(error).__name__+': '+str(error)
    if primary_error is None:raise
   write_new(directory/(label+'.exit.json'),{'pid':proc.pid,'returncode':proc.returncode,'identity_absent':(not alive(entry) if entry is not None else proc.poll() is not None),'wall_seconds':time.monotonic()-start,'execution_start':execution_start,'cleanup_error':cleanup_error})
 return {'process':entry,'wall_seconds':time.monotonic()-start,'returncode':proc.returncode,'execution_start':execution_start}
def require_parent_closure(root=ROOT):
 root=Path(root);c=read_json(root/'configs/PARENT_CLOSURE.json')
 require(c.get('ready') is True and c.get('status')=='READY','R86 actual parent materialization pending')
 cases=read_json(root/'configs/protocol.json')['cases']
 require(set(c['cases'])=={v['source_id'] for v in cases},'single-case parent closure incomplete')
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

def preserved_user_process(row,entry):
 """Exclude only the exact user-owned 8189 generation from research-card count."""
 runtime=read_json(ROOT/'configs/runtime.json');expected=runtime['preserved_user_service']
 if row['pid']!=expected['pid']:return False
 require(entry is not None and entry['uid']==expected['uid'] and
         str(entry['start_ticks'])==str(expected['start_ticks']) and
         entry['cmdline_sha256']==expected['cmdline_sha256'] and
         row['gpu_uuid']==runtime['preserved_user_service_gpu'],
         'preserved user service generation/device differs')
 return True

def validate_preserved_registry(permitted):
 runtime=read_json(ROOT/'configs/runtime.json');expected=runtime['preserved_user_service']
 require(len(permitted)==1 and permitted[0]['pid']==expected['pid'],
         'online trial permits only the preserved user service')
 old=permitted[0]['identity']
 require(old['uid']==expected['uid'] and str(old['start_ticks'])==str(expected['start_ticks']) and
         old['cmdline_sha256']==expected['cmdline_sha256'],'preserved registry identity differs')
 return True

def decoder_memory_profile(*,bootstrap=False):
 path=ROOT/'configs/decoder_memory_profile.json';p=read_json(path)
 require(p.get('schema')=='r86-decoder-capacity-trial-v1' and p.get('status')=='ROOT_158_CAPACITY_TRIAL_UNMEASURED','decoder trial scope differs')
 require(p['geometry']=={'width':1312,'height':736,'frames':158,'fps':24} and p['required_free_bytes']==16*1024**3,'decoder trial geometry/budget differs')
 approval=read_json(ROOT/'audit/ROOT_ONLINE_APPROVAL.json')
 require(approval.get('root_approved') is True and approval['decoder_profile_sha256']==sha(path),'root decoder trial approval pending')
 require(approval['runtime_sha256']==sha(ROOT/'configs/runtime.json'),'runtime trial binding differs')
 return dict(p,profile_sha256=sha(path),profile_scope='host41 full158 real capacity trial; 16GiB admission, no claimed 158 measurement')

def validate_resource_capacity(uuid,gpu,processes,required_bytes,*,parent=None,lookup=resource_process_identity):
 snapshot={'observed_unix':time.time(),'gpu':dict(gpu),'expected_parent':parent,'required_free_bytes':required_bytes,'processes':[]}
 if uuid!=DECODER_UUID or gpu['uuid']!=uuid or uuid==MAIN_UUID:
  raise AdmissionIntegrityError('wrong isolated decoder GPU',snapshot)
 entries={}
 for row in processes:
  try:entry=lookup(row['pid'])
  except (PermissionError,ProcessLookupError,FileNotFoundError):entry=None
  entries[row['pid']]=entry;snapshot['processes'].append(dict(row,identity=entry))
 if parent is not None:
  actual=lookup(parent['pid']);snapshot['actual_parent']=actual
  if parent['uid']!=os.getuid() or actual!=parent:
   raise AdmissionIntegrityError('stale/reused/missing main parent',snapshot)
  if not any(row['gpu_uuid']==MAIN_UUID and row['pid']==parent['pid'] for row in processes):
   raise ResourceUnavailable('main parent compute not yet visible',snapshot)
 if any(entry is None for entry in entries.values()):
  raise ResourceUnavailable('compute process ownership unavailable',snapshot)
 owned={row['gpu_uuid'] for row in processes if entries[row['pid']]['uid']==os.getuid() and not preserved_user_process(row,entries[row['pid']])}
 if parent is not None and any(row['gpu_uuid']!=MAIN_UUID and entries[row['pid']]['uid']==os.getuid() and not preserved_user_process(row,entries[row['pid']]) for row in processes):
  raise ResourceUnavailable('another owned research CUDA process is active outside main',snapshot)
 planned=owned|{DECODER_UUID}|({MAIN_UUID} if parent is not None else set())
 if len(planned)>2:raise ResourceUnavailable('planned decoder exceeds two owned GPU cards',snapshot)
 if gpu['memory_free_mib']*1024**2<required_bytes:
  raise ResourceUnavailable('decoder GPU lacks measured memory headroom',snapshot)
 return dict(gpu,main_compute_parent=parent,planned_owned_GPUs=sorted(planned),owned_GPU_cards=sorted(owned),required_free_bytes=required_bytes,resource_snapshot=snapshot)

def standalone_decoder_admission(uuid):
 profile=decoder_memory_profile(bootstrap=True)
 gpu,processes,snapshot=query_resource_state(uuid)
 try:result=validate_resource_capacity(uuid,gpu,processes,profile['required_free_bytes'])
 except (ResourceUnavailable,AdmissionIntegrityError) as error:
  error.snapshot.update(snapshot);raise
 return dict(result,memory_profile_sha256=profile['profile_sha256'],memory_profile_scope=profile['profile_scope'])

def validate_separate_decoder(parent,uuid,gpu,processes,lookup=resource_process_identity):
 profile=decoder_memory_profile()
 result=validate_resource_capacity(uuid,gpu,processes,profile['required_free_bytes'],parent=parent,lookup=lookup)
 return dict(result,memory_profile_sha256=profile['profile_sha256'],memory_profile_scope=profile['profile_scope'])

def query_resource_state(uuid):
 snapshot={'observed_unix':time.time(),'requested_gpu':uuid,'gpu_raw':None,'compute_raw':None}
 gpu_query.policy(ROOT,read_json(ROOT/'configs/runtime.json'),uuid)
 try:
  text=subprocess.check_output(['nvidia-smi','--id='+uuid,'--query-gpu=uuid,memory.used,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=10);snapshot['gpu_raw']=text
  raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True,timeout=10);snapshot['compute_raw']=raw
 except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:
  snapshot['query_error']=str(error);raise ResourceUnavailable('GPU query temporarily unavailable',snapshot) from error
 try:
  rows=[v.strip().split(',') for v in text.splitlines() if v.strip()]
  if len(rows)!=1 or len(rows[0])!=4:raise ValueError('GPU row shape')
  gpu={'uuid':rows[0][0].strip(),'memory_used_mib':int(rows[0][1]),'memory_free_mib':int(rows[0][2]),'utilization_percent':int(rows[0][3])}
  if min(gpu['memory_used_mib'],gpu['memory_free_mib'],gpu['utilization_percent'])<0 or gpu['utilization_percent']>100:raise ValueError('GPU quantities')
  processes,quarantine=gpu_query.parse_and_record(ROOT,read_json(ROOT/'configs/runtime.json'),raw,uuid)
  snapshot['quarantine']=quarantine
 except ValueError as error:raise AdmissionIntegrityError('unexpected GPU query schema',snapshot) from error
 return gpu,processes,snapshot

def separate_decoder_admission(parent,uuid=DECODER_UUID):
 gpu,processes,snapshot=query_resource_state(uuid)
 try:return validate_separate_decoder(parent,uuid,gpu,processes)
 except (ResourceUnavailable,AdmissionIntegrityError) as error:
  error.snapshot.update(snapshot);raise

# Dedicated exit code plus bound typed-CUDA-OOM proof distinguishes retriable
# allocator exhaustion from data, numerical, driver and child-lifetime failures.
CUDA_OOM_EXIT=86
class ChildExitError(RuntimeError):
 def __init__(self,message,result):super().__init__(message);self.result=result

def typed_cuda_oom(error,oom_type):
 chain=[];seen=set();current=error
 while current is not None and id(current) not in seen and len(chain)<12:
  seen.add(id(current));chain.append({'type':type(current).__name__,'message':str(current)})
  if oom_type is not None and isinstance(current,oom_type) and 'cuda' in str(current).lower() and 'out of memory' in str(current).lower():return chain
  current=current.__cause__ if current.__cause__ is not None else current.__context__
 return None

def validate_oom_proof(path,child,r,request_sha):
 p=read_json(path)
 require(child['returncode']==CUDA_OOM_EXIT and p.get('schema')=='h3-typed-cuda-oom-v4','unclassified decoder child failure')
 require(p.get('identity')==child['process'] and p.get('request_sha256')==request_sha,'OOM proof identity/request changed')
 for key in ('endpoint_file_sha256','seed','geometry'):
  require(p.get(key)==r.get(key),'OOM proof input changed: '+key)
 require(p.get('typed_cuda_oom') is True and isinstance(p.get('exception_chain'),list) and p['exception_chain'],'typed CUDA OOM evidence missing')
 return p

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
 profile=decoder_memory_profile()
 require(admission['memory_profile_sha256']==profile['profile_sha256'] and admission['required_free_bytes']==profile['required_free_bytes'] and admission['memory_free_mib']*1024**2>=profile['required_free_bytes'],'response decoder memory admission invalid')
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
  if entry and entry['uid']==os.getuid() and not preserved_user_process(row,entry):owned.append((row,entry))
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
 require(set(value)==set(template['fixed_fields'])|{'permitted_compute_processes','root_live_review_required','ready_for_launch'},'admission document has unreviewed fields')
 for key,expected in template['fixed_fields'].items():require(value[key]==expected,'frozen admission field differs: '+key)
 require(type(value['root_live_review_required']) is bool,'invalid root approval field')
 require(type(value['ready_for_launch']) is bool,'invalid root launch flag')
 if approved:require(value['root_live_review_required'] is False and value['ready_for_launch'] is True,'root live admission not approved')
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
