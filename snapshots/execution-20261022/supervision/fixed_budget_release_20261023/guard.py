"""Audit each fixed-budget pilot; admit the next only after natural service exit."""
from pathlib import Path
import sys,json,time,hashlib,fcntl,importlib.util

def may_append(states,first,snap):
 return states.get(first,{}).get('status')=='completed' and snap['worker']['state'] in ('exited','missing_record') and snap['service']['state'] in ('exited','missing_record') and not any(snap['locks'].values()) and not snap['port_listening']

def main(root):
 sys.path.insert(0,str(root/'scripts'));import fixed_budget_helpers as g
 p=root/'custom_nodes/H3TemporalGainFieldFixedBudget/audit.py';spec=importlib.util.spec_from_file_location('budget_audit',p);audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
 d=root/'innovation_handoff/fixed_budget_20261023';jobs=g.read(d/'planned_jobs.json')['jobs'];results={}
 with (d/'guard.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  for _ in range(2880):
   g.reap_finished_children();states=g.read(root/'queue_state/state.json',{'jobs':{}})['jobs']
   for job in jobs:
    jid=job['id'];s=states.get(jid,{})
    if s.get('status') in ('failed','failed_exhausted','invalid','blocked'):raise RuntimeError('Pilot terminal failure '+jid)
    if s.get('status')=='completed' and jid not in results:
     ap=max((root/'audit/feature_gain_field_fixed_budget').glob(jid+'__a*.json'),key=lambda p:p.stat().st_mtime_ns)
     result={'status':'passed','job':jid,'audit':audit.check_budget(g.read(ap)),'output':g.verify_outputs_and_timing(root,states,jid),'audit_sha256':hashlib.sha256(ap.read_bytes()).hexdigest(),'time':time.time()}
     if root.name=='run_uniform_energy':
      service=g.read(root/'service.json');mp=root/'audit/memory'/('capacity20_'+str(service['pid'])+'.json');peak=g.read(mp);assert peak['pid']==service['pid'] and peak['cap_bytes']==int(19.5*1024**3);assert 0<peak['max_allocated_bytes']<=peak['max_reserved_bytes']<=peak['cap_bytes'];result['memory_peak']=peak
     results[jid]=result;g.atomic(d/(jid+'.result.json'),result)
   if len(jobs)==2 and jobs[0]['id'] in results and jobs[1]['id'] not in {j['id'] for j in g.read(root/'jobs.json')['jobs']}:
    snap=g.snapshot(root)
    if may_append(states,jobs[0]['id'],snap):
     with (d/'activation.lock').open('a') as activation:
      fcntl.flock(activation,fcntl.LOCK_EX|fcntl.LOCK_NB);manifest=g.read(root/'jobs.json');assert jobs[1]['id'] not in states;manifest['jobs'].append(jobs[1]);g.atomic(root/'jobs.json',manifest);g.launch_owned_worker(root,d/'SECOND_STARTED.json',{'status':'first_complete_audited','time':time.time()})
   g.atomic(d/'PROGRESS.json',{'status':'observing','completed':len(results),'jobs':list(results),'time':time.time()})
   if len(results)==len(jobs):g.atomic(d/'RESULT.json',{'status':'passed','jobs':results,'time':time.time()});return
   time.sleep(30)
  raise TimeoutError('24h fixedbudget guard')
if __name__=='__main__':
 root=Path(__file__).resolve().parents[1]
 try:main(root)
 except Exception as e:
  (root/'innovation_handoff/fixed_budget_20261023/RESULT.json').write_text(json.dumps({'status':'audit_or_execution_failure','error':repr(e),'time':time.time()},indent=2));raise
