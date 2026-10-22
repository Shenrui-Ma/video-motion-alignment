import json,pathlib,hashlib,statistics,collections,re
B=pathlib.Path('/Users/researcher/DevProjects');O=B/'h3-research-progress-notes-20261020/timing_audit'
def load(p):return json.loads(pathlib.Path(p).read_text())
def ev(p):return {'file':str(p),'sha256':hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()}
def stat(v):return {'n':len(v),'mean':statistics.mean(v),'median':statistics.median(v),'min':min(v),'max':max(v)} if v else None
base=load(B/'h3-research-progress-notes-20261020/overnight_audit/RESULT.json');rows=[]
excerpts=[]
for p in B.glob('h3-timing-*/audit/ACTUAL_EFFICIENCY_LOG_EXCERPT.json'):excerpts.append((p,load(p)))
for r in base['successful_outputs']:
 p=pathlib.Path(r['completion_evidence']['history_file']);h=load(p);h=h if 'prompt'in h else next(iter(h.values()));g=h['prompt'][2];role=r['method_role']; rid=r['run_id']
 row={k:r[k] for k in ['run_id','source_id','inventory_id','method_role','method_type','period','completion']}; row['history_evidence']=ev(p)
 small=[]
 for q in p.parent.glob('*.json'):
  if q.stat().st_size>1500000:continue
  z=load(q)
  if isinstance(z,dict):small.append((q,z))
 gates=[(q,z) for q,z in small if 'RUNTIME_GATE'in q.name]
 runtime=next((z.get('runtime_profile') for q,z in gates if z.get('runtime_profile')),None)
 if runtime is None:
  cp=pathlib.Path(r['generation_identity']['variant_path'])/'configs/producer_runtime.json'
  if cp.exists():runtime=load(cp)
 row['host']=(runtime or {}).get('host','H3_SERVER_B' if rid.startswith('r138_') else 'unknown');row['runtime']=runtime
 row['graph_configuration']={'classes':[n['class_type'] for n in g.values()], 'unet':g['1']['inputs'], 'text_encoder':g['2']['inputs'], 'sampler':g['8']['inputs'], 'sigmas':g['9']['inputs'],'sigma_shift':g['41']['inputs'], 'guider':g['7']['class_type'], 'Sage_nodes':[n['class_type'] for n in g.values() if 'sage'in n['class_type'].lower()], 'LoRA_nodes':[n['class_type'] for n in g.values() if 'lora'in n['class_type'].lower()]}
 mts={kind:data['timestamp']/1000 for kind,data in h['status']['messages'] if isinstance(data,dict) and 'timestamp'in data}
 start=mts.get('execution_start');end=mts.get('execution_success');row['job_execution_wall_seconds']=end-start if start else None
 manifests=[(q,z) for q,z in small if z.get('schema')=='h3-x0-readout-v1' and z.get('run_id')==rid]
 if manifests:
  q,z=manifests[0];t0=z['created_unix'];t1=z['finished_unix'];row['geometry']=z['geometry'];row['sampler_envelope']={'evidence':ev(q),'start_unix':t0,'finish_unix':t1,'seconds':t1-t0,'seconds_per_callback':(t1-t0)/z['callback_count'],'callbacks':z['callback_count'],'capture_seconds':sum(c.get('capture_seconds',0) for c in z['captures']),'scope':'Measured wrapper interval enclosing Euler sampling, x0 callbacks, final CPU tensor copy/hash/write and endpoint check. Excludes pre-sampler model/condition preparation and final VAE media decode. Not pure model runtime and not exact tqdm sampling interval.'};row['pre_sampler_job_seconds']=t0-start if start else None;row['post_sampler_job_seconds']=end-t1
 routers=[(q,z) for q,z in small if z.get('run_id')==rid and 'backend'in z]
 if routers:
  q,z=routers[0];row['actual_attention']={'evidence':ev(q),'backend':z['backend'],'first_attention':z.get('first_attention'),'layout':z.get('validated_layout'),'routed_calls':z.get('routed_calls'),'completed_forward_calls':z.get('completed_forward_calls')}
 for q,z in gates:
  for ro,rr in z.get('runs',{}).items():
   if isinstance(rr,dict) and rr.get('run_id')==rid:
    row['gate_run_summary']={k:rr[k] for k in ['valid_frames','NFE','Euler_updates','routed_blocks','job_wall_seconds','capture_seconds'] if k in rr};row['gate_evidence']=ev(q)
 for ep,ed in excerpts:
  match=rid.split('_')[0] in ep.parent.parent.name.split('-')
  if not match:continue
  k='guided' if role=='forced' else 'native'
  if k+'_sampling_seconds' in ed:
   row['exact_logged_sampling']={'evidence':ev(ep),'elapsed_seconds':ed[k+'_sampling_seconds'],'mean_seconds_per_step':ed.get(k+'_mean_seconds_per_step',ed.get('mean_seconds_per_step',ed[k+'_sampling_seconds']/20)),'scope':'Actual final tqdm sampling log, includes per-step callbacks; not job wall divided by steps.'}
  elif 'sampling_seconds'in ed:
   row['exact_logged_sampling']={'evidence':ev(ep),'elapsed_seconds':ed['sampling_seconds'],'mean_seconds_per_step':ed.get('mean_seconds_per_step',ed.get('sampling_mean_seconds_per_step',ed['sampling_seconds']/20)),'scope':'Actual final tqdm sampling log, includes per-step callbacks; not job wall divided by steps.'}
  elif any(kk in ed for kk in ['lines','final_sampling_lines']):
   lines=ed.get('final_sampling_lines',ed.get('lines',[]))
   vals=[re.search(r'20/20 \[([0-9:]+)<[^,]+, ([0-9.]+)s/it',line) for line in lines]
   vals=[x for x in vals if x]
   if vals:
    v=vals[-1];parts=[int(x)for x in v[1].split(':')];elapsed=sum(x*60**i for i,x in enumerate(reversed(parts)))
    row['exact_logged_sampling']={'evidence':ev(ep),'elapsed_seconds':elapsed,'mean_seconds_per_step':float(v[2]),'scope':'Actual final tqdm sampling log, includes per-step callbacks; not job wall divided by steps.'}
 rows.append(row)
