"""CPU actual-output verifier, single P1 Native with actual R85 P0 inputs/noise. Quality is assessed separately."""
import argparse,copy,json,os,subprocess,sys,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import torch
from capture_checks import inspect_capture,checked_snapshot,inspect_blob,condition_files,signature,expected_routing
from r90_contract import read,sha,require,registry,validate_job,SOURCES,GEOMETRY,SHAPES,RUN_ID
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

def compare_parent_conditions(current,previous):
    """Text-conditioned embeddings/layout may differ; actual visual input and clean latents must match."""
    a=current['pair_snapshot']['actual'];b=previous['pair_snapshot']['actual']
    return {'original_input_pixels':current['input_video']==previous['input_video'],
            'actual_prepared_RGB_and_clean_VAE':current['native_vae_calls']==previous['native_vae_calls'],
            'actual_reference_snapshot':a['references']==b['references'],
            'Qwen_visual_sampling':current['qwen_presentation']==previous['qwen_presentation'],
            'target_shapes_and_dtype':a['target_latent_shapes']==b['target_latent_shapes'] and a['target_latent_dtypes']==b['target_latent_dtypes']}

def verify(root=ROOT):
    torch.set_num_threads(1);root=Path(root).resolve();jobs,order=registry(root);run=RUN_ID;row=validate_job(run,root);case=row['case'];arm='native'
    runtime=read(root/'configs/runtime.json');bindings=read(root/'configs/parent_bindings.json');oldroot=Path(bindings['r85_root']);oldrun=bindings['r85_run']
    seal=read(root/'deploy_manifest.json');checks={}
    checks['producer_seal']=all(sha(root/p)==v['sha256'] for p,v in seal['files'].items())
    owner=read(root/'processes/service.json');checks['actual_runtime_device']=owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port']
    parent_files={'service.json':'processes/service.json','PAIR_RUNTIME_GATE.json':'analysis/postrun/one_leg__movie_man_9/PAIR_RUNTIME_GATE.json',oldrun+'_job.json':'logs/'+oldrun+'_job.json',oldrun+'_history.json':'logs/'+oldrun+'_history.json',oldrun+'_conditioning.json':'audit/'+oldrun+'_conditioning.json',oldrun+'_noise.json':'audit/'+oldrun+'_noise.json'}
    checks['actual_parent_evidence_unchanged']=all(sha(oldroot/path)==bindings['actual_record_sha256'][name] for name,path in parent_files.items())
    parent=read(oldroot/'audit'/(oldrun+'_conditioning.json'));parent_noise=read(oldroot/'audit'/(oldrun+'_noise.json'));parent_gate=read(oldroot/'analysis/postrun/one_leg__movie_man_9/PAIR_RUNTIME_GATE.json')
    require(parent_gate['passed'] is True and parent_gate['runs']['native']['run_id']==oldrun,'actual parent gate is incomplete')
    parent_runtime=parent_gate['runtime_profile']
    # Profile labels/ports/paths legitimately differ; all numerical runtime dependencies agree.
    runtime_keys=('host','gpu_uuid','core','python','dependencies','models','kj_nodes','reserve_vram','memory_mode')
    checks['same_host_numerical_runtime']=all(runtime[k]==parent_runtime[k] for k in runtime_keys)
    graph=read(root/'configs/graphs'/(run+'.json'));grid=torch.tensor([float(x) for x in graph['9']['inputs']['sigmas'].split(',')],dtype=torch.float32).tolist()
    hist=read(root/'logs'/(run+'_history.json'));job=read(root/'logs'/(run+'_job.json'))
    checks['actual_history']=(hist['status']['completed'] is True and hist['status']['status_str']=='success' and hist['prompt'][2]==graph and hist['prompt'][1]==job['prompt_id'] and job['status']=='success' and job['name']==run)
    checks['actual_service_generation']=job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'] and job['graph_sha256']==row['graph_sha256']
    c=read(root/'audit'/(run+'_conditioning.json'));n=read(root/'audit'/(run+'_noise.json'));shared=root/'audit/r90_one_leg__movie_man_9_shared_conditioning.json'
    checks['actual_P1_condition_snapshot']=(c['run_id']==run and c['pair_snapshot']['verified'] is True and c['pair_snapshot']['source_run_id']=='r90_one_leg__movie_man_9_shared' and c['pair_snapshot']['source_manifest_sha256']==sha(shared) and c['prompt']==case['prompt'])
    require(len(condition_files(c))==8,'expected eight actual condition tensors')
    blob_files=[];seen=set()
    for record in walk_blobs(read(shared)):
        if record['tensor_file'] not in seen:seen.add(record['tensor_file']);blob_files.append(inspect_blob(root/'audit',record))
    checks.update(compare_parent_conditions(c,parent))
    router=read(root/'audit/router'/(run+'.json'))
    expect={'run_id':run,'mode':'native','alpha':1.,'radius':0,'time_offset':0,'block_interval_half_open':[0,50],'step_interval_half_open':[0,20],'pixel_interval_inclusive':[0,146],'started_calls':1000,'completed_calls':1000,'completed_forward_calls':20,'native_override_calls':1000,'routed_calls':0,'calls_by_forward':[50]*20,'calls_by_block':[20]*50,'routed_by_forward':[0]*20,'routed_by_block':[0]*50,'sample_sigmas':grid,'expected_sampling_steps':20}
    checks['actual20NFE20Euler0routes']=all(router.get(k)==v for k,v in expect.items())
    plan=router['validated_layout'];seq=c['packed_layout']['seq_len']
    checks['actual_native_layout']=(router['first_attention']['qkv_shape']==[1,56,seq,128] and plan['frame_rows']==864 and plan['latent_interval_half_open']==[0,44] and plan['position_bin_coverage_inclusive']==[0,148] and len(plan['reference_image_segments'])==1)
    checks['actual_reference_geometry']=reference_geometry_matches(c,case,plan)
    checks['sampled_finite']=all(x.get('sampled_finite',True) for x in router['forward_summaries'])
    manifest,files,prefix=inspect_capture(root/'audit/x0'/run,run,grid,row['seed']);del prefix
    noise_file=root/'audit/r90_one_leg__movie_man_9_seed2026101701_noise.pt';saved=torch.load(noise_file,map_location='cpu',weights_only=True)
    actual=[{k:signature(t)[k] for k in ('shape','dtype','sha256')} for t in saved['tensors']]
    checks['actual_noise_cache']=(n['run_id']==run and n['pair_id']=='r90_one_leg__movie_man_9_seed2026101701' and saved['signature']==n['signature'] and len(actual)==2 and [v['shape'] for v in actual]==[list(SHAPES[k]) for k in ('video','audio')] and actual==saved['hashes']==n['actual_noise_streams'])
    checks['raw_initial_AV_noise_matches_R85']=(sha(noise_file)==bindings['noise_cache_sha256']==sha(oldroot/bindings['noise_cache_relative']) and n['signature']==parent_noise['signature'] and actual==parent_noise['actual_noise_streams'])
    del saved
    video=output_file(root,hist);properties=video_properties(video)
    result={'schema':'r90-p1-native-runtime-gate-v1','passed':all(checks.values()),'checks':checks,'run_id':run,'source_id':SOURCES[0],'prompt_version':'P1','runtime_profile_sha256':sha(root/'configs/runtime.json'),'runtime_profile':runtime,'parent_R85_P0_gate_sha256':bindings['actual_record_sha256']['PAIR_RUNTIME_GATE.json'],'video':{'file':str(video),'sha256':sha(video),'properties':properties},'valid_frames':147,'evaluation_indices':list(range(0,147,3)),'NFE':20,'Euler_updates':20,'routed_blocks':0,'job_wall_seconds':job['observed_unix']-job['submitted_unix'],'capture_seconds':sum(x['capture_seconds'] for x in manifest['captures']),'snapshots':files,'condition_tensor_files':blob_files,'changed_text_conditioning':{'parent_shape':parent['conditioning_embedding']['shape'],'current_shape':c['conditioning_embedding']['shape'],'parent_embedding_sha256':parent['conditioning_embedding']['sha256'],'current_embedding_sha256':c['conditioning_embedding']['sha256'],'packed_text_and_position_ids_may_change':True,'x0_equality_required':False},'quality_assessment':'root visual and descriptive physical time evaluation; this gate only establishes execution/input comparability','created_unix':time.time()}
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();dest=a.root/'analysis/postrun/NATIVE_RUNTIME_GATE.json'
    try:result=verify(a.root)
    except BaseException as e:atomic(dest.with_name('NATIVE_RUNTIME_GATE_FAILURE.json'),{'passed':False,'error':repr(e),'unix':time.time()});raise
    atomic(dest,result);print(json.dumps({'receipt':str(dest),'sha256':sha(dest),'passed':result['passed'],'checks':result['checks']},indent=2))
    if not result['passed']:raise SystemExit(2)
