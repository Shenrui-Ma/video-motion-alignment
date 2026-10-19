"""CPU actual-output verifier, one fresh P0/P1 Native pair. Quality is assessed separately."""
import argparse,copy,json,os,subprocess,sys,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import torch
from capture_checks import inspect_capture,checked_snapshot,inspect_blob,condition_files,signature,expected_routing
from r72_contract import read,sha,require,registry,validate_job,SOURCES,GEOMETRY,SHAPES,prompt_pair_condition_checks
from execution_gate import atomic

def semantic_condition(c):
 return {k:v for k,v in c.items() if k!='run_id'}

def walk_blobs(value):
 if isinstance(value,dict):
  if 'tensor_file' in value:yield value
  for v in value.values():yield from walk_blobs(v)
 elif isinstance(value,list):
  for v in value:yield from walk_blobs(v)

def reference_geometry_matches(c,case,plan):
 """Check both reference modalities and the actual packed layout for this target image."""
 image=case['reference_image_expected'];w,h=image['expected_native_ref_image_size_match_width_height']
 image_shape=image['expected_clean_reference_latent_shape'];tokens=image['expected_DiT_visual_patch_tokens']
 calls=c['native_vae_calls'];require(len(calls)==2,'expected image then video VAE calls')
 shapes_ok=(calls[0]['prepared_frames']['shape']==[1,h,w,3] and calls[0]['latent']['shape']==image_shape and calls[1]['prepared_frames']['shape']==[158,768,1152,3] and calls[1]['latent']['shape']==list(SHAPES['video']) and c['target_latent_shapes']==[list(SHAPES[k]) for k in ('video','audio')])
 actual=c['pair_snapshot']['actual'];refs=actual['references']
 shapes_ok=shapes_ok and [x['kind'] for x in refs]==['image','video'] and [x['clean_latent']['shape'] for x in refs]==[image_shape,list(SHAPES['video'])] and actual['target_latent_shapes']==c['target_latent_shapes']
 segments=c['packed_layout']['segments'];require(len(segments)==5,'unexpected silent image+video packed layout')
 sizes=[segments[0][1],tokens,40608,526,40608];labels=['text','ref_img','ref_img','audio','video'];offset=0;expected=[]
 for size,label in zip(sizes,labels):expected.append([offset,offset+size,label]);offset+=size
 layout_ok=(segments[0][0]==0 and segments[0][1]>0 and segments==expected and c['packed_layout']['seq_len']==offset and actual['packed_layout']['segments']==segments and actual['packed_layout']['seq_len']==offset and plan['reference_image_segments']==[segments[1][:2]] and plan['reference_video_segment']==segments[2][:2] and plan['target_video_segment']==segments[4][:2])
 return shapes_ok and layout_ok

def output_file(root,history):
 images=history['outputs']['14']['images'];require(len(images)==1,'expected one final video')
 record=images[0];require(record.get('type')=='output','final file is not in output')
 rel=Path(record.get('subfolder',''))/record['filename'];require(not rel.is_absolute() and '..' not in rel.parts,'unsafe final video path')
 file=root/'output'/rel;require(file.is_file() and not file.is_symlink(),'final video missing')
 return file

def video_properties(path):
 result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames','-of','json',str(path)],capture_output=True,text=True,timeout=120,check=True)
 streams=json.loads(result.stdout)['streams'];require(len(streams)==1,'expected exactly one video stream');s=streams[0]
 require(s['width']==1152 and s['height']==768 and int(s['nb_read_frames'])==158 and s['avg_frame_rate']=='24/1','final geometry/frame count/fps differs')
 return s

