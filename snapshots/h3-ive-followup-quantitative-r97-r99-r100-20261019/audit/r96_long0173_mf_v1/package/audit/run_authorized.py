"""Root authorization: R96 long0173 source/native/forced sequential trackers on .41 GPU7, then CPU score."""
import fcntl,importlib.util,os,subprocess,sys,time,traceback
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from common import *
PEER=Path('/data4/researcher/h3_runs/timing_ive_native_screen_r96_20261018');GPU='GPU-REDACTED';PY='/data3/researcher/ComfyUI/.venv/bin/python';C=R/'cases/r96_long_0173';BATCH=R/'audit/actual_r96_long0173_attempt1';OUT=None;ROLE=None
spec=__import__('importlib.util',fromlist=['x']).spec_from_file_location('peer_cgroup',PEER/'scripts/cgroup_memory.py');cg=__import__('importlib.util',fromlist=['x']).module_from_spec(spec);spec.loader.exec_module(cg)
def owner_check():
 owner=read(PEER/'processes/service.json');require(owner['pid']==951112 and owner['identity']['start_ticks']=='10923395','R96 generation changed');current=process_identity.snapshot(owner['pid'])
 if current is None:
  require(owner['pid'] not in cuda_pids(),'R96 exit has NVML tail; wait for actual release');return None
 require(process_identity.service_record(current)==owner['identity'],'R96 exact service changed');return owner

def capacity():
 owner=owner_check();headroom=cg.snapshot();require(headroom['effective_headroom_bytes']>=8*1024**3,'effective cgroup headroom below8GiB');g=resource_check(GPU)
 known=identity(owner['pid']) if owner else None
 for row in g['processes']:
  if row['uid']==os.getuid():require(owner is not None and row['pid']==owner['pid'] and all(row[k]==v for k,v in known.items()),'unexpected own compute process')
 return {'gpu':g,'cgroup':headroom}

def peer_change(ready,add):
 path=PEER/'configs/admission.json';record={'pid':ready['identity']['pid'],'identity':{k:v for k,v in ready['identity'].items() if k!='pid'}}
 with (PEER/'configs/r96_own_metric_peer.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);before=path.read_bytes();d=json.loads(before);rows=d['permitted_compute_processes'];match=[x for x in rows if x['pid']==record['pid']]
  if add:
   require(owner_check() is not None,'R96 exited before peer registration; retry from fresh preflight');require(not match,'cannot replace existing peer');d['permitted_compute_processes']=rows+[record]
  else:
   require(match==[record],'exact peer entry changed');d['permitted_compute_processes']=[x for x in rows if x!=record]
  require(path.read_bytes()==before,'concurrent peer admission change');save(path,d);save(OUT/('PEER_REGISTERED.json' if add else 'PEER_REMOVED.json'),{'before':json.loads(before),'after':d,'owned_record':record})

def cuda_pids():
 return {int(x.strip()) for x in subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True,timeout=15).splitlines() if x.strip()}

def cleanup(child,ready,registered):
 if child.poll() is None:
  require(ready is None or identity(child.pid)==ready['identity'],'child generation changed before signal');child.terminate()
  try:child.wait(timeout=10)
  except subprocess.TimeoutExpired:
   require(ready is None or identity(child.pid)==ready['identity'],'child generation changed before kill');child.kill();child.wait(timeout=10)
 else:child.wait()
 deadline=time.monotonic()+30
 while child.pid in cuda_pids():require(time.monotonic()<deadline,'own NVML tail >30s');time.sleep(.5)
 require(identity(child.pid) is None,'child PID currently exists; inspect identity before removal')
 if registered:peer_change(ready,False)
 return {'pid':child.pid,'returncode':child.returncode,'process_absent':True,'own_cuda_absent':True,'peer_removed':registered,'unix':time.time()}

def run_one():
 OUT.mkdir(parents=True,exist_ok=False);os.environ['CUDA_VISIBLE_DEVICES']=GPU;verify_seal();save(OUT/'PREFLIGHT.json',capacity());save(OUT/'R96_OWNER.json',owner_check())
 argv=[PY,'-u',str(R/'scripts/track.py'),'--case','r96_long_0173','--role',ROLE,'--gpu-uuid',GPU];control=C/'controls'/ROLE;ready=None;registered=False;primary=None
 with (OUT/(ROLE+'.log')).open('xb') as log:child=subprocess.Popen(argv,cwd=R,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2'),stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 try:
  deadline=time.monotonic()+180
  while not(control/'ready.json').exists():require(child.poll() is None and time.monotonic()<deadline,'ready deadline or child exit');time.sleep(.2)
  ready=read(control/'ready.json');require(ready['identity']==identity(child.pid) and ready['identity']['pid']==child.pid and ready['gpu_uuid']==GPU and ready['CUDA_started'] is False and ready['input_manifest_sha256']==sha(C/'INPUTS.json') and ready['seal_sha256']==sha(R/'SEAL.json'),'exact ready identity/data mismatch')
  save(OUT/'CAPACITY_AT_GO.json',capacity());
  if owner_check() is not None:peer_change(ready,True);registered=True
  save(control/'go.json',ready);save(OUT/'GO.json',ready);print(json.dumps({'GO':True,'identity':ready['identity']}),flush=True)
  require(child.wait(timeout=600)==0,'tracker returned failure');d=read(C/'tracks'/ROLE/'REPORT.json');require(d['passed'] is True and d['pid']==child.pid and d['tracks_shape']==[1,145,100,2] and d['tracks_sha256']==sha(C/'tracks'/ROLE/'tracks.npz'),'actual tracker output invalid')
 except BaseException as e:
  primary=e
  try:save(OUT/'ERROR.json',{'error':repr(e),'traceback':traceback.format_exc()})
  except Exception:pass
 finally:
  try:save(OUT/'RELEASED.json',cleanup(child,ready,registered))
  except BaseException as e:
   if primary:raise RuntimeError('primary '+repr(primary)+'; cleanup '+repr(e)) from primary
   raise
 if primary:raise primary
 save(OUT/'COMPLETE.json',{'passed':True,'tracker':bound(C/'tracks'/ROLE/'REPORT.json'),'own_process_and_cuda_released':True,'GPU_started_only':GPU,'unix':time.time()});print('TRACK_COMPLETE '+ROLE,flush=True)
def main():
 global OUT,ROLE
 BATCH.mkdir(parents=True,exist_ok=False)
 require(sha(C/'INPUTS.json')=='a4ad92aac5693d9cd9bec4b4f41dffe71e340a32445e17b396b00dfb774f8e98','authorized exact input manifest changed')
 require(read(C/'INPUTS.json')['valid_frames']==145,'authorized physical domain changed')
 for role in ['source','native','forced']:
  ROLE=role;OUT=BATCH/role;run_one()
 for role in ['native','forced']:
  result=subprocess.run([PY,str(R/'scripts/score.py'),'--case','r96_long_0173','--role',role],env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'),cwd=R,capture_output=True,text=True,timeout=600)
  (BATCH/(role+'_score.log')).write_text(result.stdout+'\n'+result.stderr);require(result.returncode==0,'CPU score failed '+role)
 save(BATCH/'COMPLETE.json',{'passed':True,'scores':{k:bound(C/'results'/(k+'.json')) for k in ['native','forced']},'all_three_trackers_released':True,'GPU_started_only':GPU,'authorized_case':'r96_long_0173','unix':time.time()})
 print('BATCH_COMPLETE',flush=True)
if __name__=='__main__':main()
