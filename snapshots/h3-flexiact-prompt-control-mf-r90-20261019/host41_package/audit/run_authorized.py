"""Serial official FlexiAct trackers under the approved raw-memory short-task policy."""
from pathlib import Path
import os,sys,subprocess,time,traceback
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from common import read,save,sha,load,require,bound,verify_runtime
identity=load('r90_proc_identity',R/'scripts/process_identity.py');cg=load('r90_cgroup',R/'audit/cgroup_memory.py');resources=load('r90_resource',R/'scripts/track_shared.py');capacity_module=load('r90_capacity',R/'scripts/mf_capacity.py')
GPU='GPU-REDACTED';PY='/data3/researcher/ComfyUI/.venv/bin/python';BATCH=R/'audit/actual_tracking_capacity4';OUT=None

def process_record(pid):return identity.hashed_record(identity.snapshot(pid)) if identity.snapshot(pid) else None

def cuda_pids():return {int(x.split(',')[0].strip()) for x in subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'],text=True).splitlines() if x.strip()}

def capacity():
 c=capacity_module.check(12);g=resources.resource_check(GPU)
 require(not any(x['uid']==os.getuid() for x in g['processes']),'unexpected own CUDA process; wait for peer coordination')
 return {'cgroup':c,'gpu':g}

def oom_check():
 before=read(BATCH/'OOM_BASE.json');after=cg.snapshot();delta=cg.delta(after,before)
 require(not any(x['counter_reset_detected'] or any(x['events_delta'].get(k,0)>0 for k in ['oom','oom_kill','oom_group_kill']) for x in delta['paths'].values()),'new OOM or counter reset; halt subsequent submissions')
 save(OUT/'OOM_DELTA.json',delta)

def cleanup(child,ready):
 if child.poll() is None:
  require(ready is None or process_record(child.pid)==ready['identity'],'PID generation changed')
  child.terminate()
  try:child.wait(timeout=10)
  except subprocess.TimeoutExpired:
   require(ready is None or process_record(child.pid)==ready['identity'],'PID generation changed before kill');child.kill();child.wait(timeout=10)
 else:child.wait()
 deadline=time.monotonic()+30
 while child.pid in cuda_pids():require(time.monotonic()<deadline,'own NVML tail timeout');time.sleep(.5)
 require(not Path('/proc',str(child.pid)).exists(),'own PID remains')
 return {'pid':child.pid,'returncode':child.returncode,'process_absent':True,'own_cuda_absent':True,'unix':time.time()}

def telemetry(child):
 samples=[];deadline=time.monotonic()+600
 while child.poll() is None:
  require(time.monotonic()<deadline,'tracker deadline')
  item={'unix':time.time()}
  try:
   item['cgroup']=cg.snapshot();status=Path('/proc',str(child.pid),'status').read_text();item['process_memory']={x.split(':',1)[0]:x.split(':',1)[1].strip() for x in status.splitlines() if x.startswith(('VmRSS:','VmHWM:','RssAnon:','RssFile:'))}
  except OSError as exc:item['error']=repr(exc)
  samples.append(item);time.sleep(.25)
 child.wait();save(OUT/'RESOURCE_OBSERVATIONS.json',{'samples':samples,'final_snapshot':cg.snapshot(),'returncode':child.returncode})

def main():
 global OUT
 verify_runtime();BATCH.mkdir(parents=True,exist_ok=False);save(BATCH/'OOM_BASE.json',cg.snapshot());os.environ['CUDA_VISIBLE_DEVICES']=GPU
 for method in ['reference','old_native','new_native']:
  OUT=BATCH/method;OUT.mkdir();oom_check();save(OUT/'PREFLIGHT.json',capacity())
  plan=subprocess.run([PY,str(R/'scripts/tracking_plan.py'),'--method',method,'--gpu-uuid',GPU],capture_output=True,text=True,check=True);argv=read_plan=__import__('json').loads(plan.stdout)['argv'];control=Path(argv[argv.index('--control')+1]);output=Path(argv[argv.index('--output')+1]);ready=None;error=None
  with (OUT/'tracker.log').open('xb') as log:child=subprocess.Popen(argv,cwd=R,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
  try:
   deadline=time.monotonic()+180
   while not(control/'ready.json').exists():require(child.poll() is None and time.monotonic()<deadline,'ready failure');time.sleep(.2)
   ready=read(control/'ready.json');require(ready['pid']==child.pid and ready['identity']==process_record(child.pid) and ready['gpu_uuid']==GPU and ready['CUDA_started'] is False and ready['consumer_freeze_sha256']==sha(R/'CONSUMER_FREEZE.json'),'ready mismatch')
   save(OUT/'CAPACITY_AT_GO.json',capacity());save(control/'go.json',ready);save(OUT/'GO.json',ready);print('GO '+method,flush=True);telemetry(child);oom_check();require(child.returncode==0,'tracker failed');rep=read(output/'REPORT.json');require(rep['passed'] and rep['pid']==child.pid and rep['tracks_shape']==[3025,49,2] and rep['nonfinite_track_values']==0 and rep['tracks_sha256']==sha(output/'tracks.pt'),'track output differs')
  except BaseException as exc:error=exc;save(OUT/'ERROR.json',{'error':repr(exc),'traceback':traceback.format_exc()})
  finally:save(OUT/'RELEASED.json',cleanup(child,ready))
  if error:raise error
  save(OUT/'COMPLETE.json',{'passed':True,'report':bound(output/'REPORT.json')});print('TRACK_COMPLETE '+method,flush=True)
 for method in ['old_native','new_native']:
  q=subprocess.run([PY,str(R/'scripts/score_one.py'),'--method',method],cwd=R,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,timeout=600);(BATCH/(method+'_score.log')).write_text(q.stdout+'\n'+q.stderr);require(q.returncode==0,'CPU score failed')
 save(BATCH/'COMPLETE.json',{'passed':True,'scores':{k:bound(R/'scores'/k/'SCORE.json') for k in ['old_native','new_native']},'all_trackers_released':True,'comparison_kind':'prompt_control','guidance_used':False,'unix':time.time()});print('BATCH_COMPLETE',flush=True)
if __name__=='__main__':main()
