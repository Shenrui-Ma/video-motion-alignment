import hashlib,json,pathlib,shutil
B=pathlib.Path('/workspace/research-user/DevProjects'); R=B/'video-motion-alignment/execution-20261022'; O=pathlib.Path(__file__).parent
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(pathlib.Path(p).read_text())
M=load(R/'metrics/manifest.json')['jobs']; tasks={t['task_id']:t for t in load(R/'task_catalog.json')['tasks']}; J=load(R/'inference/package/jobs.json')['jobs']
ids=['short_0252','short_0358','long_0039','long_0059','short_0085','short_0274','short_0343','short_0114','crouch__movie_man_4','long_0167']
rows=[]; missing=[]
def graph_record(p,tid,method):
 p=pathlib.Path(p);d=load(p); dest=O/'graphs'/f'{tid}__{method}.json';dest.parent.mkdir(exist_ok=True);shutil.copyfile(p,dest)
 return {'original_file':str(p),'copy':str(dest),'sha256':sha(p),'nodes':{k:v for k,v in d.items() if v['class_type'] in ['UNETLoader','CLIPLoader','KSamplerSelect','ManualSigmas','MiniMaxH3SigmaShift','H3TemporalRouter','H3FixedSchedule','H3EventAuditNoise','H3CachedReferenceConditioning','H3EventAuditReference','H3X0Readout','H3BenchmarkTiming']}},d
for tid in ids:
 old=tid not in tasks; mj={x['method']:x for x in M if x['task_id']==tid}; ng=wg=None
 if old:
  em=load(mj['native']['source_manifest']);c=next(c for c in em['cases'] if c['source_id']==tid)
  rtpath=mj['global_weak']['timing']['original_record']['evidence']['runtime'];rt=load(rtpath)
  gp={'native':c['historical_runs']['native']['graph']['file'],'global_weak':rt['graph']['file']}
  row={'task_id':tid,'dataset':'IVEBench','title':c['title'],'prompt':c['prompt'],'prompt_protocol':'historical_R149_R150_preserved','seed':c['seed'],'geometry':c['geometry'],'official_edit_prompt':mj['native']['metadata']['edit_prompt'],'reference_video':c['media']['source']['file'],'reference_image':None,'remote_source_hint':c.get('historical_source_remote'),'source_manifest':mj['native']['source_manifest'],'global_weak_runtime':rtpath,'global_weak_remote_root':rt['remote_root'],'global_weak_remote_host':rt['host']}
 else:
  t=tasks[tid];jj={x['metadata']['method']:x for x in J if x['metadata']['task_id']==tid};gp={k:R/'inference/package'/jj[k]['graph'] for k in ['native','global_weak']}
  row={'task_id':tid,'dataset':t['benchmark'],'title':t['title'],'prompt':jj['native']['metadata']['prompt'],'prompt_protocol':t['recommended_prompt_protocol'],'seed':t['seed'],'geometry':dict(t['geometry'],valid_frames=t['valid_frames'],crop_xywh=t['evaluation_crop_xywh']),'official_edit_prompt':t['original_task'].get('edit_prompt'),'reference_video':t['reference_video'],'reference_image':t['reference_image'],'remote_source_hint':jj['native']['metadata']['source_video'],'reference_image_remote':jj['native']['metadata'].get('reference_image_remote'),'source_manifest':str(R/'inference/package/jobs.json'),'global_weak_remote_root':'/data4/research-user/h3_runs/benchmark_schedule_20261022','global_weak_remote_host':'H3_HOST_CONFIGURE_LOCALLY'}
 row['prompt_sha256']=hashlib.sha256(row['prompt'].encode()).hexdigest();row['graphs']={};gd={}
 for method,p in gp.items():
  rec,d=graph_record(p,tid,method);row['graphs'][method]=rec;gd[method]=d
 ng=gd['native'];wg=gd['global_weak'];router=wg['50']['inputs'];row['reference_guidance']={k:router.get(k) for k in ['mode','alpha','radius','time_offset','start_frame','end_frame','block_start','block_end','step_start','step_end','schedule']}
 row['sampling']={'sampler':ng['8']['inputs']['sampler_name'],'sigmas':ng['9']['inputs']['sigmas'],'steps':len(ng['9']['inputs']['sigmas'].split(','))-1,'sigma_shift':ng['41']['inputs'],'fps':ng['13']['inputs']['fps']}
 row['native_input_nodes']={k:v for k,v in ng.items() if v['class_type'] in ['LoadVideo','LoadImage','GetVideoComponents','H3EventAuditReference']}
 row['benchmark_outputs']={k:{'remote_metrics_video':mj[k]['video'],'sha256':mj[k].get('sha256')} for k in ['native','global_weak'] if k in mj}
 row['preservation_notes']=[]
 if old:
  row['preservation_notes']+=['Historical prompt retained verbatim; differs from the official one-line edit instruction.','Historical runs include per-step CPU x0 capture and audit I/O; historical timing is not directly comparable to runs without these hooks.','Global-weak graph uses cached conditioning. Preserve the cached tensor or verify re-encoding condition and initial noise match before claiming exact paired rerun.']
  cache=pathlib.Path(gp['global_weak']).parents[1]/'CONDITION_CACHE.json'
  if cache.exists():
   shutil.copyfile(cache,O/f'{tid}__CONDITION_CACHE.json');row['condition_cache_manifest']={'file':str(cache),'sha256':sha(cache),'contents':load(cache)}
  else:missing.append({'task_id':tid,'kind':'local_condition_cache_manifest','path':str(cache)})
 else:row['preservation_notes']+=['Use frozen 20261022 graph and its exact simple prompt; earlier structured-prompt outputs are a different comparison.']
 for k in ['reference_video','reference_image']:
  if row[k]:
   p=pathlib.Path(row[k]);row[k+'_local_exists']=p.exists()
   if not p.exists():missing.append({'task_id':tid,'kind':k,'path':str(p),'remote_hint':row.get('remote_source_hint')})
   else:row[k+'_sha256']=sha(p)
 assert row['sampling']['steps']==20
 assert router['alpha']==.25 and router['step_start']==0 and router['step_end']==20
 assert router['radius']==0 and router['time_offset']==0
 assert ng['6']['inputs']['noise_seed']==row['seed']
 if 'prompt' in ng['5']['inputs']:assert ng['5']['inputs']['prompt']==row['prompt']
 rows.append(row)
