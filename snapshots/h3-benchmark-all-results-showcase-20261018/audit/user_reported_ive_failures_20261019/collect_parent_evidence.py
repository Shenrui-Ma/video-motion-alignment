from pathlib import Path
import json,subprocess,shlex,time
R=Path(__file__).resolve().parent;B=R.parents[2]
parents=[('r71','short_0210','p1','timing_ivebench_prompt_pair_r71_20261018'),('r80','short_0230','native','timing_local_edit_repair_r80_20261018'),('r80','short_0352','native','timing_local_edit_repair_r80_20261018')]
paths=[]
for prefix,s,arm,root in parents:
 base='/data5/researcher/h3_runs/'+root;run=f'{prefix}_{s}_seed2026101701_{arm}';shared=f'{prefix}_{s}_p1_shared' if prefix=='r71' else f'{prefix}_{s}_shared'
 paths += [base+'/audit/'+x+'.json' for x in [run+'_noise',run+'_conditioning',shared+'_conditioning']]
paths += ['/data5/researcher/h3_runs/timing_ive_object_control_r91_20261018/'+x for x in ['processes/service.json','processes/controller.json','audit/root_pair_attempt1/STARTED.json']]
code='''import json,hashlib,os,time
from pathlib import Path
paths=PATHS
out={'unix':time.time(),'files':{},'pt_stats':{},'r91':{}}
for name in paths:
 p=Path(name)
 if not p.is_file():out['files'][name]=None;continue
 data=p.read_bytes();v=json.loads(data);out['files'][name]={'sha256':hashlib.sha256(data).hexdigest(),'value':v}
 def walk(x):
  if isinstance(x,dict):
   for y in x.values():walk(y)
  elif isinstance(x,list):
   for y in x:walk(y)
  elif isinstance(x,str) and x.startswith('/data5/researcher/') and x.endswith('.pt'):
   q=Path(x)
   try:st=q.stat();out['pt_stats'][x]={'exists':True,'bytes':st.st_size,'mtime':st.st_mtime}
   except FileNotFoundError:out['pt_stats'][x]={'exists':False}
 walk(v)
r=Path('/data5/researcher/h3_runs/timing_ive_object_control_r91_20261018')
for sub in ['logs','processes','analysis/postrun/short_0114','output']:
 p=r/sub;out['r91'][sub]=[x.name for x in p.iterdir()] if p.is_dir() else None
print(json.dumps(out))
'''.replace('PATHS',repr(paths))
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','H3_SERVER_A','python3 -c '+shlex.quote(code)],capture_output=True,text=True,timeout=50);r.check_returncode();d=json.loads(r.stdout);(R/'REMOTE_PARENT_EVIDENCE.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print('remote small JSON',sum(v is not None for v in d['files'].values()),'PT stat',len(d['pt_stats']),'R91',d['r91'])
