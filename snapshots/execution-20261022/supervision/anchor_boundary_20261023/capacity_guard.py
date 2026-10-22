"""Finish one bounded allocator-20 pilot, then resume authorized comparisons."""
from pathlib import Path
import os,sys,json,time,fcntl,subprocess,math
R=Path('/data4/research-user/h3_inference_20261023/run');D=R/'innovation_handoff/anchor_priority_20261023/capacity20'
sys.path.insert(0,str(R/'scripts'));import anchor_runtime_helpers as h

def choose_cap(success,peak_bytes):
 return 20 if success and peak_bytes is not None and 0<peak_bytes<=20*1024**3 else 26

def run():
 with (D/'guard.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  req=h.read(D/'request.json');jid=req['anchor_id']
  while True:
   snap=h.snapshot(R);state=snap['states'].get(jid,{})
   if state.get('status') not in ('completed','failed','invalid') or snap['worker']['state']!='exited' or snap['service']['state'] not in ('exited','missing_record') or any(snap['locks'].values()) or snap['port_listening']:
    h.atomic(D/'status.json',{'status':'waiting_anchor_capacity','job_state':state.get('status','not_submitted'),'worker':snap['worker'],'time':time.time()});time.sleep(30);continue
   with (R/'innovation_handoff/activation.lock').open('a') as gate:
    fcntl.flock(gate,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert h.read(R/'jobs.json')==req['base'],'unexpected manifest edit'
    ok=False;error=None;peak=None
    if state['status']=='completed':
     try:
      h.verify_outputs_and_timing(R,snap['states'],jid)
      p=subprocess.run(['python3',str(R/'scripts/anchor_audit.py'),str(R/'audit/feature_anchor'/(state['attempt_id']+'.json')),'--kind','anchor','--output',str(D/'anchor_audit.json')],capture_output=True,text=True)
      assert p.returncode==0,p.stderr
      records=[h.read(p) for p in (R/'audit/memory').glob('capacity20_*.json')];records=[v for v in records if v.get('cap_bytes')==20*1024**3 and v.get('created_unix',0)>=req['unix']]
      assert records,'memory peak not recorded';peak=max(v['max_allocated_bytes'] for v in records);ok=True
     except Exception as e:error=repr(e)
    cap=choose_cap(ok,peak);policy=h.read(R/'shared_gpu_authorization.json');policy.update(torch_allocator_cap_gib=cap,minimum_free_mib=(cap+7)*1024,reason='Post-anchor capacity audit; reserve6GiB plus context1GiB retained')
    h.atomic(R/'shared_gpu_authorization.json',policy)
    target={**req['base'],'jobs':req['base']['jobs']+req['parked_jobs']};target['planned_count']=len(target['jobs']);h.atomic(R/'jobs.json',target)
    receipt={'phase':'prepared','capacity_success':ok,'peak_allocated_bytes':peak,'selected_allocator_gib':cap,'anchor_state':state['status'],'audit_error':error,'jobs':[j['id'] for j in req['parked_jobs']],'unix':time.time()};h.atomic(D/'RESUMED.json',receipt)
    h.launch_owned_worker(R,D/'RESUMED.json',receipt);h.atomic(D/'status.json',{'status':'comparisons_resumed','allocator_gib':cap,'worker':receipt['worker'],'time':time.time()});return
if __name__=='__main__':run()
