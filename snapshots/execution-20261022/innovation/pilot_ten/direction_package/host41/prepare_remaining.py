"""Prepare eight remaining graphs without changing active jobs or deployed nodes."""
import json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;SOURCE=P.parent
OLD='/home/research-user/h3_runs/benchmark_schedule_20261022_host9a';ROOT='/data4/research-user/h3_runs/benchmark_schedule_20261022'
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def relocate(x):
 if isinstance(x,str):return x.replace(OLD,ROOT)
 if isinstance(x,list):return [relocate(v) for v in x]
 if isinstance(x,dict):return {k:relocate(v) for k,v in x.items()}
 return x
all_jobs=json.loads((SOURCE/'jobs.json').read_text());jobs=[]
for original in all_jobs['jobs']:
 task=original['metadata']['task_id']
 if task in ('short_0252','short_0358'):continue
 j=relocate(original);j['metadata']['host']='H3_HOST_CONFIGURE_LOCALLY';j['id']=j['id'].replace('innov_','innov41_',1)
 g=relocate(json.loads((SOURCE/original['graph']).read_text()))
 if g['5']['class_type']=='H3TrustedConditionCache':
  cache=relocate(json.loads((SOURCE/'cache_manifests'/f'{task}.json').read_text()));save(P/'cache_manifests'/f'{task}.json',cache)
  g['5']['inputs']['manifest_sha256']=hashlib.sha256((P/'cache_manifests'/f'{task}.json').read_bytes()).hexdigest()
 g['14']['inputs']['filename_prefix']=j['id']+'/{attempt_id}';j['graph']='graphs/'+j['id']+'.json';j['expected_output_prefix']=j['id']+'/'
 assert j['metadata']['prompt']==original['metadata']['prompt'] and j['metadata']['seed']==original['metadata']['seed']
 assert j['metadata']['innovation_parameters']==relocate(original['metadata']['innovation_parameters'])
 save(P/j['graph'],g);jobs.append(j)
assets=[relocate(a) for a in json.loads((SOURCE/'assets.json').read_text())['assets'] if a['task_id'] not in ('short_0252','short_0358')]
save(P/'remaining_jobs.json',{'jobs':jobs});save(P/'remaining_assets.json',{'remote_target_root':ROOT,'assets':assets});print('Prepared',len(jobs),'graphs and',len(assets),'assets')
