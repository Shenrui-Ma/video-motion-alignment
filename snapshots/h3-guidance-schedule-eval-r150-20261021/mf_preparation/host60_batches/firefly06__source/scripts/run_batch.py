"""One short tracker at a time, exact lifecycle and reviewed cache-aware admission."""
import argparse,subprocess,sys,time,signal,traceback
from common import *
import capacity,process_identity

def oom_delta(before,after):
 value=capacity.oom_delta(before,after);assert value['passed'],'new allocation/OOM event';return value

def cuda_pids():return {int(x.strip())for x in subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True,timeout=15).splitlines()if x.strip()}
def cleanup(child,bound_id):
 if child.poll()is None:
  assert identity(child.pid)==bound_id;child.terminate()
  try:child.wait(timeout=10)
  except subprocess.TimeoutExpired:
   assert identity(child.pid)==bound_id;child.kill();child.wait(timeout=10)
 else:child.wait()
 deadline=time.monotonic()+30
 while child.pid in cuda_pids():assert time.monotonic()<deadline;time.sleep(.5)
 assert not Path('/proc',str(child.pid)).exists()
 return dict(passed=True,identity=bound_id,returncode=child.returncode,process_absent=True,CUDA_absent=True,unix=time.time())

def main():
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--gpu',required=True);p.add_argument('--review',required=True);p.add_argument('--maximum-new-trackers',type=int);a=p.parse_args();assert a.attempt.replace('_','').isalnum();assert os.getuid()==1015;verify_seal();review=read(a.review);assert review['passed']and review['GPU_execution_authorized']and review['seal_sha256']==sha(ROOT/'SEAL.json')and review['gpu']==a.gpu;os.environ['CUDA_VISIBLE_DEVICES']=a.gpu
 assert review['execution_scope']=='host60_single_tracker_only';assert read(ROOT/'configs/SOURCE_INPUTS_VERIFIED.json')['passed'];assert not read(ROOT/'configs/RUNTIME.json')['peer_roots']
 root=ROOT/'audit'/a.attempt;assert not root.exists();root.mkdir(parents=True);save(root/'STARTED.json',dict(identity=identity(os.getpid()),review=bound(a.review),seal=bound(ROOT/'SEAL.json'),unix=time.time()));baseline=capacity.snapshot();save(root/'OOM_BASE.json',baseline)
 def stop(n,f):raise KeyboardInterrupt('signal '+str(n))
 signal.signal(signal.SIGTERM,stop);count=0
 for job in read(ROOT/'configs/PLAN.json')['jobs']:
  key,role=job['case'],job['role'];c=case(key);state=ROOT/'state'/key/(role+'.json')
  if state.exists():
   folder_for(c,role)
   if role!='source'and not(ROOT/'results'/key/(role+'.json')).exists():
    subprocess.run([sys.executable,str(ROOT/'scripts/score.py'),'--case',key,'--role',role],env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'),check=True,timeout=600)
   continue
  if a.maximum_new_trackers is not None and count>=a.maximum_new_trackers:break
  snap=capacity.snapshot();delta=oom_delta(baseline,snap);entry=resource_check(a.gpu);logdir=root/'jobs'/key/role;logdir.mkdir(parents=True);save(logdir/'PREFLIGHT.json',dict(resource=entry,oom_delta=delta));child=None;ident=None;samples=[];error=None;registered_peers=[]
  command=[sys.executable,str(ROOT/'scripts/track.py'),'--case',key,'--role',role,'--attempt',a.attempt,'--gpu',a.gpu]
  try:
   with(logdir/'tracker.log').open('xb')as log:child=subprocess.Popen(command,cwd=ROOT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
   row=process_identity.bind_or_reap(child,command);ident=dict(pid=child.pid,**process_identity.hashed_record(row));save(logdir/'LAUNCHED.json',dict(identity=ident,command=command));control=root/'controls'/key/role;deadline=time.monotonic()+180
   while not(control/'ready.json').exists():assert child.poll()is None and time.monotonic()<deadline,'ready timeout or exit';time.sleep(.2)
   ready=read(control/'ready.json');assert ready['identity']==ident and ready['CUDA_started']is False and ready['input_sha256']==sha(c/'INPUTS.json')and ready['seal_sha256']==sha(ROOT/'SEAL.json')
   registered_peers=register_peer(ident);fresh=capacity.snapshot();oom_delta(baseline,fresh);save(logdir/'AT_GO.json',resource_check(a.gpu,child.pid));save(control/'go.json',ready);print('GO',key,role,flush=True);deadline=time.monotonic()+600
   while child.poll()is None:
    assert time.monotonic()<deadline,'tracker deadline';v=capacity.snapshot();delta=oom_delta(baseline,v);check=capacity.assess(v,'running');assert check['passed'],check['failures'];obs=dict(unix=time.time(),capacity=v)
    try:obs['process_memory']={line.split(':',1)[0]:line.split(':',1)[1].strip()for line in Path('/proc',str(child.pid),'status').read_text().splitlines()if line.startswith(('VmHWM:','VmRSS:','RssAnon:','RssFile:'))}
    except FileNotFoundError:obs['process_exited_during_read']=True
    samples.append(obs);time.sleep(.5)
   child.wait();assert child.returncode==0,'tracker failed';folder=root/'tracks'/key/role;r=read(folder/'REPORT.json');assert r['passed'];ext='tracks.pt'if read(c/'INPUTS.json')['benchmark']=='FlexiAct'else'tracks.npz';assert sha(folder/ext)==r['tracks_sha256']
  except BaseException as exc:error=exc;save(logdir/'ERROR.json',dict(error=repr(exc),traceback=traceback.format_exc()))
  finally:
   if ident is not None:
    released=cleanup(child,ident);unregister_peer(ident,registered_peers);released['peer_registrations_removed']=True;save(logdir/'RELEASED.json',released)
   save(logdir/'RESOURCE_OBSERVATIONS.json',dict(samples=samples))
  if error is not None:raise error
  save(state,dict(folder=str(folder.relative_to(ROOT)),report_sha256=sha(folder/'REPORT.json'),release=bound(logdir/'RELEASED.json')));count+=1;print('TRACK_COMPLETE',key,role,flush=True)
  if role!='source':
   result=subprocess.run([sys.executable,str(ROOT/'scripts/score.py'),'--case',key,'--role',role],env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,timeout=600);(logdir/'score.log').write_text(result.stdout+'\n'+result.stderr);assert result.returncode==0,'CPU score failed'
 remaining=[x for x in read(ROOT/'configs/PLAN.json')['jobs']if not(ROOT/'state'/x['case']/(x['role']+'.json')).exists()];save(root/'COMPLETE.json',dict(passed=True,new_trackers=count,remaining=remaining,all_spawned_trackers_released=True,unix=time.time()));print('BATCH_COMPLETE',count,'remaining',len(remaining),flush=True)
if __name__=='__main__':main()
