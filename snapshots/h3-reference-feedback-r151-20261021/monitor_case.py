"""Read only live case evidence; retain a compact local snapshot."""
from pathlib import Path
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sid = sys.argv[1]
case = HERE / "cases" / sid
runtime = json.loads((case / "configs/runtime.json").read_text())
code = "ROOT=" + repr(runtime["remote_root"]) + "\n" + r'''
from pathlib import Path
import json,time,sys,hashlib,subprocess
root=Path(ROOT);sys.path.insert(0,str(root/'scripts'));import service
def read(p):
 for i in range(3):
  try:return json.loads(p.read_text())
  except json.JSONDecodeError:
   if i==2:raise
   time.sleep(.05)
def bound(p):
 return {'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'record':read(p)}
out={'root':ROOT,'unix':time.time(),'jobs':[],'gates':[],'terminal':[]}
p=root/'processes/service.json'
if p.exists():
 s=read(p);out['service']={k:s.get(k) for k in ('pid','identity','gpu_uuid','state')}
 out['service']['exact_generation_alive']=service.current_identity(s['pid'])==s['identity']
for p in sorted((root/'audit/router').glob('*.json')):
 d=read(p);v={k:d.get(k) for k in ('run_id','started_calls','completed_calls','completed_forward_calls','routed_calls','forward_routed_calls','reverse_routed_calls')}
 v['early_steps']=[]
 for s in d.get('forward_summaries',[])[:3]:
  q={'step':s['forward_index']}
  for direction,record in s.get('directions',{}).items():
   rows=record.get('layer_stats',[])
   q[direction]={k:record[k] for k in ('raw_log_mass_min','raw_log_mass_max','all_finite') if k in record}
   for field in ('mass_mean','correction_ratio'):
    q[direction][field+'_range']=[min(x[field] for x in rows),max(x[field] for x in rows)]
  v['early_steps'].append(q)
 for k in ('forward_wall_seconds','timing_scope','sampler_timing'):
  if k in d:v[k]=d[k]
 out['jobs'].append(v)
for p in sorted((root/'analysis/postrun').glob('*/*GATE.json')):
 d=read(p);out['gates'].append({'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'passed':d.get('passed'),'run':d.get('run_id',d.get('run'))})
for attempt in sorted((root/'audit').glob('root_r151*')):
 for name in ('COMPLETE.json','FAILURE.json','ROOT_EXIT_RECEIPT.json'):
  p=attempt/name
  if p.exists():out['terminal'].append(bound(p))
p=root/'logs/comfyui.log'
if p.exists():out['log_tail']=p.read_text()[-1500:]
print(json.dumps(out))
'''
result = subprocess.run(["ssh", "-o", "ProxyCommand=none", "H3_SERVER_A", "python3 -"],
                        input=code, text=True, capture_output=True, check=True)
value = json.loads(result.stdout)
(case / "audit/LATEST_MONITOR.json").write_text(
    json.dumps(value, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(value, ensure_ascii=False))
