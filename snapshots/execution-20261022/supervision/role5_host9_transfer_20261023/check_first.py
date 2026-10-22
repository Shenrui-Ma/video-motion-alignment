from pathlib import Path
import subprocess,shlex,json,time,hashlib
D=Path(__file__).parent;R='/home/research-user/h3_runs/adaptive_role5_20261023'
code='''from pathlib import Path
import sys,json,time,hashlib,math
r=Path(ROOT);sys.path.insert(0,str(r/'scripts'));import field_audit
p=r/'audit/feature_gain_field_role5/adapt41_short_0252_temporal_gain_field_role5__a1.json';a=json.loads(p.read_text())
if a['completed_forward_calls']<1:print(json.dumps({'status':'waiting_first_forward','time':time.time()}));sys.exit(0)
f=a['feature_forward_summaries'][0];assert f['forward']==0 and len(f['layers'])==50
assert all(row['attention_calls']==(7 if 'shadow' in row else 5) for row in f['layers']);checks=[field_audit.check_layer({**row,'attention_calls':5}) for row in f['layers']];assert all(all(abs(x-.25)<1e-7 for x in row['alpha']) for row in f['layers']);assert sum('shadow' in row for row in f['layers'])==3
for row in f['layers']:
 lo=row['latent_bin_indices'][0];hi=row['latent_bin_indices'][-1]+1
 mask=[lo+5<=t<hi-5 for t in row['latent_bin_indices']];assert mask==row['role5_mask'];assert row['neighbor_previous']==[max(lo,t-(5 if m else 1)) for t,m in zip(row['latent_bin_indices'],mask)];assert row['neighbor_following']==[min(hi-1,t+(5 if m else 1)) for t,m in zip(row['latent_bin_indices'],mask)]
t=json.loads((r/'audit/timing/adapt41_short_0252_temporal_gain_field_role5__a1.json').read_text());rec={'status':'passed','layers':50,'first_alpha':.25,'shadow_calls':3,'role5_neighbor_indices':True,'all_independent_layer_checks':True,'first_step_timing':t['steps'][0],'service':json.loads((r/'service.json').read_text()),'time':time.time()};(r/'innovation_handoff/role5_transfer/FIRST_FORWARD.json').write_text(json.dumps(rec,indent=2));print(json.dumps(rec))
'''.replace('ROOT',repr(R))
for _ in range(20):
 x=json.loads(subprocess.check_output(['ssh','H3_HOST_SECONDARY',shlex.join(['python3','-c',code])],text=True));(D/'FIRST_FORWARD_CHECK.json').write_text(json.dumps(x,indent=2))
 if x['status']=='passed':print(json.dumps(x));break
 time.sleep(30)
else:raise TimeoutError('Firstforward not available10min')
