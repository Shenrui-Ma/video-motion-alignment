"""Read only four known own-run directories; no process or GPU control."""
from pathlib import Path
import json,re,hashlib
BASE=Path('/data3/researcher/h3_runs')
NAMES=['timing_ivebench_heldout_r64_20261018','timing_ivebench_remaining_r69_20261018','timing_flexiact_prompt_pair_r72_20261018','timing_flexiact_official_six_r74_20261018']
for name in NAMES:
 r=BASE/name;out={'root':str(r),'runtime':json.loads((r/'configs/runtime.json').read_text()),'services':[],'jobs':[],'source_shapes':{},'log_evidence':{},'inventories':{}}
 science=json.loads((r/'configs/scientific_contract.json').read_text());out['source_shapes']={c['run_id']:c.get('geometry') for c in science['cases']}
 for p in sorted((r/'processes').glob('service*.json')):
  v=json.loads(p.read_text())
  if 'gpu_readiness' in v:
   out['services'].append({'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'record':v})
 for p in sorted((r/'logs').glob('*_job.json')):
  v=json.loads(p.read_text());run=v['name'];history=r/'logs'/(run+'_history.json');h=json.loads(history.read_text()) if history.exists() else {}
  out['jobs'].append({'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'name':run,'status':v['status'],'submitted_unix':v['submitted_unix'],'observed_unix':v.get('observed_unix'),'service_pid':v['service_pid'],'service_identity':v['service_identity'],'actual_history_status':h.get('status'),'actual_geometry':h.get('prompt',[None,None,{}])[2].get('5',{}).get('inputs',{}) if False else out['source_shapes'].get(run)})
 for rel in ['logs/service_resource_admission.jsonl','logs/resources.jsonl','logs/residency.jsonl']:
  p=r/rel
  if p.exists():out['log_evidence'][rel]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'records':[json.loads(x) for x in p.read_text().splitlines() if x]}
 p=r/'logs/comfyui.log'
 if p.exists():
  lines=[]
  with p.open(errors='replace') as f:
   for i,line in enumerate(f,1):
    if any(word in line.lower() for word in ['loaded completely','loaded partially','offload device','enabled pinned','prompt executed','total vram','total ram','out of memory','torch out of memory','cuda error']):lines.append({'line':i,'text':re.sub(r'\x1b\[[0-9;]*m','',line.strip())})
  out['log_evidence']['logs/comfyui.log']={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'filtered_lines':lines}
 print(json.dumps(out))
