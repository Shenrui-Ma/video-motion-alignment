def decoder_memory_profile(*,bootstrap=False):
 path=ROOT/'configs/decoder_memory_profile.json';p=read_json(path)
 require(p.get('schema')=='h3-decoder-memory-profile-v4','decoder memory profile schema')
 require(p.get('safety_margin_bytes')==2*1024**3,'decoder memory margin differs')
 if p.get('status')=='PENDING':
  require(bootstrap and p.get('geometry')=={'frames':90,'height':736,'width':1312,'fps':24},'measured decoder memory profile required')
  require(p.get('bootstrap_required_free_bytes')==16*1024**3,'bootstrap budget differs')
  return dict(p,required_free_bytes=16*1024**3,profile_sha256=sha(path),profile_scope='unprofiled standalone full90 bootstrap')
 require(p.get('status')=='MEASURED','decoder profile is not measured')
 evidence=inside(str((ROOT/p['evidence_file']).absolute()),ROOT/'configs/decoder_memory_evidence')
 require(sha(evidence)==p['evidence_sha256'],'decoder memory evidence changed')
 gate=read_json(evidence);d=gate['decode'];g=p['geometry']
 require(gate.get('passed') is True and gate.get('NFE')==0 and gate.get('model_forward_calls')==0,'decoder memory gate failed')
 require(d.get('status')=='complete' and d.get('decoded_shape')==[g['frames'],g['height'],g['width'],3] and d.get('fps')==g['fps'],'decoder memory geometry differs')
 require(d.get('vae_sha256')==p['vae_sha256'] and d['fallback_guard']['calls']==0,'decoder memory model/fallback differs')
 peak=d['max_memory_reserved_bytes'];allocated=d['max_memory_allocated_bytes']
 require(type(peak) is int and type(allocated) is int and 0<allocated<=peak,'decoder memory measurement invalid')
 require(p['peak_reserved_bytes']==peak and p['required_free_bytes']==peak+p['safety_margin_bytes'],'decoder budget differs from measurement plus margin')
 return dict(p,profile_sha256=sha(path),profile_scope='measured full-shape decoder plus2GiB')

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
 owned={row['gpu_uuid'] for row in processes if entries[row['pid']]['uid']==os.getuid()}
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
 try:
  text=subprocess.check_output(['nvidia-smi','--id='+uuid,'--query-gpu=uuid,memory.used,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=10);snapshot['gpu_raw']=text
  raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True,timeout=10);snapshot['compute_raw']=raw
 except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:
  snapshot['query_error']=str(error);raise ResourceUnavailable('GPU query temporarily unavailable',snapshot) from error
 try:
  rows=[v.strip().split(',') for v in text.splitlines() if v.strip()]
  if len(rows)!=1 or len(rows[0])!=4:raise ValueError('GPU row shape')
  gpu={'uuid':rows[0][0].strip(),'memory_used_mib':int(rows[0][1]),'memory_free_mib':int(rows[0][2]),'utilization_percent':int(rows[0][3])}
  if min(gpu['memory_used_mib'],gpu['memory_free_mib'],gpu['utilization_percent'])<0 or gpu['utilization_percent']>100:raise ValueError('GPU quantities')
  processes=[]
  for line in raw.splitlines():
   if line.strip():
    u,pid=[v.strip() for v in line.split(',')];processes.append({'gpu_uuid':u,'pid':int(pid)})
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

