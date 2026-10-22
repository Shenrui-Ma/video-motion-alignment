"""A second scientific pilot starts only after the first export and full audit pass."""
from pathlib import Path
import json,time,sys,hashlib,fcntl

def sequence_ready(states,first_result,snap):
 return first_result.get('status')=='passed' and states.get(first_result['job'],{}).get('status')=='completed' and snap['worker']['state'] in ('exited','missing_record') and snap['service']['state'] in ('exited','missing_record') and not any(snap['locks'].values()) and not snap['port_listening']

def main(root):
 sys.path.insert(0,str(root/'scripts'));import runtime_helpers as g;import role5_audit
 d=root/'innovation_handoff/role5_transfer';jobs=g.read(d/'planned_jobs.json')['jobs'];assert len(jobs)==2;results={}
 with (d/'sequence.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  for _ in range(2880):
   g.reap_finished_children();states=g.read(root/'queue_state/state.json',{'jobs':{}})['jobs']
   for job in jobs:
    jid=job['id'];st=states.get(jid,{})
    if st.get('status') in ('failed','failed_exhausted','invalid','blocked'):
     g.atomic(d/'RESULT.json',{'status':'execution_failed','job':jid,'job_state':st,'time':time.time()});return
    if st.get('status')=='completed' and jid not in results:
     p=max((root/'audit/feature_gain_field_role5').glob(jid+'__a*.json'),key=lambda p:p.stat().st_mtime_ns)
     result={'status':'passed','job':jid,'audit':role5_audit.check_role5(g.read(p)),'output':g.verify_outputs_and_timing(root,states,jid),'audit_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'time':time.time()};results[jid]=result;g.atomic(d/(jid+'.result.json'),result)
   first=jobs[0]['id'];second=jobs[1]['id'];manifest=g.read(root/'jobs.json');ids=[j['id'] for j in manifest['jobs']]
   if first in results and second not in ids:
    snap=g.snapshot(root)
    if sequence_ready(states,results[first],snap):
     with (d/'activation.lock').open('a') as activation:
      fcntl.flock(activation,fcntl.LOCK_EX|fcntl.LOCK_NB)
      assert g.read(root/'jobs.json')['jobs']==[jobs[0]];assert second not in states
      g.atomic(root/'jobs.json',{'jobs':jobs,'planned_count':2});rec={'status':'first_audit_passed_second_started','source_result_sha256':hashlib.sha256((d/(first+'.result.json')).read_bytes()).hexdigest(),'time':time.time()};g.launch_owned_worker(root,d/'SECOND_STARTED.json',rec)
   g.atomic(d/'PROGRESS.json',{'status':'observing','completed':len(results),'jobs':list(results),'time':time.time()})
   if len(results)==2:g.atomic(d/'RESULT.json',{'status':'passed','jobs':results,'time':time.time()});return
   time.sleep(30)
  raise TimeoutError('Role5 sequence24h')
if __name__=='__main__':
 r=Path(__file__).resolve().parents[1]
 try:main(r)
 except Exception as e:
  (r/'innovation_handoff/role5_transfer/RESULT.json').write_text(json.dumps({'status':'audit_or_sequence_error','error':repr(e),'time':time.time()},indent=2));raise
