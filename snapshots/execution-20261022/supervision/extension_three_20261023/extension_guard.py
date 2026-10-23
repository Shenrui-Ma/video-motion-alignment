"""Audit each extension pair; admit the next only after natural service exit."""
from pathlib import Path
import sys,json,time,hashlib,fcntl,importlib.util

def check_schedule(a,method):
 assert a['schema']=='h3-temporal-router-v1'
 assert a['completed_forward_calls']==20 and a['started_calls']==a['completed_calls']==a['native_override_calls']==1000
 assert a['calls_by_block']==[20]*50 and a['calls_by_forward']==[50]*20
 assert a['block_interval_half_open']==[0,50] and a['radius']==0 and a['time_offset']==0
 weak=method=='global_weak';assert method in ('native','global_weak')
 assert a['schedule']==method and a['mode']==('mass_preserve' if weak else 'native')
 assert a['routed_calls']==(1000 if weak else 0)
 if weak:
  assert a['alpha']==.25 and a['step_set_zero_based']==list(range(20))
  layers=[l for f in a['forward_summaries'] for l in f.get('layer_stats',[])]
  assert len(layers)==1000 and all(l['finite'] for l in layers)
 else:assert a['step_set_zero_based']==[]
 return {'passed':True,'method':method,'forwards':20,'blocks':1000,'routed':a['routed_calls']}

def may_append(states,first,snap):
 return states.get(first,{}).get('status')=='completed' and snap['worker']['state'] in ('exited','missing_record') and snap['service']['state'] in ('exited','missing_record') and not any(snap['locks'].values()) and not snap['port_listening']

def main(root):
 sys.path.insert(0,str(root/'scripts'));import extension_helpers as g
 d=root/'innovation_handoff/extension_three_20261023';jobs=g.read(d/'planned_jobs.json')['jobs'];results={}
 with (d/'guard.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  for _ in range(2880):
   g.reap_finished_children();states=g.read(root/'queue_state/state.json',{'jobs':{}})['jobs']
   for job in jobs:
    jid=job['id'];s=states.get(jid,{})
    if s.get('status') in ('failed','failed_exhausted','invalid','blocked'):raise RuntimeError('Pilot terminal failure '+jid)
    if s.get('status')=='completed' and jid not in results:
     ap=max((root/'audit/router').glob(jid+'__a*.json'),key=lambda p:p.stat().st_mtime_ns)
     result={'status':'passed','job':jid,'audit':check_schedule(g.read(ap),job['metadata']['method']),'output':g.verify_outputs_and_timing(root,states,jid),'audit_sha256':hashlib.sha256(ap.read_bytes()).hexdigest(),'time':time.time()}
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
  raise TimeoutError('24h extension guard')
if __name__=='__main__':
 root=Path(__file__).resolve().parents[1]
 try:main(root)
 except Exception as e:
  (root/'innovation_handoff/extension_three_20261023/RESULT.json').write_text(json.dumps({'status':'audit_or_execution_failure','error':repr(e),'time':time.time()},indent=2));raise
