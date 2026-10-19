"""Root-only administrative launch. Import and --plan are inert; --execute is explicit.

No producer files are changed. Uses R43's sealed preCUDA service_entry and exact-owner
lifecycle. R40 RUN_GATE + release + cleanup must already exist; no release is requested.
"""
from pathlib import Path
import argparse,fcntl,hashlib,importlib,json,os,subprocess,sys,time,urllib.request

ROOT=Path('/data5/researcher/h3_runs/timing_source51765_native_r43_20261017')
OLD=Path('/data5/researcher/h3_runs/timing_auto_source51310_r40_20261017')
OLD_RUN='r40_source51310_seed2026101701_auto'
GPU='GPU-REDACTED';PEER_GPU='GPU-REDACTED';PORT=8505
MANIFEST_SHA='44120ecd803eeac051540bb5ea1d24e59e8c72a7b0eb7b55b6700be44e4818c7'
OLD_ID={'pid':16635,'uid':1016,'start_ticks':'2623514879','cmdline_sha256':'850af6280946af017471126c5ab5116c554b5d34d3e934bb7e4f1f4a896b13b6'}

def require(ok,message):
 if not ok:raise ValueError(message)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_new(p,value):
 p=Path(p);data=(json.dumps(value,indent=2)+'\n').encode();tmp=p.with_name(p.name+'.'+str(os.getpid())+'.tmp')
 with tmp.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 try:os.link(tmp,p)
 finally:tmp.unlink()
def raw_command_sha(owner):return hashlib.sha256(b'\0'.join(x.encode() for x in owner['command'])+b'\0').hexdigest()
def external_from_owner(owner):
 return {'uid':owner['identity']['uid'],'start_ticks':str(owner['identity']['start_ticks']),'cmdline_sha256':raw_command_sha(owner)}
def check_config(c):
 require(c.get('schema')=='r43-root-launch-config-v1' and c.get('root_approved') is True,'root config approval required')
 require(set(c)=={'schema','root_approved','old_run_gate_sha256','old_cleanup_sha256','old_release_sha256','peer'},'unexpected config fields')
 peer=c['peer'];require(set(peer)=={'root','pid','identity','manifest_sha256','admission_sha256'},'peer config schema')
 root=Path(peer['root']);require(root.is_absolute() and root.parent==ROOT.parent and root not in (ROOT,OLD),'peer root outside task area')
 require(type(peer['pid']) is int and peer['pid']>1,'peer PID schema')
 identity=peer['identity'];require(set(identity)=={'uid','start_ticks','cmdline_sha256'} and type(identity['uid']) is int and isinstance(identity['start_ticks'],str) and identity['start_ticks'].isdigit(),'peer exact identity schema')
 for value in (c['old_run_gate_sha256'],c['old_cleanup_sha256'],c['old_release_sha256'],peer['manifest_sha256'],peer['admission_sha256'],identity['cmdline_sha256']):
  require(isinstance(value,str) and len(value)==64 and all(x in '0123456789abcdef' for x in value),'unbound SHA in root config')
 return c

def validate_release(gate,cleanup,release,gate_file,gate_sha,old_absent):
 require(gate.get('passed') is True and gate.get('run_id')==OLD_RUN,'R40 archive RUN_GATE is not complete')
 owner=gate['owner'];require(owner['pid']==OLD_ID['pid'] and owner['gpu_uuid']==GPU and owner['port']==8502,'wrong R40 owner')
 require(external_from_owner(owner)=={k:OLD_ID[k] for k in ('uid','start_ticks','cmdline_sha256')},'wrong historical R40 generation')
 require(cleanup.get('pid')==owner['pid'] and cleanup.get('service_record')==owner,'cleanup belongs to another generation')
 for key in ('process_absent','own_compute_absent','child_compute_absent'):require(cleanup.get(key) is True,'R40 cleanup incomplete: '+key)
 require(release.get('pid')==owner['pid'] and release.get('owner')==owner['identity'],'root release owner differs')
 require(release.get('gate_file')==str(gate_file) and release.get('gate_sha256')==gate_sha,'root release is not bound to this RUN_GATE')
 require(old_absent is True,'R40 exact PID still exists; refuse even reused PID')
 require(gate.get('runtime',{}).get('status')=='pass','R40 actual runtime gate failed')
 return owner

