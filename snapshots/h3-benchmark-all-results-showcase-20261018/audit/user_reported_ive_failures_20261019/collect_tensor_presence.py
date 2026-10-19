from pathlib import Path
import json,subprocess,shlex
R=Path(__file__).resolve().parent;d=json.loads((R/'REMOTE_PARENT_EVIDENCE.json').read_text());paths=set();hash_small=set()
for name,entry in d['files'].items():
 if not entry:continue
 base=str(Path(name).parent)
 def walk(v):
  if isinstance(v,dict):
   if 'tensor_file' in v:paths.add(base+'/'+v['tensor_file'])
   for x in v.values():walk(x)
  elif isinstance(v,list):
   for x in v:walk(x)
 walk(entry['value'])
 if name.endswith('_noise.json'):
  paths.add(entry['value']['cache_file']);hash_small.add(entry['value']['cache_file'])
for root,run in [('timing_ivebench_prompt_pair_r71_20261018','r71_short_0210_seed2026101701_p1'),('timing_local_edit_repair_r80_20261018','r80_short_0230_seed2026101701_native'),('timing_local_edit_repair_r80_20261018','r80_short_0352_seed2026101701_native')]:
 for i in range(6):paths.add('/data5/researcher/h3_runs/'+root+'/audit/x0/'+run+f'/x0_step{i:03}.pt')
code='''from pathlib import Path
import json,time,hashlib
out={'unix':time.time(),'files':{}}
for name in PATHS:
 p=Path(name)
 try:
  st=p.stat();x={'exists':True,'bytes':st.st_size,'mtime':st.st_mtime}
  if name in HASH:x['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
  out['files'][name]=x
 except FileNotFoundError:out['files'][name]={'exists':False}
print(json.dumps(out))
'''.replace('PATHS',repr(sorted(paths))).replace('HASH',repr(sorted(hash_small)))
x=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','H3_SERVER_A','python3 -c '+shlex.quote(code)],capture_output=True,text=True,timeout=50);x.check_returncode();v=json.loads(x.stdout);(R/'REMOTE_PARENT_TENSOR_PRESENCE.json').write_text(json.dumps(v,indent=2)+'\n');print('existing',sum(i['exists'] for i in v['files'].values()),'total',len(v['files']),'noisehashed',sum('sha256' in i for i in v['files'].values()))
