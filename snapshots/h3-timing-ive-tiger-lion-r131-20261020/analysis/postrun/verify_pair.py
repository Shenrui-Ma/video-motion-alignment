"""CPU actual-output verifier, one fresh Native/ON pair. Quality is assessed separately."""
import argparse,copy,json,os,subprocess,sys,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import torch
from capture_checks import inspect_capture,checked_snapshot,inspect_blob,condition_files,signature,expected_routing
from r123_contract import read,sha,require,registry,validate_job,SOURCES,geometry,latent_shapes,routing_layout
from execution_gate import atomic,persist_gate

def semantic_condition(c):
 return {k:v for k,v in c.items() if k!='run_id'}

def walk_blobs(value):
 if isinstance(value,dict):
  if 'tensor_file' in value:yield value
  for v in value.values():yield from walk_blobs(v)
 elif isinstance(value,list):
  for v in value:yield from walk_blobs(v)

def output_file(root,history):
 images=history['outputs']['14']['images'];require(len(images)==1,'expected one final video')
 record=images[0];require(record.get('type')=='output','final file is not in output')
 rel=Path(record.get('subfolder',''))/record['filename'];require(not rel.is_absolute() and '..' not in rel.parts,'unsafe final video path')
 file=root/'output'/rel;require(file.is_file() and not file.is_symlink(),'final video missing')
 return file

def video_properties(path,case):
 result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames','-of','json',str(path)],capture_output=True,text=True,timeout=120,check=True)
 streams=json.loads(result.stdout)['streams'];require(len(streams)==1,'expected exactly one video stream');s=streams[0]
 require(s['width']==1312 and s['height']==736 and int(s['nb_read_frames'])==geometry(case)['frames'] and s['avg_frame_rate']=='24/1','final geometry/frame count/fps differs')
 return s

