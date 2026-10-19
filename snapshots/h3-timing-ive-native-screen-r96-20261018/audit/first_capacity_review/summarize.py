from pathlib import Path
import json,re,sys,hashlib
HERE=Path(__file__).resolve().parent
p=Path(sys.argv[1]) if len(sys.argv)>1 else sorted(HERE.glob('snapshot_*.json'))[-1]
d=json.loads(p.read_text());files=d['files']
def data(name):
 f=files.get(name,{})
 return json.loads(f['text']) if f.get('present') else None
base=data('audit/CGROUP_STARTUP.json');baseline={x['path']:x for x in base['ancestors']};all_rows=[json.loads(x) for x in files['logs/resources.jsonl']['text'].splitlines()];rows=[x for x in all_rows if x.get('job')=='r96_long_0047_seed2026101701_native'];samples=[]
for row in rows:
 c=row.get('cgroup_memory',{});snap=c.get('snapshot')
 if c.get('sample_available') and snap:samples.append(snap)
summary={}
for path,old in baseline.items():
 values=[next((a for a in x['ancestors'] if a['path']==path),None) for x in samples];values=[x for x in values if x]
 if not values:continue
 current=[x['current_bytes'] for x in values if x['current_bytes'] is not None]
 summary[path]={'startup_current_bytes':old['current_bytes'],'sampled_current_peak_bytes':max(current) if current else None,'sampled_last_current_bytes':values[-1]['current_bytes'],'sample_count':len(values),'last_events_delta':{k:values[-1]['events'][k]-v for k,v in old['events'].items() if k in values[-1]['events']},'max_PSI_avg10':{name:max(x['pressure'].get(name,{}).get('avg10',0) for x in values) for name in ('some','full')},'PSI_total_increment_us':{name:values[-1]['pressure'].get(name,{}).get('total',0)-old['pressure'].get(name,{}).get('total',0) for name in ('some','full')},'kernel_peak_counter_start':old['peak_bytes'],'kernel_peak_counter_latest':values[-1]['peak_bytes'],'high_bytes':old['high_bytes'],'max_bytes':old['max_bytes']}
 if current and old['high_bytes'] is not None:summary[path]['min_sampled_high_headroom_bytes']=old['high_bytes']-max(current)
 if current and old['max_bytes'] is not None:summary[path]['min_sampled_max_headroom_bytes']=old['max_bytes']-max(current)
 if path.endswith('.scope'):summary[path]['peak_interpretation']='Fresh attempt session kernel memory.peak; includes service and same-session administrative processes/cache, not isolated model allocation.'
 else:summary[path]['peak_interpretation']='Kernel peak may predate this attempt; sampled_current_peak is this-attempt lower bound. Ancestor includes other users.'
gpu=[]
for row in rows:
 if row.get('sample_available') and row.get('sample'):
  fields=[x.strip() for x in row['sample'].split(',')]
  gpu.append({'unix':row['unix'],'memory_used_mib':float(fields[1]),'utilization_percent':float(fields[2]),'temperature_c':float(fields[3])})
manifest=data('audit/x0/r96_long_0047_seed2026101701_native/manifest.json');job=data('logs/r96_long_0047_seed2026101701_native_job.json');history=data('logs/r96_long_0047_seed2026101701_native_history.json');router=data('audit/router/r96_long_0047_seed2026101701_native.json');backend=data('logs/backend_dispatch_audit.json');times={'submitted_unix':job['submitted_unix'],'observation_unix':d['observed_unix'],'observed_status':job['status'],'submit_to_observation_seconds':d['observed_unix']-job['submitted_unix']}
if manifest:
 times.update(sampler_started_unix=manifest['created_unix'],submit_to_sampler_start_seconds=manifest['created_unix']-job['submitted_unix'],callback_count=manifest['callback_count'],capture_seconds=sum(x['capture_seconds'] for x in manifest['captures']))
 if manifest.get('finished_unix'):
  times['sampler_with_capture_seconds']=manifest['finished_unix']-manifest['created_unix'];times['sampler_finished_unix']=manifest['finished_unix']
if history:
 events=history['status'].get('messages',[]);times['history_messages']=events
 if manifest and manifest.get('finished_unix'):times['sampler_end_to_success_observation_upperbound_seconds']=job['observed_unix']-manifest['finished_unix']
text=files['logs/comfyui.log']['text'];selected=[line for line in re.sub(r'\x1b\[[0-9;]*m','',text).splitlines() if any(x in line for x in ['Requested to load','loaded completely','loaded partially','Unloaded','lowvram','Prompt executed','FLOW_AV','Native ops:','Using RAM pressure cache'])]
value={'schema':'r96-first-capacity-observation-v1','input_snapshot':p.name,'input_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'observed_unix':d['observed_unix'],'source':'long_0047','service_pid':d['owner']['pid'],'cgroup':summary,'resource_scope':'only rows whose job is r96_long_0047_seed2026101701_native; current manual snapshot may be later','gpu_sampled':{'sample_count':len(gpu),'peak_used_mib':max(x['memory_used_mib'] for x in gpu) if gpu else None,'peak_temperature_c':max(x['temperature_c'] for x in gpu) if gpu else None,'interpretation':'Device total memory sampled about20seconds; lower bound on peak, not allocator high-water mark. Current PID list saved separately.'},'timings':times,'load_messages':selected,'backend':backend,'router_summary':{k:router.get(k) for k in ['status','backend','started_calls','completed_calls','completed_forward_calls','native_override_calls','routed_calls','created_unix','updated_unix']} if router else None,'current_proc':d['proc'],'current_cgroups':d['cgroups'],'current_GPU':d['gpu'],'limitations':['Single-source107total/97valid Native run; fixed guidance/later158framecases capacity not certified.','Cold preparation duration includes file/model loading, tokenization and reference VAE encode; individual load phase timings unavailable.','Sampler duration includes passive snapshot writes and final capture checks.','No new watcher, profiler or CUDA operation; existing telemetry only.','PSI/event deltas for shared ancestors include unrelated users.','No second GPU launch authorized by this report.']}
(HERE/'CAPACITY_SUMMARY.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps({'status':times['observed_status'],'callbacks':times.get('callback_count'),'parent_sampled_peak_gib':summary['/user.slice']['sampled_current_peak_bytes']/2**30,'parent_last_gib':summary['/user.slice']['sampled_last_current_bytes']/2**30,'gpu_peak_sampled_mib':value['gpu_sampled']['peak_used_mib'],'events_delta':summary['/user.slice']['last_events_delta']},indent=2))
