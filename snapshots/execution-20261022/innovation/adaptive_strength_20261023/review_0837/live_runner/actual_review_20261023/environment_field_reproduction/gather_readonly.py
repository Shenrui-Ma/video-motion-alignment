
import pathlib,json,hashlib,sys
p=pathlib.Path(sys.argv[1]);kind=sys.argv[2];sha=lambda b:hashlib.sha256(b).hexdigest();out={}
def read(name):
 f=p/name; return {'sha256':sha(f.read_bytes()),'data':json.loads(f.read_text())}
if kind=='field41':
 out['result']=read('queue_state/results/adapt41_short_0358_temporal_gain_field.json')
 out['history']=read('queue_state/history/769dad83-5c6a-46c6-a12c-3f03c5c78f6b.json')
 out['cache']=read('innovation_cache/short_0358/manifest.json')
 lines=(p/'logs/comfy.log').read_text(errors='replace').splitlines();boots=[]
 for i,l in enumerate(lines):
  if 'H3_TASK_BACKEND_DISPATCH_AUDIT=' in l:
   try:d=json.loads(l.split('H3_TASK_BACKEND_DISPATCH_AUDIT=',1)[1])
   except:continue
   boots.append((i,d))
 for k,(i,d) in enumerate(boots):
  if d.get('pid')==86424:
   end=boots[k+1][0];out['field_service_log']={'boot':d,'line_range_1based':[i+1,end],'next_boot':boots[k+1][1], 'selected_lines':[l for l in lines[i:end] if any(s in l for s in ['pytorch version','Found comfy_kitchen','Total VRAM','VRAM state','Device:','Set vram','loaded completely','loaded partially','Prompt executed','Using pytorch attention','model weight dtype'])]}
 out['current_source_sha']={str(f.relative_to(p)):sha(f.read_bytes()) for folder in ['custom_nodes/H3TemporalGainField','custom_nodes/H3Study'] for f in (p/folder).glob('*.py')}
 out['matching_events']=[]
 for l in (p/'queue_state/events.jsonl').read_text().splitlines():
  try:d=json.loads(l)
  except:continue
  if isinstance(d,dict) and 1792699800<float(d.get('time') or 0)<1792702200:out['matching_events'].append({k:v for k,v in d.items() if k!='statuses'})
else:
 for f in ['logs/backend_dispatch_audit.json','service.json']:out[f]=read(f)
 f=pathlib.Path('/data/research-user/h3_inference_20261023/run_uniform_energy/innovation_cache/short_0358/manifest.json');out['cache']={'sha256':sha(f.read_bytes()),'data':json.loads(f.read_text())}
 lines=(p/'logs/comfy.log').read_text(errors='replace').splitlines();out['selected_log_lines']=[l for l in lines if any(s in l for s in ['pytorch version','Found comfy_kitchen','Total VRAM','Device:','Set vram','loaded completely','loaded partially','model weight dtype','Prompt executed'])]
 out['current_source_sha']={str(f.relative_to(p)):sha(f.read_bytes()) for f in (p/'custom_nodes/H3Study').glob('*.py')}
print(json.dumps(out))