def validate_peer(config,owner,current_identity,current_uid):
 expected=config['identity']
 require(expected['uid']==current_uid and current_identity==expected,'peer live UID/start/cmdSHA differs')
 require(owner['pid']==config['pid'] and owner['gpu_uuid']==PEER_GPU,'peer registry PID/device differs')
 require(external_from_owner(owner)==expected,'peer service registry differs from live command')
 require(str(Path(config['root'])) in owner['command'],'peer command does not bind its root')
 return owner

def next_peer_admission(old,new_owner,new_identity):
 require(old.get('scope')=='own_user_video_jobs','peer admission scope differs')
 if 'root_live_review_required' in old:require(old['root_live_review_required'] is False,'peer automatic admission not approved')
 elif 'ready_for_launch' in old:require(old['ready_for_launch'] is True,'peer native admission not approved')
 else:raise ValueError('unknown peer admission schema')
 require(new_owner['gpu_uuid']==GPU and new_owner['port']==PORT,'new owner resource differs')
 require(external_from_owner(new_owner)==new_identity,'new owner identity differs')
 expected={k:OLD_ID[k] for k in ('uid','start_ticks','cmdline_sha256')};rows=[];seen=set()
 for row in old['permitted_compute_processes']:
  require(row['pid'] not in seen,'duplicate peer permitted PID');seen.add(row['pid'])
  require(row['pid']!=new_owner['pid'],'new PID already registered; explicit recovery required')
  if row['pid']==OLD_ID['pid']:require(row['identity']==expected,'old permitted PID reused/wrong identity')
  else:rows.append(row)
 rows.append({'pid':new_owner['pid'],'identity':new_identity})
 return dict(old,permitted_compute_processes=rows)

def validate_gate(gate,owner,external,bootstrap_sha):
 require(gate.get('schema')=='r43-before-CUDA-root-gate-v1','unexpected preCUDA schema')
 require(gate['pid']==owner['pid'] and gate['identity']==external==external_from_owner(owner),'preCUDA PID generation differs')
 require(owner['gpu_uuid']==GPU and owner['port']==PORT,'preCUDA resource mismatch')
 require(gate['target']==str(ROOT/'scripts/compatibility_bootstrap.py') and gate['target_sha256']==bootstrap_sha,'preCUDA bootstrap mismatch')
 return gate

def owner_from_startup_log(text):
 records=[]
 for line in text.splitlines():
  try:value=json.loads(line)
  except json.JSONDecodeError:continue
  if isinstance(value,dict) and value.get('service_only') is True and 'gate_ready' in value:records.append(value)
 require(len(records)==1 and records[0].get('controller_started') is False,'service-only did not return one gated child')
 record=records[0];require(record['gate_ready']['pid']==record['service']['pid'],'startup child/gate mismatch')
 return record['service']

# Ordered, injectable sequence so CPU tests exercise the same go/controller ordering.
def launch_sequence(ops):
 ops.precheck()
 ops.launch_service_only()
 owner,gate=ops.ready_owner()
 ops.register_peer(owner)
 ops.recheck_before_go(owner,gate)
 ops.go(gate)
 ops.wait_http(owner)
 ops.start_controller(owner)
 return owner

