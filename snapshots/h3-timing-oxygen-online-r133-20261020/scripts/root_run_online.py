"""Explicit root-only single online trial; exact lifecycle and bounded read-only waits."""
import argparse,fcntl,json,os,signal,subprocess,time,urllib.error
from pathlib import Path
import service,job,launch_remote
from r86_contract import ROOT,RUN,read,sha,require
from execution_gate import atomic,approval
from observer_import import t

def read_transport_error(error):
 return isinstance(error,(TimeoutError,ConnectionError,urllib.error.URLError))

def completed(owner):
 service.assert_owned(owner)
 try:r=job.status(RUN)
 except Exception as e:
  if not read_transport_error(e):raise
  return False,{'status':'UNKNOWN','error':repr(e)}
 v=r.get('status');v=v.get('status_str') if isinstance(v,dict) else v
 if v=='success':return True,r
 if v in ('error','failed','cancelled','submission_uncertain'):raise RuntimeError('actual job failed: '+repr(r))
 return False,r

def wait_completed(owner,timeout,log,*,clock=time.monotonic,sleep=time.sleep,check=completed):
 start=clock()
 while clock()-start<timeout:
  done,row=check(owner)
  with Path(log).open('a') as f:f.write(json.dumps({'unix':time.time(),'elapsed':clock()-start,'observation':row})+'\n')
  if done:return row
  sleep(min(20,max(0,timeout-(clock()-start))))
 raise TimeoutError('single online job deadline expired')

def cleanup_observers(root=ROOT,timeout=60):
 """No guessed PIDs: only exact identities registered under this attempt root."""
 root=Path(root);entries=[]
 for path in (root/'audit/observations').glob('*/*.process.json'):
  row=read(path);entry={k:row[k] for k in ('pid','uid','start_ticks','cmdline_sha256')}
  require(entry['uid']==os.getuid(),'observer record belongs to different UID')
  if t.alive(entry):
   require(os.getpgid(entry['pid'])==entry['pid'],'observer is not isolated group')
   os.killpg(entry['pid'],signal.SIGTERM)
  entries.append(entry)
 deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  alive=[e for e in entries if t.alive(e)];rows=service.compute_processes();remaining=[r for r in rows if any(r['pid']==e['pid'] for e in entries)]
  if not alive and not remaining:return {'registered_children':entries,'all_exact_generations_absent':True,'all_registered_CUDA_pids_absent':True}
  time.sleep(.5)
 raise TimeoutError('registered observer children have not released within bound')

def run(attempt):
 require(str(ROOT)==service.RUNTIME['remote_root'],'root execution requires remote package')
 require(attempt.replace('_','').isalnum() and attempt.startswith('root_'),'invalid attempt')
 controller_lock=(ROOT/'processes/root_controller.lock').open('a');fcntl.flock(controller_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 d=ROOT/'audit'/attempt;d.mkdir(exist_ok=False);owner=None;primary=None;clean=None
 os.environ['H3_ROOT_ATTEMPT_TOKEN']=attempt
 try:
  approval();t.bindings(external=True)
  admission=t.admission_document(approved=True);t.validate_preserved_registry(admission['permitted_compute_processes'])
  service.wait_admission_snapshot(admission,{'queue_running':[],'queue_pending':[]})
  # Decoder reservation is a trial capacity check, not a claim of measured demand.
  t.standalone_decoder_admission(t.DECODER_UUID)
  wrapper={'pid':os.getpid(),'identity':service.current_identity(os.getpid()),'role':'online_root_controller','attempt':attempt}
  atomic(ROOT/'processes/controller.json',wrapper)
  owner,ready=launch_remote.launch()
  watchdog_command=['python3','-u',str(ROOT/'scripts/lease_watchdog.py'),'--expected-pid',str(owner['pid']),'--expected-start',str(owner['identity']['start_ticks'])]
  with (ROOT/'logs/watchdog.log').open('ab',buffering=0) as log:
   watchdog=subprocess.Popen(watchdog_command,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
  watchdog_identity=service.bind_child(watchdog,watchdog_command)
  atomic(ROOT/'processes/watchdog.json',{'pid':watchdog.pid,'identity':watchdog_identity,'role':'watchdog','service_pid':owner['pid'],'service_identity':owner['identity']})
  atomic(d/'STARTED.json',{'service':owner,'root_controller':wrapper,'ready':ready,'protocol_sha256':sha(ROOT/'configs/protocol.json')})
  require(t.admission_document(approved=True)==admission,'admission changed before root GO')
  service.assert_owned(owner)
  import cgroup_memory
  atomic(d/'CGROUP_PRE_GO.json',cgroup_memory.check(ROOT))
  atomic(ROOT/'processes/cuda_gate_go.json',ready)
  deadline=time.monotonic()+1200
  while True:
   service.assert_owned(owner)
   try:
    with __import__('urllib.request',fromlist=['urlopen']).urlopen(job.URL+'/system_stats',timeout=15) as f:json.load(f)
    with __import__('urllib.request',fromlist=['urlopen']).urlopen(job.URL+'/object_info',timeout=15) as f:nodes=json.load(f)
    require('H3AutomaticWindowRouter' in nodes,'automatic router node missing from actual service')
    break
   except Exception as e:
    if not read_transport_error(e):raise
    if time.monotonic()>deadline:raise TimeoutError('HTTP ready deadline') from e
    time.sleep(5)
  # POST is issued once. An uncertain submission is preserved and never resent.
  submitted=job.submit(RUN,expected_owner=owner);atomic(d/'SUBMITTED.json',submitted)
  wait_completed(owner,read(ROOT/'configs/scientific_contract.json')['continuous']['job_timeout_seconds'],d/'STATUS.jsonl')
  atomic(d/'ACTUAL_SUCCESS.json',{'run_id':RUN,'service':owner,'history_sha256':sha(ROOT/'logs'/(RUN+'_history.json'))})
 except BaseException as error:
  primary=error
  try:atomic(d/'FAILURE.json',{'error':repr(error),'service':owner,'unix':time.time()})
  except BaseException as receipt:
   if hasattr(error,'add_note'):error.add_note('failure receipt: '+repr(receipt))
 finally:
  errors=[];children=None
  try:
   if owner is not None:clean=service.stop(expected_record=owner)
  except BaseException as error:errors.append(error)
  try:children=cleanup_observers()
  except BaseException as error:errors.append(error)
  if not errors:
   try:atomic(d/'ROOT_EXIT_RECEIPT.json',{'passed':True,'service':owner,'service_cleanup':clean,'observer_children':children,'unix':time.time()})
   except BaseException as error:errors.append(error)
  if errors:
   try:atomic(d/'CLEANUP_FAILURE.json',{'errors':[repr(x) for x in errors],'primary':repr(primary),'service_cleanup':clean,'observer_children':children})
   except BaseException:pass
   if primary is None:primary=errors[0]
   elif hasattr(primary,'add_note'):primary.add_note('cleanup: '+repr(errors))

 if primary is not None:raise primary
 subprocess.run([service.PYTHON,str(ROOT/'analysis/postrun/verify_online.py'),'--root-exit',str(d/'ROOT_EXIT_RECEIPT.json')],check=True,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''))
 atomic(d/'COMPLETE_REVIEW_HOLD.json',{'passed':True,'run_id':RUN,'gate_sha256':sha(ROOT/'analysis/postrun/ONLINE_RUNTIME_GATE.json'),'no_followup_submission':True})

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true',required=True);p.add_argument('--attempt',required=True);a=p.parse_args();run(a.attempt)
