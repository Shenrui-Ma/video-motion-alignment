from pathlib import Path
import subprocess,shlex,json,time,concurrent.futures
D=Path(__file__).parent
HOSTS={'host41_extension':('H3_HOST_PRIMARY','/data4/research-user/h3_runs/benchmark_schedule_20261022','expand_short_0135_native'),'host9_extension':('H3_HOST_SECONDARY','/home/research-user/h3_runs/adaptive_role5_20261023','expand2_short_0166_native')}
def check(owner):
 h,r,j=HOSTS[owner];code='''from pathlib import Path
import json,sys,time
r=Path(ROOT);j=JOB;sys.path.insert(0,str(r/'scripts'));import extension_helpers as g;s=g.snapshot(r);state=s['states'].get(j,{});attempt=state.get('attempt_id');timing=g.read(r/'audit/timing'/(str(attempt)+'.json'),{});audit=g.read(r/'audit/router'/(str(attempt)+'.json'),{});d=r/'innovation_handoff/extension_three_20261023';p=g.read(r/'gpu.json',{});print(json.dumps({'time':time.time(),'worker':s['worker'],'service':s['service'],'api':s['api_queue'],'state':state,'timing':timing,'forwards':audit.get('completed_forward_calls',0),'blocks':audit.get('completed_calls',0),'guard':g.identity(g.read(d/'GUARD.json'),str(r/'scripts/extension_guard.py')),'progress':g.read(d/'PROGRESS.json'),'gpu':p,'budget':g.read(r/'shared_gpu_authorization.json'),'runtime_io':(Path('/proc')/str(s['service'].get('pid',0))/'io').read_text() if s['service']['state']=='owned_alive' else None}))
'''.replace('ROOT',repr(r)).replace('JOB',repr(j));p=subprocess.run(['ssh',h,shlex.join(['python3','-c',code])],capture_output=True,text=True,timeout=40);assert p.returncode==0,p.stderr;v=json.loads(p.stdout);(D/owner/'LIVE.json').write_text(json.dumps(v,indent=2));n=len(v['timing'].get('steps',[]));assert v['state'].get('status') not in ['failed','failed_exhausted','invalid'];
 if n:
  assert all(x['seconds']>0 for x in v['timing']['steps']);(D/owner/'FIRST_SAMPLING.json').write_text(json.dumps(v,indent=2))
 print(owner,n,v['service'],flush=True);return n>0
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--watch',action='store_true');args=a.parse_args();done=set()
 for _ in range(60 if args.watch else 1):
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
   for owner,result in zip([o for o in HOSTS if o not in done],ex.map(check,[o for o in HOSTS if o not in done])):
    if result:done.add(owner)
  if len(done)==2:break
  if args.watch:time.sleep(60)
