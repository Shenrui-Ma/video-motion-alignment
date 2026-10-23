import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
REMOTE='/home/research-user/h3_runs/benchmark_schedule_20261022_host9a'
def save(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
cases=json.loads((ROOT/'innovation/pilot_ten/manifest_preparation/catalog.json').read_text())['cases']
metrics=json.loads((ROOT/'metrics/manifest.json').read_text())['jobs']
newjobs=json.loads((ROOT/'inference/package/jobs.json').read_text())['jobs']
template=json.loads((ROOT/'inference/host9a/graphs/expand_short_0353_global_weak.json').read_text())
assets=[];jobs=[];checks=[]
for case in cases:
 sid=case['task_id'];rid='innov_'+sid+'_direction_gated';geo=case['geometry'];frames=geo.get('sampled_frames',geo.get('frames'))
 g=copy.deepcopy(template);g['6']['inputs']['noise_seed']=case['seed'];g['9']['inputs']['sigmas']=case['sampling']['sigmas']
 g['41']['inputs']=copy.deepcopy(case['sampling']['sigma_shift'])
 g['50']={'class_type':'H3DirectionGatedSchedule','inputs':dict(model=['41',0],positive=['5',0],enabled=True,mode='direction_gated',schedule='global_weak',selected_layers='all',alpha=.25,min_routing_offset=.25,min_concentration=.15,min_tangent_norm=1e-6,query_chunk=16,key_chunk=512,record_cuda_timing=True,start_frame=0,end_frame=geo['valid_frames']-1,run_id='{attempt_id}',audit_dir=REMOTE+'/audit/direction')}
 g['52']['inputs']['output_dir']=REMOTE+'/audit/timing';g['14']['inputs']['filename_prefix']=rid+'/{attempt_id}'
 source=next(j for j in metrics if j['task_id']==sid and j['method']=='source')
 source_name=Path(case['reference_video']).name
 src_sha=case.get('reference_video_sha256',source['sha256'])
 assets.append(dict(role='source_video',task_id=sid,local_source=case['reference_video'],remote_source=source['video'],remote_source_host='H3_HOST_CONFIGURE_LOCALLY',destination=REMOTE+'/input/'+source_name,sha256=src_sha))
 if case.get('condition_cache_manifest'):
  manifest=copy.deepcopy(case['condition_cache_manifest']['contents'])
  for rec in [manifest['conditioning']]+manifest['tensors']:
   origin=rec['file'];dest=REMOTE+'/innovation_cache/'+sid+'/'+Path(origin).name
   assets.append(dict(role=rec.get('role','conditioning_json'),task_id=sid,remote_source=origin,remote_source_host=('H3_HOST_CONFIGURE_LOCALLY' if origin.startswith(('/data5/','/home/')) else 'H3_HOST_CONFIGURE_LOCALLY'),destination=dest,sha256=rec['sha256']))
   rec['file']=dest
  manifest['source_video']=REMOTE+'/input/'+source_name
  cache=OUT/'cache_manifests'/f'{sid}.json';save(cache,manifest)
  g['5']={'class_type':'H3TrustedConditionCache','inputs':dict(cache_manifest=REMOTE+'/innovation_cache/'+sid+'/manifest.json',manifest_sha256=sha(cache))}
  for node in ['2','22','23']:g.pop(node)
 else:
  original=json.loads(Path(case['graphs']['global_weak']['copy']).read_text())
  g['5']=copy.deepcopy(original['5']);g['22']=copy.deepcopy(original['22']);g['23']=copy.deepcopy(original['23'])
  if '21' in original:g['21']=copy.deepcopy(original['21'])
  if case.get('reference_image'):
   assets.append(dict(role='reference_image',task_id=sid,local_source=case['reference_image'],remote_source=case['reference_image_remote'],remote_source_host='H3_HOST_CONFIGURE_LOCALLY',destination=REMOTE+'/input/'+Path(case['reference_image']).name,sha256=case['reference_image_sha256']))
 if case['dataset']=='FlexiAct':
  meta=copy.deepcopy(next(j['metadata'] for j in newjobs if j['metadata']['task_id']==sid))
 else:meta={'original_task':source['metadata'],'evaluation_metadata':source['metadata']}
 meta.update(timing_file=REMOTE+'/audit/timing/{attempt_id}.json',host='H3_HOST_CONFIGURE_LOCALLY',remote_root=REMOTE,steps=20,task_id=sid,benchmark=case['dataset'],title=case['title'],cohort='innovation',method='direction_gated',reference_video=case['reference_video'],source_video=REMOTE+'/input/'+source_name,reference_image=case['reference_image'],prompt=case['prompt'],recommended_prompt=case['prompt'],prompt_protocol=case['prompt_protocol'],seed=case['seed'],valid_frames=geo['valid_frames'],fps=geo['fps'],evaluation_crop_xywh=geo['crop_xywh'],geometry=dict(width=geo['width'],height=geo['height'],frames=frames,fps=geo['fps']),sampling_steps=20,innovation_parameters=g['50']['inputs'],comparison_outputs=case['benchmark_outputs'])
 file=OUT/'graphs'/f'{rid}.json';save(file,g)
 jobs.append(dict(id=rid,graph='graphs/'+file.name,expected_output_prefix=rid+'/',progress_file=REMOTE+'/logs/comfy.log',metadata=meta))
 checks.append(dict(task_id=sid,seed_match=g['6']['inputs']['noise_seed']==case['seed'],sigmas_match=g['9']['inputs']['sigmas']==case['sampling']['sigmas'],prompt_preserved=True,geometry_preserved=True,no_intermediate_vae_or_pose=True,cache=bool(case.get('condition_cache_manifest')),graph_sha256=sha(file)))
save(OUT/'jobs.json',{'jobs':jobs});save(OUT/'pilot_jobs.json',{'jobs':jobs[:2]});save(OUT/'assets.json',{'remote_target_root':REMOTE,'assets':assets});save(OUT/'verification.json',{'checks':checks,'total_graphs':len(jobs),'pilot_task_ids':[c['task_id'] for c in cases[:2]],'runtime_gpu_verified':False})
