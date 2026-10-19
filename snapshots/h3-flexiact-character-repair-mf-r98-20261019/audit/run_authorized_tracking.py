"""Root-authorized R98 source/Native tracker batch, GPU7 only. No inference service mutation."""
from pathlib import Path
import sys,os,json,time,subprocess,hashlib,importlib.util,traceback
R=Path(__file__).resolve().parents[1];PEER=Path('/data4/researcher/h3_runs/timing_ive_native_screen_r96_20261018');GPU='GPU-REDACTED';PY='/data3/researcher/ComfyUI/.venv/bin/python';OUT=R/'audit/actual_tracking_attempt1'
sys.path.insert(0,str(R/'scripts'));from common import read,save,sha,load,require,bound
identity=load('r98_peer_identity',PEER/'scripts/process_identity.py');cg=load('r98_peer_cgroup',PEER/'scripts/cgroup_memory.py');resources=load('r98_resource_guard',R/'scripts/track_shared.py')
def atomic(p,d):
 p=Path(p);q=p.with_suffix(p.suffix+'.r98.tmp');save(q,d);q.replace(p)
def owner_check():
 owner=read(PEER/'processes/service.json');require(owner['pid']==951112 and owner['identity']['start_ticks']=='10923395','R96 service generation changed');require(identity.service_record(identity.snapshot(owner['pid']))==owner['identity'],'R96 current identity differs');return owner
def capacity():
 value=cg.snapshot();require(value['effective_headroom_bytes']>=8*1024**3,'cgroup headroom below8GiB');gpu=resources.resource_check(GPU);return {'cgroup':value,'gpu':gpu}
def edit_peer(child,ready,add):
 p=PEER/'configs/admission.json';before=read(p);rows=before['permitted_compute_processes'];record={'pid':child.pid,'identity':ready['identity']}
 if add:
  require(not any(x['pid']==child.pid for x in rows),'child already admitted');owner_check();before['permitted_compute_processes']=rows+[record]
 else:before['permitted_compute_processes']=[x for x in rows if x!=record]
 atomic(p,before)
def cuda_pids():
 raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'],text=True,timeout=10);return {int(x.split(',')[0]) for x in raw.splitlines() if x.strip()}
def cleanup(child,ready):
 if child.poll() is None:
  require(ready is None or identity.hashed_record(identity.snapshot(child.pid))==ready['identity'],'child generation changed; refuse signal')
  child.terminate()
  try:child.wait(timeout=10)
  except subprocess.TimeoutExpired:
   require(ready is None or identity.hashed_record(identity.snapshot(child.pid))==ready['identity'],'child changed before kill');child.kill();child.wait(timeout=10)
 else:child.wait()
 deadline=time.monotonic()+30
 while child.pid in cuda_pids():
  require(time.monotonic()<deadline,'own NVML PID lingered >30s');time.sleep(.5)
 require(not Path('/proc',str(child.pid)).exists(),'original child still in proc')
 if ready:edit_peer(child,ready,False)
 return {'pid':child.pid,'returncode':child.returncode,'process_absent':True,'own_cuda_absent':True,'peer_removed':True,'unix':time.time()}
def main():
 OUT.mkdir(parents=True,exist_ok=False);os.environ['CUDA_VISIBLE_DEVICES']=GPU
 owner=owner_check();save(OUT/'R96_OWNER.json',owner);save(OUT/'PREFLIGHT_CAPACITY.json',capacity());done=[]
 for method in ['reference','native']:
  pre=capacity();save(OUT/(method+'_capacity_before.json'),pre)
  plan=subprocess.run([PY,str(R/'scripts/tracking_plan.py'),'--method',method,'--gpu-uuid',GPU],cwd=R,check=True,capture_output=True,text=True,timeout=120);argv=json.loads(plan.stdout)['argv'];control=Path(argv[argv.index('--control')+1]);output=Path(argv[argv.index('--output')+1]);ready=None;registered=False;error=None
  with (OUT/(method+'.log')).open('xb') as log:child=subprocess.Popen(argv,cwd=R,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
  try:
   deadline=time.monotonic()+120
   while not (control/'ready.json').exists():require(child.poll() is None and time.monotonic()<deadline,'tracker pre-CUDA ready failed');time.sleep(.2)
   ready=read(control/'ready.json');require(ready['pid']==child.pid and ready['identity']==identity.hashed_record(identity.snapshot(child.pid)) and ready['gpu_uuid']==GPU and ready['CUDA_started'] is False,'exact ready differs')
   owner_check();save(OUT/(method+'_capacity_at_go.json'),capacity());edit_peer(child,ready,True);registered=True;atomic(control/'go.json',ready);save(OUT/(method+'_GO.json'),ready)
   require(child.wait(timeout=600)==0,'tracker returned failure');report=read(output/'REPORT.json');require(report['passed'] and report['pid']==child.pid and report['tracks_shape']==[3025,49,2] and report['nonfinite_track_values']==0 and sha(output/'tracks.pt')==report['tracks_sha256'],'actual track validation failed')
   done.append({'method':method,'report':bound(output/'REPORT.json'),'wall_seconds':report['wall_seconds'],'peak_reserved_bytes':report['peak_reserved_bytes']})
  except BaseException as exc:error=exc;save(OUT/(method+'_ERROR.json'),{'error':repr(exc),'traceback':traceback.format_exc()})
  finally:
   released=cleanup(child,ready if registered else None);save(OUT/(method+'_RELEASED.json'),released)
  if error:raise error
  save(OUT/'PROGRESS.json',{'completed':done});print(json.dumps(done[-1]),flush=True)
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1');score=subprocess.run([PY,str(R/'scripts/score_one.py'),'--method','native'],cwd=R,env=env,capture_output=True,text=True,timeout=600);(OUT/'score.log').write_text(score.stdout+'\n'+score.stderr);require(score.returncode==0,'CPU score failed')
 save(OUT/'COMPLETE.json',{'passed':True,'completed':done,'score':bound(R/'scores/native/SCORE.json'),'GPU_started_only':GPU,'all_own_children_released':True,'unix':time.time()});print('COMPLETE',flush=True)
if __name__=='__main__':main()
