from pathlib import Path
import subprocess,json,shlex,time,concurrent.futures
D=Path(__file__).parent
HOSTS={'host41_fixed_budget':('H3_HOST_PRIMARY','/data4/research-user/h3_runs/benchmark_schedule_20261022'),'host81_fixed_budget':('H3_HOST_RTX4090','/data/research-user/h3_inference_20261023/run_uniform_energy'),'host9_fixed_budget':('H3_HOST_SECONDARY','/home/research-user/h3_runs/adaptive_role5_20261023')}
def check(owner):
 host,r=HOSTS[owner];jid=json.loads((D/owner/'jobs.json').read_text())['jobs'][0]['id']
 c='''from pathlib import Path
import sys,json,importlib.util,time
r=Path(ROOT);jid=JOB;d=r/'innovation_handoff/fixed_budget_20261023';p=r/'audit/feature_gain_field_fixed_budget'/(jid+'__a1.json');state=json.loads((r/'queue_state/state.json').read_text())['jobs'].get(jid,{})
if state.get('status') in ('failed','failed_exhausted','invalid'):raise RuntimeError(str(state))
if not p.exists():print(json.dumps({'status':'loading','job':jid,'state':state.get('status'),'time':time.time()}));sys.exit(0)
a=json.loads(p.read_text());n=a['completed_forward_calls']
if n<2:print(json.dumps({'status':'waiting_two_steps','job':jid,'completed_forwards':n,'time':time.time()}));sys.exit(0)
spec=importlib.util.spec_from_file_location('audit_budget',r/'custom_nodes/H3TemporalGainFieldFixedBudget/audit.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);rows=[row for f in a['feature_forward_summaries'][:2] for row in f['layers']];assert len(rows)==100;proof=[m.check_budget_layer(row) for row in rows];assert all(all(abs(x-.25)<1e-7 for x in row['alpha']) for row in rows[:50]);timing=json.loads((r/'audit/timing'/(jid+'__a1.json')).read_text());out={'status':'passed','job':jid,'rows':100,'completed_forwards':n,'first_alpha':.25,'alpha_min':min(min(row['alpha']) for row in rows),'alpha_max':max(max(row['alpha']) for row in rows),'first_two_timing':timing['steps'][:2],'proof_example':proof[-1],'worker':json.loads((r/'worker_pid.json').read_text()),'service':json.loads((r/'service.json').read_text()),'time':time.time()};(d/'FIRST_FORWARD.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
'''.replace('ROOT',repr(r)).replace('JOB',repr(jid))
 p=subprocess.run(['ssh',host,shlex.join(['python3','-c',c])],capture_output=True,text=True);assert p.returncode==0,p.stderr;v=json.loads(p.stdout);(D/owner/'FIRST_FORWARD.json').write_text(json.dumps(v,indent=2));return owner,v
remaining=set(HOSTS)
for _ in range(30):
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
  for owner,v in ex.map(check,list(remaining)):
   print(owner,v['status'],v.get('completed_forwards'),flush=True)
   if v['status']=='passed':remaining.remove(owner)
 if not remaining:break
 time.sleep(30)
else:raise TimeoutError('first2steps15min; inspect runtime')
