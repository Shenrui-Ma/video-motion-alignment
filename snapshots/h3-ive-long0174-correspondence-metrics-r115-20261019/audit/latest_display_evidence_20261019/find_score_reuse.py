from pathlib import Path
import json,hashlib,time
B=Path(__file__).parent; inv=Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018/inventory')
rows=[]
for name in ['flexiact.json','ivebench.json']:rows+=json.loads((inv/name).read_text())['items']
cache={}
def sha(p):
 p=str(p)
 if p not in cache:
  h=hashlib.sha256()
  with open(p,'rb') as f:
   for x in iter(lambda:f.read(1048576),b''):h.update(x)
  cache[p]=h.hexdigest()
 return cache[p]
def normalized(r):
 q=r.get('quantitative_metrics',{});m=q.get('motion_fidelity',{});o={k:m.get(k) for k in ['native','guided','alternative_native']}
 if r.get('comparison_kind')=='sampler_control':o.update(native=m.get('euler'),alternative_native=m.get('res_multistep'))
 if 'task_repair_motion_fidelity' in q:
  t=q['task_repair_motion_fidelity'];o.update(native=t.get('old_native'),alternative_native=t.get('new_native'))
 return o
roles={'native':'ordinary_video_path','guided':'guided_video_path','alternative_native':'alternative_video_path'}
lookup={r['id']:r for r in rows};pending=json.loads((B/'MISSING_MF.json').read_text());matches=[];missing=[]
for item in pending['all_display_versions_missing']:
 r=lookup[item['id']];n=normalized(r)
 for field in item['missing_fields']:
  p=r.get(roles[field])
  if not p:continue
  if n.get(field) is not None:
   matches.append(dict(id=r['id'],field=field,value=n[field],kind='already_in_inventory_special_field',donor=r['id'],metrics=r.get('quantitative_metrics',{})));continue
  found=[]
  for donor in rows:
   if donor['benchmark']!=r['benchmark'] or donor.get('valid_frames')!=r.get('valid_frames'):continue
   if sha(donor['reference_video_path'])!=sha(r['reference_video_path']):continue
   dm=normalized(donor)
   for dk,dv in dm.items():
    dp=donor.get(roles[dk])
    if dv is None or not dp or sha(dp)!=sha(p):continue
    q=donor['quantitative_metrics']; m=q.get('task_repair_motion_fidelity') if donor['id'].startswith('flex_r98') else q['motion_fidelity']
    sources=m.get('source_sha256',{})
    assert sources and all(sha(path)==digest for path,digest in sources.items()),donor['id']
    found.append(dict(id=r['id'],field=field,value=dv,kind='byte_identical_media_source_valid_domain',donor=donor['id'],donor_field=dk,video_sha256=sha(p),source_sha256=sha(r['reference_video_path']),valid_frames=r['valid_frames'],score_evidence=sources,protocol=m.get('protocol')))
  if found:
   assert len({x['value'] for x in found})==1,(r['id'],field,found)
   matches.append(found[0])
  else:missing.append(dict(id=r['id'],field=field,media=p,media_sha256=sha(p),source=r['reference_video_path'],source_sha256=sha(r['reference_video_path']),valid_frames=r.get('valid_frames')))
d=dict(created_unix=time.time(),GPU_launched=False,reusable_scores=matches,remaining_missing=missing,remaining_versions=len({x['id'] for x in missing}),current_remaining_versions=len(set(x['id'] for x in missing)&set(x['id'] for x in pending['current_missing'])))
p=B/'SCORE_REUSE_VERIFIED.json';p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print('reusable',[(x['id'],x['field'],x['value']) for x in matches]);print('remaining',len(missing),d['remaining_versions'],d['current_remaining_versions']);print('SHA',sha(p))