def verify(root,source,native_only=False):
 torch.set_num_threads(1);root=Path(root).resolve();require(source in SOURCES,'unknown source');jobs,order=registry(root)
 runtime=read(root/'configs/runtime.json');runtime_sha=sha(root/'configs/runtime.json');seal=read(root/'deploy_manifest.json')
 checks={};checks['producer_seal']=all(sha(root/p)==v['sha256'] for p,v in seal['files'].items())
 owner=read(root/'processes/service.json');checks['actual_runtime_device']=(owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port'])
 pair=[run for run in order if jobs[run]['source_id']==source];require(len(pair)==2,'paired registry differs')
 if native_only:pair=pair[:1]
 result={'schema':'r123-native-runtime-gate-v1' if native_only else 'r123-paired-runtime-gate-v1','source_id':source,'prompt_version':'official_context_ir_with_benchmark_captions_and_subject_binding','runtime_profile_sha256':runtime_sha,'runtime_profile':runtime,'checks':checks,'runs':{},'created_unix':time.time(),'quality_assessment':'One source with verbatim official edit sentence and minimal reference/task envelope; all valid frames reviewed for requested edit, scene preservation and separately visible action timing.','condition_tensor_files':[],'service_owner':{'pid':owner['pid'],'identity':owner['identity']}}
 conditions={};noises={};manifests={};seen=set()
 for run in pair:
  row=validate_job(run,root);arm=row['arm'];case=row['case'];forced=arm=='forced';graph=read(root/'configs/graphs'/f'{run}.json');grid=torch.tensor([float(x) for x in graph['9']['inputs']['sigmas'].split(',')],dtype=torch.float32).tolist()
  hist=read(root/'logs'/f'{run}_history.json');job=read(root/'logs'/f'{run}_job.json')
  checks[arm+'_history']=(hist['status']['completed'] is True and hist['status']['status_str']=='success' and hist['prompt'][2]==graph and hist['prompt'][1]==job['prompt_id'] and job['status']=='success' and job['name']==run)
  checks[arm+'_service']=(job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'] and job['graph_sha256']==row['graph_sha256'])
  c=read(root/'audit'/f'{run}_conditioning.json');n=read(root/'audit'/f'{run}_noise.json');conditions[arm]=c;noises[arm]=n
  shared=root/'audit'/f'r123_{source}_shared_conditioning.json';shared_value=read(shared)
  checks[arm+'_shared_conditions']=(c['run_id']==run and c['pair_snapshot']['verified'] is True and c['pair_snapshot']['source_run_id']==f'r123_{source}_shared' and c['pair_snapshot']['source_manifest_sha256']==sha(shared) and c['prompt']==case['prompt'])
  require(len(condition_files(c))==6,'expected six condition tensor blobs')
  for record in walk_blobs(shared_value):
   if record['tensor_file'] not in seen:
    seen.add(record['tensor_file']);result['condition_tensor_files'].append(inspect_blob(root/'audit',record))
  router=read(root/'audit/router'/f'{run}.json');expect={'run_id':run,'mode':'mass_preserve' if forced else 'native','alpha':1.,'radius':0,'time_offset':0,'block_interval_half_open':[0,50],'step_interval_half_open':[6,15],'pixel_interval_inclusive':[0,case['valid_frame_count']-1],'started_calls':1000,'completed_calls':1000,'completed_forward_calls':20,'native_override_calls':1000,'routed_calls':450 if forced else 0,'calls_by_forward':[50]*20,'calls_by_block':[20]*50,'routed_by_forward':expected_routing(forced),'routed_by_block':[9 if forced else 0]*50,'sample_sigmas':grid,'expected_sampling_steps':20}
  checks[arm+'_actual_execution_counts']=all(router.get(k)==v for k,v in expect.items())
  plan=router['validated_layout'];seq=c['packed_layout']['seq_len'];route=routing_layout(case);shapes=latent_shapes(case);bins=route['latent_interval_half_open'][1];rows=route['frame_rows'];t=shapes['video'][2]
  checks[arm+'_actual_layout']=(router['first_attention']['qkv_shape']==[1,56,seq,128] and plan['frame_rows']==rows and plan['latent_interval_half_open']==route['latent_interval_half_open'] and plan['position_bin_coverage_inclusive']==route['position_bin_coverage_inclusive'] and plan['pixel_interval_inclusive']==route['pixel_interval_inclusive'] and plan['query_interval_half_open']==[plan['target_video_segment'][0],plan['target_video_segment'][0]+bins*rows] and plan['key_interval_half_open']==[plan['reference_video_segment'][0],plan['reference_video_segment'][0]+bins*rows] and plan['target_video_segment'][1]-plan['target_video_segment'][0]==t*rows and plan['reference_video_segment'][1]-plan['reference_video_segment'][0]==t*rows and plan['signature'][1:]==[t,46,82,shapes['audio'][-1]] and plan['reference_image_segments']==[])
  checks[arm+'_sampled_finite']=all(x.get('sampled_finite',True) for x in router['forward_summaries'])
  m,files,prefix=inspect_capture(root/'audit/x0'/run,run,grid,row['seed'],case);manifests[arm]=m
  pair_id=f'r123_{source}_seed2026101701';cache=root/'audit'/f'{pair_id}_noise.pt';saved=torch.load(cache,map_location='cpu',weights_only=True)
  hashes=[{k:signature(t)[k] for k in ('shape','dtype','sha256')} for t in saved['tensors']]
  checks[arm+'_actual_noise_cache']=(n['run_id']==run and n['pair_id']==pair_id and n['signature']['seed']==row['seed'] and len(hashes)==2 and [tuple(x.shape) for x in saved['tensors']]==[shapes[k] for k in ('video','audio')] and saved['signature']==n['signature'] and saved['hashes']==hashes==n['actual_noise_streams'])
  parent_noise=read(root/'configs/parent_noise.json')
  checks[arm+'_registered_initial_noise_equal']=(sha(cache)==parent_noise['source_sha256'] and hashes==parent_noise['actual_noise_streams'] and n['signature']==parent_noise['signature'])
  video=output_file(root,hist);properties=video_properties(video,case)
  result['runs'][arm]={'run_id':run,'video':{'file':str(video),'sha256':sha(video),'properties':properties},'valid_frames':case['valid_frame_count'],'evaluation_crop_xywh':case['evaluation_crop_xywh'],'NFE':20,'Euler_updates':20,'routed_blocks':router['routed_calls'],'job_wall_seconds':job['observed_unix']-job['submitted_unix'],'snapshots':files,'capture_seconds':sum(x['capture_seconds'] for x in m['captures']),'router_file_sha256':sha(root/'audit/router'/f'{run}.json'),'history_sha256':sha(root/'logs'/f'{run}_history.json'),'job_sha256':sha(root/'logs'/f'{run}_job.json')}
  result['runs'][arm]['task_scope']=case.get('task_scope');result['runs'][arm]['evaluation_scope']=case.get('evaluation_scope')
  result['runs'][arm]['binding_artifacts']={str(p.relative_to(root)):sha(p) for p in (root/'configs/graphs'/f'{run}.json',root/'logs'/f'{run}_history.json',root/'logs'/f'{run}_job.json',root/'audit'/f'{run}_conditioning.json',root/'audit'/f'{run}_noise.json',shared,cache,root/'audit/x0'/run/'manifest.json')}
  del prefix,saved
 if not native_only:
  checks['actual_clean_conditions_equal']=semantic_condition(conditions['native'])==semantic_condition(conditions['forced'])
  checks['actual_initial_AV_noise_equal']=(noises['native']['signature']==noises['forced']['signature'] and noises['native']['actual_noise_streams']==noises['forced']['actual_noise_streams'] and checks['native_actual_noise_cache'] and checks['forced_actual_noise_cache'])
  prefix_results=[]
  for i in range(6):
   a,_=checked_snapshot(root/'audit/x0'/pair[0],manifests['native']['captures'][i],pair[0],latent_shapes(jobs[pair[0]]['case']));b,_=checked_snapshot(root/'audit/x0'/pair[1],manifests['forced']['captures'][i],pair[1],latent_shapes(jobs[pair[1]]['case']));prefix_results.append({'step_zero_based':i,**{k:torch.equal(a[k],b[k]) for k in ('video','audio')}})
  checks['Native_prefix_0_5_equal']=all(row[k] for row in prefix_results for k in ('video','audio'));result['prefix_tensor_comparison']=prefix_results
 result['passed']=all(checks.values());return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',choices=SOURCES,required=True);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--native-only',action='store_true');a=p.parse_args();dest=a.root/'analysis/postrun'/a.source/('NATIVE_RUNTIME_GATE.json' if a.native_only else 'PAIR_RUNTIME_GATE.json')
 try:
  result=verify(a.root,a.source,a.native_only);result=persist_gate(dest,result)
 except BaseException as e:
  atomic(dest.with_name(dest.stem+'_FAILURE.json'),{'schema':'r123-pair-verifier-error-v1','passed':False,'source_id':a.source,'error':repr(e),'unix':time.time()});raise
 print(json.dumps({'receipt':str(dest),'sha256':sha(dest),'passed':result['passed'],'checks':result['checks']},indent=2))
 if not result['passed']:raise SystemExit(2)
if __name__=='__main__':main()
