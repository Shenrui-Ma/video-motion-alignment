import json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
src=(P.parent/'deploy_inputs.py').read_text().split("a=json.loads((P/'assets.json').read_text());rows=[]")[0]
n={'__file__':str(P/'deploy_remaining.py')};exec(src.replace("TARGET='H3_HOST_CONFIGURE_LOCALLY'","TARGET='H3_HOST_CONFIGURE_LOCALLY'"),n)
a=json.loads((P/'remaining_assets.json').read_text());records=[];root=a['remote_target_root']
try:
 for row in a['assets']:
  source=row['destination'].replace(root,'/home/research-user/h3_runs/benchmark_schedule_20261022_host9a')
  status=n['transfer']('H3_HOST_CONFIGURE_LOCALLY',source,row['destination'],row['sha256'])
  records.append(dict(destination=row['destination'],sha256=row['sha256'],status=status));print(row['task_id'],row['role'],status,flush=True)
 for j in json.loads((P/'remaining_jobs.json').read_text())['jobs']:
  files=[(P/j['graph'],root+'/'+j['graph'])];task=j['metadata']['task_id'];cache=P/'cache_manifests'/f'{task}.json'
  if cache.exists():files.append((cache,root+'/innovation_cache/'+task+'/manifest.json'))
  for f,dest in files:
   sha=hashlib.sha256(f.read_bytes()).hexdigest();status=n['transfer'](None,str(f),dest,sha)
   records.append(dict(destination=dest,sha256=sha,status=status))
finally:
 (P/'remaining_deployment_receipt.json').write_text(json.dumps({'records':records,'complete':len(records)==41},indent=2)+'\n')
