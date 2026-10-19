"""Root-authorized R101 actual guided tracker, GPU7 only. No inference service mutation."""
from pathlib import Path
import sys,os,json,time,subprocess,hashlib,importlib.util,traceback
R=Path(__file__).resolve().parents[1];PEER=Path('/data4/researcher/h3_runs/timing_ive_long0174_guidance_r107_20261019');GPU='GPU-REDACTED';PY='/data3/researcher/ComfyUI/.venv/bin/python';OUT=R/'audit/actual_guided_tracking_attempt1'
sys.path.insert(0,str(R/'scripts'));from common import read,save,sha,load,require,bound
identity=load('r101_peer_identity',PEER/'scripts/process_identity.py');cg=load('r101_peer_cgroup',PEER/'scripts/cgroup_memory.py');resources=load('r101_resource_guard',R/'scripts/track_shared.py')
def atomic(p,d):
 p=Path(p);q=p.with_suffix(p.suffix+'.r101.tmp');save(q,d);q.replace(p)
def owner_check():
 owner=read(PEER/'processes/service.json');require(owner['pid']==1226044 and str(owner['identity']['start_ticks'])=='15372732' and owner['identity']['uid']==1004,'R107 exact barrier generation changed')
 require(identity.snapshot(owner['pid']) is None and owner['pid'] not in cuda_pids(),'R107 service/CUDA remains; wait for release')
 release=read(PEER/'processes/cleanup.json');require(release['pid']==owner['pid'] and release['process_absent'] is True and release['own_compute_absent'] is True,'R107 exact cleanup pending')
 return {'owner':owner,'release':release}
def capacity():
 value=cg.snapshot();require(value['effective_headroom_bytes']>=8*1024**3,'cgroup headroom below8GiB');gpu=resources.resource_check(GPU);require(not any(p['uid']==os.getuid() for p in gpu['processes']),'exclusive MF slot has another own CUDA process');return {'cgroup':value,'gpu':gpu}
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
 return {'pid':child.pid,'returncode':child.returncode,'process_absent':True,'own_cuda_absent':True,'peer_registration_required':False,'unix':time.time()}
def main():
 require(sha(R/'CONSUMER_FREEZE.json')=='a76bd2b03c3ead23186aa01c2fbfdc6f6eeb4b83d7c894a80479e24f70ee9850','actual guided freeze differs')
 require(sha(R/'prepared/guided/TRACK_INPUTS.json')=='78a0a09b95b053ed0c27cfff28a5203b124671ac25038ce8fbfb3e4946e207c2','actual guided tracking input differs')
 OUT.mkdir(parents=True,exist_ok=False);os.environ['CUDA_VISIBLE_DEVICES']=GPU
 owner=owner_check();save(OUT/'R107_RELEASE_BARRIER.json',owner);save(OUT/'PREFLIGHT_CAPACITY.json',capacity());done=[]
 for method in ['guided']:
  pre=capacity();save(OUT/(method+'_capacity_before.json'),pre)
  plan=subprocess.run([PY,str(R/'scripts/tracking_plan.py'),'--gpu-uuid',GPU],cwd=R,check=True,capture_output=True,text=True,timeout=120);argv=json.loads(plan.stdout)['argv'];control=Path(argv[argv.index('--control')+1]);output=Path(argv[argv.index('--output')+1]);ready=None;registered=False;error=None
  with (OUT/(method+'.log')).open('xb') as log:child=subprocess.Popen(argv,cwd=R,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
  try:
   deadline=time.monotonic()+120
   while not (control/'ready.json').exists():require(child.poll() is None and time.monotonic()<deadline,'tracker pre-CUDA ready failed');time.sleep(.2)
   ready=read(control/'ready.json');require(ready['pid']==child.pid and ready['identity']==identity.hashed_record(identity.snapshot(child.pid)) and ready['gpu_uuid']==GPU and ready['CUDA_started'] is False and ready['consumer_freeze_sha256']==sha(R/'CONSUMER_FREEZE.json') and ready['input_manifest']['sha256']==sha(R/'prepared/guided/TRACK_INPUTS.json'),'exact ready differs')
   owner_check();save(OUT/(method+'_capacity_at_go.json'),capacity());atomic(control/'go.json',ready);save(OUT/(method+'_GO.json'),ready)
   require(child.wait(timeout=600)==0,'tracker returned failure');report=read(output/'REPORT.json');require(report['passed'] and report['pid']==child.pid and report['tracks_shape']==[3025,49,2] and report['nonfinite_track_values']==0 and sha(output/'tracks.pt')==report['tracks_sha256'],'actual track validation failed')
   done.append({'method':method,'report':bound(output/'REPORT.json'),'wall_seconds':report['wall_seconds'],'peak_reserved_bytes':report['peak_reserved_bytes']})
  except BaseException as exc:error=exc;save(OUT/(method+'_ERROR.json'),{'error':repr(exc),'traceback':traceback.format_exc()})
  finally:
   released=cleanup(child,ready);save(OUT/(method+'_RELEASED.json'),released)
  if error:raise error
  save(OUT/'PROGRESS.json',{'completed':done});print(json.dumps(done[-1]),flush=True)
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1');score=subprocess.run([PY,str(R/'scripts/score_guided.py')],cwd=R,env=env,capture_output=True,text=True,timeout=600);(OUT/'score.log').write_text(score.stdout+'\n'+score.stderr);require(score.returncode==0,'CPU score failed')
 save(OUT/'COMPLETE.json',{'passed':True,'completed':done,'score':bound(R/'scores/guided/SCORE.json'),'GPU_started_only':GPU,'all_own_children_released':True,'unix':time.time()});print('COMPLETE',flush=True)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true',required=True);p.parse_args();main()