class RealOperations:
 def __init__(self,config,attempt):
  self.c=config;self.attempt=attempt;self.owner=None;self.gate=None;self.peer_after=None
  sys.path.insert(0,str(ROOT/'scripts'));self.service=importlib.import_module('service')
  require(self.service.RUN==ROOT and self.service.GPU==GPU and self.service.PORT==PORT,'imported service belongs to wrong task')
 def logged(self,name,command,timeout):
  with (self.attempt/(name+'.log')).open('xb') as f:
   result=subprocess.run(command,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=timeout,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
  require(result.returncode==0,name+' failed; retained log')
 def peer(self):
  c=self.c['peer'];root=Path(c['root'])
  require(sha(root/'deploy_manifest.json')==c['manifest_sha256'],'peer producer seal changed')
  owner=read(root/'processes/service.json')
  return validate_peer(c,owner,self.service.external_identity(c['pid']),os.getuid())
 def released(self):
  gate_file=OLD/'analysis/postrun/captured'/OLD_RUN/'RUN_GATE.json'
  paths={'old_run_gate_sha256':gate_file,'old_cleanup_sha256':OLD/'processes/cleanup.json','old_release_sha256':OLD/'audit/root_release_request.json'}
  for key,path in paths.items():require(sha(path)==self.c[key],'R40 release evidence changed: '+key)
  gate,cleanup,release=[read(paths[k]) for k in paths]
  owner=validate_release(gate,cleanup,release,gate_file,self.c['old_run_gate_sha256'],not Path('/proc',str(OLD_ID['pid'])).exists())
  require(sha(gate_file.parent/'FILE_INVENTORY.json')==gate['file_inventory_sha256'],'R40 inventory anchor differs')
  receipt=read(OLD/'analysis/postrun/archive_receipts'/f'{OLD_RUN}.json')
  require(receipt['owner']==owner and receipt['run_id']==OLD_RUN and receipt['run_gate_sha256']==sha(gate_file) and receipt['inventory_sha256']==gate['file_inventory_sha256'],'R40 archive receipt differs')
  require(release['unix']>=gate_file.stat().st_mtime,'R40 release predates gate')
  return {'owner':owner,'gate_sha256':sha(gate_file),'cleanup_sha256':sha(paths['old_cleanup_sha256']),'release_sha256':sha(paths['old_release_sha256'])}
 def strict_idle(self):
  peer=self.peer();rows=self.service.compute_processes()
  admission={'ready_for_launch':True,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[{'pid':peer['pid'],'identity':self.c['peer']['identity']}]}
  self.service.check_admission(admission,rows,{'queue_running':[],'queue_pending':[]})
  return admission,rows,self.service.gpu_readiness()
 def precheck(self):
  require(sha(ROOT/'deploy_manifest.json')==MANIFEST_SHA,'R43 sealed producer changed')
  for rel,item in read(ROOT/'deploy_manifest.json')['files'].items():require(sha(ROOT/rel)==item['sha256'],'sealed producer file changed: '+rel)
  self.service.refuse_existing_service()
  for rel in ('cuda_gate_ready.json','cuda_gate_go.json','controller.json'):
   require(not (ROOT/'processes'/rel).exists(),'existing generation record; explicit recovery required')
  old=self.released();peer=self.peer();admission,rows,gpu=self.strict_idle()
  require(sha(Path(self.c['peer']['root'])/'configs/admission.json')==self.c['peer']['admission_sha256'],'peer admission changed since root binding')
  write_new(self.attempt/'precheck.json',{'old_release':old,'peer':peer,'admission':admission,'compute':rows,'gpu':gpu})
  # Mutable admission only; producer files remain sealed.
  self.service.write_json(ROOT/'configs/admission.json',admission)
  self.logged('preflight',['python3','scripts/preflight.py','--live'],180)
 def launch_service_only(self):
  self.logged('service_only',['python3','-u','scripts/launch_remote.py','--service-only'],240)
  self.launched_owner=owner_from_startup_log((self.attempt/'service_only.log').read_text())
 def ready_owner(self):
  owner=read(ROOT/'processes/service.json');require(owner==self.launched_owner,'service registry changed from this launch child');self.service.assert_owned(owner)
  gate=read(ROOT/'processes/cuda_gate_ready.json')
  validate_gate(gate,owner,self.service.external_identity(owner['pid']),sha(ROOT/'scripts/compatibility_bootstrap.py'))
  self.owner=owner;self.gate=gate;write_new(self.attempt/'new_owner_ready.json',{'owner':owner,'gate':gate});return owner,gate
 def register_peer(self,owner):
  self.peer();path=Path(self.c['peer']['root'])/'configs/admission.json'
  require(sha(path)==self.c['peer']['admission_sha256'],'peer admission changed before registration')
  old=read(path);new=next_peer_admission(old,owner,self.service.external_identity(owner['pid']))
  write_new(self.attempt/'peer_admission_before.json',old)
  require(sha(path)==self.c['peer']['admission_sha256'],'peer concurrent mutation; abort')
  self.service.write_json(path,new);require(read(path)==new,'peer registration readback failed')
  self.peer_after=new;write_new(self.attempt/'peer_admission_after.json',new)
 def recheck_before_go(self,owner,gate):
  self.released();self.peer();self.service.assert_owned(owner)
  require(read(ROOT/'processes/service.json')==owner,'R43 service registry changed before go')
  require(read(Path(self.c['peer']['root'])/'configs/admission.json')==self.peer_after,'peer admission changed before go')
  validate_gate(read(ROOT/'processes/cuda_gate_ready.json'),owner,self.service.external_identity(owner['pid']),sha(ROOT/'scripts/compatibility_bootstrap.py'))
  self.strict_idle() # R43 is still before CUDA; target card must remain empty.
 def go(self,gate):
  write_new(ROOT/'processes/cuda_gate_go.json',gate)
  write_new(self.attempt/'go_written.json',{'gate':gate,'unix':time.time()})
 def wait_http(self,owner):
  deadline=time.monotonic()+300;last=None
  while time.monotonic()<deadline:
   self.service.assert_owned(owner)
   try:
    with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/object_info/H3TemporalRouter',timeout=2) as f:info=json.load(f)
    require('H3TemporalRouter' in info,'router node missing')
    with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/object_info/H3X0Readout',timeout=2) as f:info=json.load(f)
    require('H3X0Readout' in info,'readout node missing')
    write_new(self.attempt/'http_ready.json',{'pid':owner['pid'],'unix':time.time()});return
   except (OSError,ValueError) as exc:last=str(exc);time.sleep(1)
  raise TimeoutError('R43 HTTP readiness timeout: '+str(last))
 def start_controller(self,owner):
  self.peer();self.service.assert_owned(owner)
  require(read(Path(self.c['peer']['root'])/'configs/admission.json')==self.peer_after,'peer registration changed before controller')
  self.logged('controller',['python3','-u','scripts/start_controller.py','--pid',str(owner['pid']),'--start-ticks',str(owner['identity']['start_ticks'])],180)
  c=read(ROOT/'processes/controller.json');require(c['service_pid']==owner['pid'] and c['service_identity']==owner['identity'],'controller generation mismatch')
  write_new(self.attempt/'COMPLETE.json',{'service':owner,'controller':c,'status':'started','unix':time.time()})

def main():
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path);p.add_argument('--execute',action='store_true');p.add_argument('--plan',action='store_true');a=p.parse_args()
 if not a.execute:
  print(json.dumps({'prepared_only':True,'target':str(ROOT),'port':PORT,'gpu':GPU,'order':['R40 RUN_GATE + root release + exact cleanup/PID absent','R43 seal + current peer identity + GPU3 idle','service-only preCUDA ready','peer admission register and readback','root go','HTTP ready','exact controller'],'execute_requires':'root-reviewed config and explicit --execute'}));return
 require(a.config is not None,'--config is required');c=check_config(read(a.config))
 (ROOT/'audit').mkdir(exist_ok=True)
 with (ROOT/'audit/root_preCUDA_launch.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  attempt=ROOT/'audit'/('root_preCUDA_attempt_'+str(time.time_ns()));attempt.mkdir()
  write_new(attempt/'CONFIG.json',c);ops=RealOperations(c,attempt)
  try:
   owner=launch_sequence(ops);print(json.dumps({'status':'started','service_pid':owner['pid'],'audit':str(attempt)}))
  except BaseException as exc:
   write_new(attempt/'FAILURE.json',{'error':repr(exc),'owner':ops.owner,'unix':time.time()})
   # Never substitute the current registry for the exact child obtained above.
   if ops.owner is not None:
    try:ops.service.stop(expected_record=ops.owner)
    except BaseException as cleanup_error:write_new(attempt/'CLEANUP_FAILURE.json',{'error':repr(cleanup_error)})
   raise
if __name__=='__main__':main()
