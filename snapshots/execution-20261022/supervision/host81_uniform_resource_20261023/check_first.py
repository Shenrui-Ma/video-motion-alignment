from pathlib import Path
import subprocess,shlex,json,time
D=Path(__file__).parent;R='/data/research-user/h3_inference_20261023/run_uniform_energy'
code='''from pathlib import Path
import sys,json,time,math
r=Path(ROOT);sys.path.insert(0,str(r/'scripts'));import uniform_audit
p=r/'audit/feature_gain_field_uniform_energy/adapt41_short_0358_temporal_gain_field_uniform_energy__a1.json'
if not p.exists():print(json.dumps({'status':'waiting_model_loading','time':time.time()}));sys.exit(0)
a=json.loads(p.read_text())
if a['completed_forward_calls']<2:print(json.dumps({'status':'waiting_two_forwards','forward_count':a['completed_forward_calls'],'time':time.time()}));sys.exit(0)
fs=a['feature_forward_summaries'][:2];proofs=[]
for f in fs:
 assert len(f['layers'])==50
 proofs.extend(uniform_audit.check_uniform_layer(row) for row in f['layers'])
assert all(all(abs(x-.25)<1e-7 for x in row['alpha']) for row in fs[0]['layers'])
t=json.loads((r/'audit/timing/adapt41_short_0358_temporal_gain_field_uniform_energy__a1.json').read_text());rec={'status':'passed','layers':100,'first_alpha':.25,'independent_layer_checks':True,'max_relative_energy_error':max(abs(p['energy_relative_error']) for p in proofs),'alpha_min':min(min(row['alpha']) for f in fs for row in f['layers']),'alpha_max':max(max(row['alpha']) for f in fs for row in f['layers']),'timing':t['steps'][:2],'service':json.loads((r/'service.json').read_text()),'time':time.time()};(r/'innovation_handoff/uniform_energy/FIRST_FORWARD.json').write_text(json.dumps(rec,indent=2));print(json.dumps(rec))
'''.replace('ROOT',repr(R))
for _ in range(30):
 x=json.loads(subprocess.check_output(['ssh','H3_HOST_RTX4090',shlex.join(['python3','-c',code])],text=True));(D/'FIRST_FORWARD_CHECK.json').write_text(json.dumps(x,indent=2))
 if x['status']=='passed':print(json.dumps(x));break
 time.sleep(30)
else:raise TimeoutError('two forwards not available15min; inspect actual queue')
