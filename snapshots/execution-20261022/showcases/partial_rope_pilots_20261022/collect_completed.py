from pathlib import Path
import subprocess,json
D=Path(__file__).resolve().parent
ORDER=['short_0252','short_0358','long_0039','long_0059','short_0085','short_0274','short_0343']
def remote(host,code):
 p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12',host,'python3','-'],input=code,text=True,capture_output=True,check=True)
 return json.loads(p.stdout)
code='''import pathlib,json
r=pathlib.Path('/data/research-user/h3_metrics_20261022');m=json.loads((r/'code/manifest.json').read_text());ids={j['task_id'] for j in m['jobs'] if j['method']=='partial_temporal_rope'}
jobs=[j for j in m['jobs'] if j['task_id'] in ids and j['method'] in ['source','native','global_weak','partial_temporal_rope']];scores=[]
for j in jobs:
 for f in (r/'evaluation/results'/j['id']).glob('*.json'):
  if f.name!='job.json':scores.append({'task_id':j['task_id'],'method':j['method'],'metric':f.stem,'job_id':j['id'],**json.loads(f.read_text())})
print(json.dumps({'jobs':jobs,'scores':scores},ensure_ascii=False))'''
d=remote('H3_HOST_CONFIGURE_LOCALLY',code)
(D/'completed_snapshot.json').write_text(json.dumps(d,ensure_ascii=False,indent=2))
awq=remote('H3_HOST_CONFIGURE_LOCALLY', '''from pathlib import Path
import json
r=Path('/data3/research-user/h3_metrics_20261022/qwen_runtime/extra26_20261022/evaluation_awq/results');a=[]
for p in r.glob('*/*.json'):
 if p.name in ['instruction_satisfaction.json','content_fidelity.json']:a.append({'job_id':p.parent.name,'metric':p.stem,**json.loads(p.read_text())})
print(json.dumps(a))''')
(D/'awq_completed_snapshot.json').write_text(json.dumps(awq,ensure_ascii=False,indent=2))
print('partial',[(j['task_id'],j['id']) for j in d['jobs'] if j['method']=='partial_temporal_rope'])
