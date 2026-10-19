"""Root scheduling required: r107_long_0174 source/native/forced sequential trackers on .41 GPU7, then CPU score."""
import fcntl,importlib.util,os,subprocess,sys,time,traceback
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from common import *
PEER=Path('/data4/researcher/h3_runs/timing_ive_long0174_guidance_r107_20261019');GPU='GPU-REDACTED';PY='/data3/researcher/ComfyUI/.venv/bin/python';C=R/'cases/r107_long_0174';BATCH=R/'audit/actual_r107_long_0174_attempt1';OUT=None;ROLE=None
spec=__import__('importlib.util',fromlist=['x']).spec_from_file_location('peer_cgroup',R/'audit/cgroup_memory.py');cg=__import__('importlib.util',fromlist=['x']).module_from_spec(spec);spec.loader.exec_module(cg)
def owner_check():
 owner=read(PEER/'processes/service.json');require(owner['pid']==1226044 and str(owner['identity']['start_ticks'])=='15372732' and owner['identity']['uid']==1004,'R107 release barrier generation differs')
 require(process_identity.snapshot(owner['pid']) is None,'R107 process remains or PID was reused; wait')
 require(owner['pid'] not in cuda_pids(),'R107 CUDA allocation remains')
 released=read(PEER/'processes/cleanup.json')
 require(released['pid']==owner['pid'] and released['process_absent'] is True and released['own_compute_absent'] is True,'R107 exact cleanup receipt pending')
 return None

def capacity():
 owner=owner_check();headroom=cg.snapshot();require(headroom['effective_headroom_bytes']>=12*1024**3,'effective preload cgroup headroom below12GiB');g=resource_check(GPU)
 known=identity(owner['pid']) if owner else None
 for row in g['processes']:
  if row['uid']==os.getuid():require(owner is not None and row['pid']==owner['pid'] and all(row[k]==v for k,v in known.items()),'unexpected own compute process')
 return {'gpu':g,'cgroup':headroom}

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
 require(not registered,'exclusive tracker never registers peer')
 return {'pid':child.pid,'returncode':child.returncode,'process_absent':True,'own_cuda_absent':True,'peer_removed':registered,'unix':time.time()}

def run_one():
 OUT.mkdir(parents=True,exist_ok=False);os.environ['CUDA_VISIBLE_DEVICES']=GPU;verify_seal();save(OUT/'PREFLIGHT.json',capacity());save(OUT/'R107_RELEASE_BARRIER.json',owner_check())
 argv=[PY,'-u',str(R/'scripts/track.py'),'--case','r107_long_0174','--role',ROLE,'--gpu-uuid',GPU];control=C/'controls'/ROLE;ready=None;registered=False;primary=None
 with (OUT/(ROLE+'.log')).open('xb') as log:child=subprocess.Popen(argv,cwd=R,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2'),stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 try:
  deadline=time.monotonic()+180
  while not(control/'ready.json').exists():require(child.poll() is None and time.monotonic()<deadline,'ready deadline or child exit');time.sleep(.2)
  ready=read(control/'ready.json');require(ready['identity']==identity(child.pid) and ready['identity']['pid']==child.pid and ready['gpu_uuid']==GPU and ready['CUDA_started'] is False and ready['input_manifest_sha256']==sha(C/'INPUTS.json') and ready['seal_sha256']==sha(R/'SEAL.json'),'exact ready identity/data mismatch')
  save(OUT/'CAPACITY_AT_GO.json',capacity());
  require(owner_check() is None,'exclusive tracker requires R107 released')
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
 require(sha(C/'INPUTS.json')=='af5f75f62fdfee9d7ceb1f027b167c2860263056f3cc621403f061d31e2c6ed9','authorized exact input manifest changed')
 require(read(C/'INPUTS.json')['valid_frames']==145,'authorized physical domain changed')
 for role in ['source','native','forced']:
  ROLE=role;OUT=BATCH/role;run_one()
 for role in ['native','forced']:
  result=subprocess.run([PY,str(R/'scripts/score.py'),'--case','r107_long_0174','--role',role],env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'),cwd=R,capture_output=True,text=True,timeout=600)
  (BATCH/(role+'_score.log')).write_text(result.stdout+'\n'+result.stderr);require(result.returncode==0,'CPU score failed '+role)
 save(BATCH/'COMPLETE.json',{'passed':True,'scores':{k:bound(C/'results'/(k+'.json')) for k in ['native','forced']},'all_three_trackers_released':True,'GPU_started_only':GPU,'authorized_case':'r107_long_0174','unix':time.time()})
 print('BATCH_COMPLETE',flush=True)
if __name__=='__main__':main()
