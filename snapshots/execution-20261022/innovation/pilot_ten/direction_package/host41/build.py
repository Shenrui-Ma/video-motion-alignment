import copy,json,hashlib,shutil
from pathlib import Path
OUT=Path(__file__).resolve().parent;P=OUT.parent;EXEC=P.parents[2]
OLD='/home/research-user/h3_runs/benchmark_schedule_20261022_host9a';NEW='/data4/research-user/h3_runs/benchmark_schedule_20261022'
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def relocate(x):
 if isinstance(x,str):return x.replace(OLD,NEW)
 if isinstance(x,list):return [relocate(a) for a in x]
 if isinstance(x,dict):return {k:relocate(v) for k,v in x.items()}
 return x
jobs=relocate(json.loads((P/'pilot_jobs.json').read_text()));assets=[]
for j in jobs['jobs']:
 j['metadata']['host']='H3_HOST_CONFIGURE_LOCALLY'
 old=j['id'];j['id']=old.replace('innov_','innov41_',1);sid=j['metadata']['task_id']
 cache=relocate(json.loads((P/'cache_manifests'/f'{sid}.json').read_text()));save(OUT/'cache_manifests'/f'{sid}.json',cache)
 graph=relocate(json.loads((P/j['graph']).read_text()));graph['5']['inputs']['manifest_sha256']=hashlib.sha256((OUT/'cache_manifests'/f'{sid}.json').read_bytes()).hexdigest();graph['14']['inputs']['filename_prefix']=j['id']+'/{attempt_id}';j['graph']='graphs/'+j['id']+'.json';j['expected_output_prefix']=j['id']+'/'
 save(OUT/j['graph'],graph)
for a in json.loads((P/'assets.json').read_text())['assets']:
 if a['task_id'] in {'short_0252','short_0358'}:assets.append(relocate(a))
save(OUT/'jobs.json',jobs);save(OUT/'assets.json',{'remote_target_root':NEW,'assets':assets})
for name,source in [('H3DirectionRuntime',EXEC/'innovation/direction_runtime'),('H3TemporalCoverage',EXEC/'innovation/temporal_coverage'),('H3PartialRoPE',EXEC/'innovation/partial_rope/H3PartialRoPE'),('H3TrustedConditionCache',P/'custom_nodes/H3TrustedConditionCache')]:
 dest=OUT/'custom_nodes'/name;dest.mkdir(parents=True,exist_ok=True)
 for file in source.iterdir():
  if file.suffix in {'.py','.json'} and not file.name.startswith(('test_','verify_','cpu_')):shutil.copy2(file,dest/file.name)
service=(EXEC/'inference/package/scripts/manage_service.py').read_text();service=service.replace("'ComfyUI-KJNodes','H3Study','--input-directory'","'ComfyUI-KJNodes','H3Study','H3DirectionRuntime','H3TemporalCoverage','H3PartialRoPE','H3TrustedConditionCache','--input-directory'")
(OUT/'manage_service.variant.py').write_text(service)
validate=(P/'validate_remote_cache.py').read_text().replace(OLD,NEW).replace('/data5/research-user/h3_runs/short_event_pilot_20261013/ComfyUI','/data3/research-user/h3_runs/silverwolf_486_ref2va4_clean/ComfyUI').replace("selected=os.environ.get('H3_CPU_CACHE_TASKS','').split(',') if os.environ.get('H3_CPU_CACHE_TASKS') else None","selected=['short_0252','short_0358']")
(OUT/'validate_remote_cache.py').write_text(validate)