def verify(root,source):
 torch.set_num_threads(1);root=Path(root).resolve();require(source in SOURCES,'unknown source');jobs,order=registry(root)
 runtime=read(root/'configs/runtime.json');runtime_sha=sha(root/'configs/runtime.json');seal=read(root/'deploy_manifest.json')
 checks={};checks['producer_seal']=all(sha(root/p)==v['sha256'] for p,v in seal['files'].items())
 owner=read(root/'processes/service.json');checks['actual_runtime_device']=(owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port'])
 pair=[run for run in order if jobs[run]['source_id']==source];require(len(pair)==2,'paired registry differs')
 result={'schema':'r72-paired-runtime-gate-v1','source_id':source,'prompt_versions':['P0','P1'],'runtime_profile_sha256':runtime_sha,'runtime_profile':runtime,'checks':checks,'runs':{},'created_unix':time.time(),'quality_assessment':'separate official MF and human edit/motion assessment','condition_tensor_files':[]}
 conditions={};noises={};manifests={};seen=set()
 for run in pair:
  row=validate_job(run,root);arm=row['arm'];case=row['case'];forced=False;graph=read(root/'configs/graphs'/f'{run}.json');grid=torch.tensor([float(x) for x in graph['9']['inputs']['sigmas'].split(',')],dtype=torch.float32).tolist()
  hist=read(root/'logs'/f'{run}_history.json');job=read(root/'logs'/f'{run}_job.json')
  checks[arm+'_history']=(hist['status']['completed'] is True and hist['status']['status_str']=='success' and hist['prompt'][2]==graph and hist['prompt'][1]==job['prompt_id'] and job['status']=='success' and job['name']==run)
  checks[arm+'_service']=(job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'] and job['graph_sha256']==row['graph_sha256'])
  c=read(root/'audit'/f'{run}_conditioning.json');n=read(root/'audit'/f'{run}_noise.json');conditions[arm]=c;noises[arm]=n
  shared=root/'audit'/(case['reference_cache_id']+'_conditioning.json');shared_value=read(shared)
  checks[arm+'_shared_conditions']=(c['run_id']==run and c['pair_snapshot']['verified'] is True and c['pair_snapshot']['source_run_id']==case['reference_cache_id'] and c['pair_snapshot']['source_manifest_sha256']==sha(shared) and c['prompt']==case['prompt'])
  require(len(condition_files(c))==8,'expected eight condition tensor blobs')
  for record in walk_blobs(shared_value):
   if record['tensor_file'] not in seen:
    seen.add(record['tensor_file']);result['condition_tensor_files'].append(inspect_blob(root/'audit',record))
  router=read(root/'audit/router'/f'{run}.json');expect={'run_id':run,'mode':'mass_preserve' if forced else 'native','alpha':1.,'radius':0,'time_offset':0,'block_interval_half_open':[0,50],'step_interval_half_open':[6,15] if forced else [0,20],'pixel_interval_inclusive':[0,146],'started_calls':1000,'completed_calls':1000,'completed_forward_calls':20,'native_override_calls':1000,'routed_calls':450 if forced else 0,'calls_by_forward':[50]*20,'calls_by_block':[20]*50,'routed_by_forward':expected_routing(forced),'routed_by_block':[9 if forced else 0]*50,'sample_sigmas':grid,'expected_sampling_steps':20}
  checks[arm+'_actual_execution_counts']=all(router.get(k)==v for k,v in expect.items())
  plan=router['validated_layout'];seq=c['packed_layout']['seq_len']
  checks[arm+'_actual_layout']=(router['first_attention']['qkv_shape']==[1,56,seq,128] and plan['frame_rows']==864 and plan['latent_interval_half_open']==[0,44] and plan['position_bin_coverage_inclusive']==[0,148] and plan['query_interval_half_open']==[plan['target_video_segment'][0],plan['target_video_segment'][0]+44*864] and plan['key_interval_half_open']==[plan['reference_video_segment'][0],plan['reference_video_segment'][0]+44*864] and len(plan['reference_image_segments'])==1)
  checks[arm+'_reference_geometry']=reference_geometry_matches(c,case,plan)
  checks[arm+'_sampled_finite']=all(x.get('sampled_finite',True) for x in router['forward_summaries'])
  m,files,prefix=inspect_capture(root/'audit/x0'/run,run,grid,row['seed']);manifests[arm]=m
  pair_id=f'r72_{source}_seed2026101701';cache=root/'audit'/f'{pair_id}_noise.pt';saved=torch.load(cache,map_location='cpu',weights_only=True)
  hashes=[{k:signature(t)[k] for k in ('shape','dtype','sha256')} for t in saved['tensors']]
  checks[arm+'_actual_noise_cache']=(n['run_id']==run and n['pair_id']==pair_id and n['signature']['seed']==row['seed'] and len(hashes)==2 and [x['shape'] for x in hashes]==[list(SHAPES[k]) for k in ('video','audio')] and n['signature'].get('nested') is True and saved['signature']==n['signature'] and saved['hashes']==hashes==n['actual_noise_streams'])
  video=output_file(root,hist);properties=video_properties(video)
  result['runs'][arm]={'run_id':run,'video':{'file':str(video),'sha256':sha(video),'properties':properties},'valid_frames':case['valid_frame_count'],'evaluation_crop_xywh':case['evaluation_crop_xywh'],'evaluation_indices':case['evaluation_indices'],'evaluation_fps':8,'NFE':20,'Euler_updates':20,'routed_blocks':router['routed_calls'],'job_wall_seconds':job['observed_unix']-job['submitted_unix'],'snapshots':files,'capture_seconds':sum(x['capture_seconds'] for x in m['captures']),'router_file_sha256':sha(root/'audit/router'/f'{run}.json'),'history_sha256':sha(root/'logs'/f'{run}_history.json'),'job_sha256':sha(root/'logs'/f'{run}_job.json')}
  del prefix,saved
 checks.update(prompt_pair_condition_checks(conditions['p0'],conditions['p1']))
 checks['actual_initial_AV_noise_equal']=(noises['p0']['signature']==noises['p1']['signature'] and noises['p0']['actual_noise_streams']==noises['p1']['actual_noise_streams'] and checks['p0_actual_noise_cache'] and checks['p1_actual_noise_cache'])
 checks['independent_prompt_conditioning']=(conditions['p0']['prompt']!=conditions['p1']['prompt'] and conditions['p0']['pair_snapshot']['source_run_id']!=conditions['p1']['pair_snapshot']['source_run_id'] and conditions['p0']['conditioning_embedding']['sha256']!=conditions['p1']['conditioning_embedding']['sha256'])
 result['between_arm_comparison']={'equal_required':['original image/video bytes','input_video','native_vae_calls','qwen_presentation RGB/timestamps before encoding','target_latent_shapes','actual AV noise'], 'may_differ':['joint Qwen text/visual conditioning_embedding','tokenization_before_vision_expansion','token_tags','packed positions and sequence length','all x0 predictions'], 'x0_prefix_equality_required':False}
 result['passed']=all(checks.values());return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',choices=SOURCES,required=True);p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();dest=a.root/'analysis/postrun'/a.source/'PAIR_RUNTIME_GATE.json'
 try:result=verify(a.root,a.source)
 except BaseException as e:
  atomic(dest.with_name('PAIR_RUNTIME_GATE_FAILURE.json'),{'schema':'r72-pair-verifier-error-v1','passed':False,'source_id':a.source,'error':repr(e),'unix':time.time()});raise
 atomic(dest,result);print(json.dumps({'receipt':str(dest),'sha256':sha(dest),'passed':result['passed'],'checks':result['checks']},indent=2))
 if not result['passed']:raise SystemExit(2)
if __name__=='__main__':main()