result={'schema':'h3-ten-case-innovation-source-catalog-v1','cases':rows,'summary':{'cases':len(rows),'IVEBench':9,'FlexiAct':1,'graph_copies':20,'global_weak_alpha':.25,'sampling_steps':20,'selection':'Exact current main ten tasks; no outcome-based resampling.','remote_existence_checked':False},'cross_case_differences':{'seed':{r['task_id']:r['seed'] for r in rows},'prompt_protocol':{r['task_id']:r['prompt_protocol'] for r in rows},'geometry':{r['task_id']:r['geometry'] for r in rows},'all_sigmas_equal':len({r['sampling']['sigmas'] for r in rows})==1,'all_sigma_shifts_equal':len({json.dumps(r['sampling']['sigma_shift'],sort_keys=True) for r in rows})==1,'all_global_alpha_equal':True,'all_global_steps_0_20':True,'historical_conditioning_cache_and_cpu_capture':['short_0252','short_0358','long_0039','long_0059','short_0085','short_0274']}}
(O/'catalog.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
(O/'missing_assets.json').write_text(json.dumps({'local_missing':missing,'remote_status':'not checked; paths are historical evidence only'},ensure_ascii=False,indent=2))
(O/'verification.json').write_text(json.dumps({'cases':len(rows),'graphs':20,'all_global_weak_alpha_025':True,'all_sampling_steps_20':True,'all_global_steps_0_20':True,'all_seed_and_prompt_match':True,'local_missing_count':len(missing)},indent=2))
print(json.dumps(result['summary'],ensure_ascii=False));print('local missing',len(missing));print('sigmas equal',result['cross_case_differences']['all_sigmas_equal'])