# All log schemas preserved independently if varying summary fields.
(O/'LOG_EXCERPTS_INDEX.json').write_text(json.dumps([{'evidence':ev(p),'record':d} for p,d in excerpts],indent=2))
groups=collections.defaultdict(list)
for r in rows:
 if r['period']=='sleep' and r['method_role']!='visible_only':groups[(r['host'],r['method_role'])].append(r)
summaries=[]
for (host,role),rs in groups.items():
 summaries.append({'host':host,'role':role,'output_count':len(rs),'envelope_seconds_per_step':stat([r['sampler_envelope']['seconds_per_callback']for r in rs if 'sampler_envelope'in r]),'true_logged_sampler_mean_seconds_per_step':stat([r['exact_logged_sampling']['mean_seconds_per_step']for r in rs if 'exact_logged_sampling'in r]),'capture_seconds_per_run':stat([r['sampler_envelope']['capture_seconds']for r in rs if 'sampler_envelope'in r]),'by_total_frames':{str(f):stat([r['sampler_envelope']['seconds_per_callback'] for r in rs if r.get('geometry',{}).get('frames')==f]) for f in sorted({r['geometry']['frames']for r in rs if 'geometry'in r})}})
result={'schema':'overnight-actual-timing-audit-v1','interval':base['interval'],'count_summary':base['summary'],'measurements':rows,'summary_by_host_role':summaries,'source_accounting':{'R129':{'all_available_generated_outputs':1,'all_available_independent_sources':['long_0039'],'overnight_generated_outputs':1,'scope':'global target media-clock origin alignment, router OFF'},'R132':{'all_available_generated_outputs':1,'all_available_independent_sources':['long_0039'],'overnight_generated_outputs':1,'scope':'450 reference-origin branch interventions; strict historical input gate failed; exploratory'}},'failed_attempts':base['failed_attempts_without_final_video']}
(O/'RESULT.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
for r in rows:print(r['period'],r['run_id'],r['host'],r.get('geometry',{}).get('frames'),'env',round(r.get('sampler_envelope',{}).get('seconds_per_callback',0),2),'logged',r.get('exact_logged_sampling',{}).get('mean_seconds_per_step'),'pre/post',round(r.get('pre_sampler_job_seconds',0),1),round(r.get('post_sampler_job_seconds',0),1))
print('SUMMARIES',json.dumps(summaries))
