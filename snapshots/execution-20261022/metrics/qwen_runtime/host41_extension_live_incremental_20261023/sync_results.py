"""Pull small AWQ JSON results; return a fully finished delegated batch to .60."""
from pathlib import Path
import json,subprocess,shlex
D=Path(__file__).resolve().parent
TARGET='/data4/research-user/h3_metrics_qwen_20261022/qwen_runtime/extension_live_incremental_20261023'
def remote(host,code,data=None):
 return subprocess.run(['ssh',host,shlex.join(['python3','-c',code])],input=data,capture_output=True,text=True,check=True).stdout
code=r'''
from pathlib import Path
import json,time
r=Path(ROOT);d=r/'run';manifest=json.loads((d/'expected_manifest.json').read_text());results=[]
for j in manifest['jobs']:
 for m in ('instruction_satisfaction','content_fidelity'):
  p=d/'evaluation_awq/results'/j['id']/(m+'.json')
  if p.exists():results.append({'job_id':j['id'],'metric':m,'value':json.loads(p.read_text())})
out={'status':json.loads((d/'status.json').read_text()),'manifest':manifest,'results':results,'time':time.time()}
for name in ('supervisor_identity.json','worker_identity.json','dry_run.json','evaluation_awq/evaluator_configuration.json','evaluation_awq/first_sample_validation.json','evaluation_awq/batch_completion.json'):
 p=d/name
 if p.exists():out[name]=json.loads(p.read_text())
print(json.dumps(out))
'''.replace('ROOT',repr(TARGET))
snap=json.loads(remote('H3_HOST_PRIMARY',code));(D/'target_snapshot.json').write_text(json.dumps(snap,ensure_ascii=False,indent=2))
config='qwen25vl72b_awq4bit_fp16_cpu_bridge_c8b87d4b81f3';done=[r for r in snap['results'] if r['value'].get('status')=='done' and r['value'].get('evaluator',{}).get('configuration_id')==config]
summary={'completed':len(done),'expected':20,'target_status':snap['status'].get('status')};(D/'snapshot_status.json').write_text(json.dumps(summary,indent=2))
if len(done)==20 and snap['status'].get('status')=='completed':
 publish=r'''
from pathlib import Path
import sys,json,hashlib,fcntl,time,math,os
r=Path('/data3/research-user/h3_metrics_20261022/qwen_runtime/extra26_20261022');data=json.load(sys.stdin);rec=json.loads((r/'host41_delegation.json').read_text())
with (r/'launch.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if rec['status']=='completed_returned':
  print(json.dumps({'status':'already_returned','time':rec['completed_time']}));sys.exit(0)
 assert rec['status']=='delegated_active' and rec['pending_manifest']==data['manifest']
 for old in rec['success_preserved']:assert hashlib.sha256(Path(old['path']).read_bytes()).hexdigest()==old['sha256']
 expected={(j['id'],m) for j in rec['pending_manifest']['jobs'] for m in ('instruction_satisfaction','content_fidelity')};assert {(x['job_id'],x['metric']) for x in data['results']}==expected
 for item in data['results']:
  value=item['value'];assert value['status']=='done' and value['evaluator']['configuration_id']=='qwen25vl72b_awq4bit_fp16_cpu_bridge_c8b87d4b81f3';assert math.isfinite(float(value['score']));p=r/'evaluation_awq/results'/item['job_id']/(item['metric']+'.json');p.parent.mkdir(exist_ok=True,parents=True);raw=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)
  if p.exists() and json.loads(p.read_text()).get('status')=='done':assert json.loads(p.read_text())==value
  else:t=p.with_suffix('.return.tmp');t.write_text(raw);t.replace(p)
 rec.update(status='completed_returned',completed_time=time.time(),returned_items=20);(r/'host41_delegation.json').write_text(json.dumps(rec,indent=2));receipt={'status':'completed_returned','preserved_items':156,'returned_items':20,'total_completed':176,'configuration_id':'qwen25vl72b_awq4bit_fp16_cpu_bridge_c8b87d4b81f3','time':time.time()};(r/'host41_return_receipt.json').write_text(json.dumps(receipt,indent=2));(r/'status.json').write_text(json.dumps({'status':'completed','counts':{'done':176,'failed':0,'missing':0},'completion_source':'prior156_plus_host41_extension_live20','time':time.time()},indent=2));print(json.dumps(receipt))
'''
 returned=json.loads(remote('H3_HOST_AUXILIARY',publish,json.dumps(snap)))
 if returned.get('status')=='already_returned':
  returned=json.loads(remote('H3_HOST_AUXILIARY',"from pathlib import Path;print(Path('/data3/research-user/h3_metrics_20261022/qwen_runtime/extra26_20261022/host41_return_receipt.json').read_text())"))
 (D/'RETURNED.json').write_text(json.dumps(returned,indent=2));summary['returned']=returned
print(json.dumps(summary))
