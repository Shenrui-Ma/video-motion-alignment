"""Actual two-solver Native gate. Execution comparability is separate from quality."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import torch
from capture_checks import inspect_capture,inspect_blob,condition_files,signature
from r106_contract import read,sha,require,registry,validate_job,SOURCES,ARMS,RUNS,GEOMETRY,SHAPES,PAIR_ID,SHARED_ID,VALID
from execution_gate import atomic

def walk_blobs(value):
 if isinstance(value,dict):
  if 'tensor_file' in value:yield value
  for v in value.values():yield from walk_blobs(v)
 elif isinstance(value,list):
  for v in value:yield from walk_blobs(v)

def reference_geometry_matches(c,case,plan):
 calls=c['native_vae_calls'];require(len(calls)==1,'expected one video VAE call')
 actual=c['pair_snapshot']['actual'];refs=actual['references']
 shapes_ok=(calls[0]['prepared_frames']['shape']==[107,736,1312,3] and calls[0]['latent']['shape']==list(SHAPES['video']) and c['target_latent_shapes']==[list(SHAPES[k]) for k in ('video','audio')] and [x['kind'] for x in refs]==['video'] and [x['clean_latent']['shape'] for x in refs]==[list(SHAPES['video'])] and actual['target_latent_shapes']==c['target_latent_shapes'])
 segments=c['packed_layout']['segments'];require(len(segments)==4,'expected text/video-reference/audio/target-video segments')
 sizes=[segments[0][1],30176,356,30176];labels=['text','ref_img','audio','video'];offset=0;expected=[]
 for size,label in zip(sizes,labels):expected.append([offset,offset+size,label]);offset+=size
 layout_ok=(segments[0][0]==0 and segments[0][1]>0 and segments==expected and c['packed_layout']['seq_len']==offset and actual['packed_layout']['segments']==segments and actual['packed_layout']['seq_len']==offset and plan['reference_image_segments']==[] and plan['reference_video_segment']==segments[1][:2] and plan['target_video_segment']==segments[3][:2])
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
 require(s['width']==1312 and s['height']==736 and int(s['nb_read_frames'])==107 and s['avg_frame_rate']=='24/1','final geometry/frame count/fps differs')
 return s


def semantic_condition(c):return {k:v for k,v in c.items() if k!='run_id'}

def compare_prefix(left,right):
    checks={}
    for step in (0,1):
        for kind,keys in [('raw',('state_video','state_audio','prediction_video','prediction_audio')),('normalized',('video','audio'))]:
            for key in keys:checks[f'step{step}_{kind}_{key}']=torch.equal(left[step][kind][key],right[step][kind][key])
    return checks

def verify(root=ROOT):
    torch.set_num_threads(1);root=Path(root).resolve();jobs,order=registry(root)
    runtime=read(root/'configs/runtime.json');seal=read(root/'deploy_manifest.json');owner=read(root/'processes/service.json')
    checks={'producer_seal':all(sha(root/p)==v['sha256'] for p,v in seal['files'].items()),'actual_runtime_device':owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port']}
    shared=root/'audit'/(SHARED_ID+'_conditioning.json');source_condition=read(shared)
    require(len(condition_files(source_condition))==6,'six shared condition tensors required')
    blob_files=[];seen=set()
    for record in walk_blobs(source_condition):
        if record['tensor_file'] not in seen:seen.add(record['tensor_file']);blob_files.append(inspect_blob(root/'audit',record))
    noise_file=root/'audit'/(PAIR_ID+'_noise.pt');saved=torch.load(noise_file,map_location='cpu',weights_only=True)
    actual_noise=[{k:signature(t)[k] for k in ('shape','dtype','sha256')} for t in saved['tensors']]
    checks['raw_noise_geometry']=len(actual_noise)==2 and [v['shape'] for v in actual_noise]==[list(SHAPES[k]) for k in ('video','audio')] and actual_noise==saved['hashes']
    results={};prefixes={};conditions={};manifests={};noise_manifests={}
    for arm,run in zip(ARMS,RUNS):
        row=validate_job(run,root);case=row['case'];graph=read(root/'configs/graphs'/(run+'.json'))
        grid=torch.tensor([float(x) for x in graph['9']['inputs']['sigmas'].split(',')],dtype=torch.float32).tolist()
        hist=read(root/'logs'/(run+'_history.json'));job=read(root/'logs'/(run+'_job.json'))
        checks[arm+'_history']=hist['status']['completed'] is True and hist['status']['status_str']=='success' and hist['prompt'][2]==graph and hist['prompt'][1]==job['prompt_id'] and job['status']=='success' and job['name']==run
        checks[arm+'_generation']=job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'] and job['graph_sha256']==row['graph_sha256']
        c=read(root/'audit'/(run+'_conditioning.json'));n=read(root/'audit'/(run+'_noise.json'));conditions[arm]=c;noise_manifests[arm]=n
        checks[arm+'_actual_conditions']=c['run_id']==run and c['pair_snapshot']['verified'] is True and c['pair_snapshot']['source_run_id']==SHARED_ID and c['pair_snapshot']['source_manifest_sha256']==sha(shared) and c['prompt']==case['prompt'] and condition_files(c)==condition_files(source_condition)
        checks[arm+'_actual_noise']=n['run_id']==run and n['pair_id']==PAIR_ID and n['signature']==saved['signature'] and n['actual_noise_streams']==actual_noise
        router=read(root/'audit/router'/(run+'.json'))
        expect={'run_id':run,'mode':'native','alpha':1.,'radius':0,'time_offset':0,'block_interval_half_open':[0,50],'step_interval_half_open':[6,15],'pixel_interval_inclusive':[0,97],'started_calls':1000,'completed_calls':1000,'completed_forward_calls':20,'native_override_calls':1000,'routed_calls':0,'calls_by_forward':[50]*20,'calls_by_block':[20]*50,'routed_by_forward':[0]*20,'routed_by_block':[0]*50,'sample_sigmas':grid,'expected_sampling_steps':20}
        checks[arm+'_20calls_0routes']=all(router.get(k)==v for k,v in expect.items())
        plan=router['validated_layout'];seq=c['packed_layout']['seq_len']
        checks[arm+'_layout']=router['first_attention']['qkv_shape']==[1,56,seq,128] and plan['frame_rows']==943 and plan['latent_interval_half_open']==[0,29] and plan['position_bin_coverage_inclusive']==[0,97] and len(plan['reference_image_segments'])==0
        checks[arm+'_reference_geometry']=reference_geometry_matches(c,case,plan)
        checks[arm+'_finite']=all(x.get('sampled_finite',True) for x in router['forward_summaries'])
        manifest,files,prefix=inspect_capture(root/'audit/x0'/run,run,grid,row['seed'],case['sampler_function']);prefixes[arm]=prefix;manifests[arm]=manifest
        video=output_file(root,hist);properties=video_properties(video)
        results[arm]={'run_id':run,'solver':arm,'sampler_function':manifest['sampler'],'video':{'file':str(video),'sha256':sha(video),'properties':properties},'NFE':20,'solver_updates':20,'routed_blocks':0,'valid_frames':VALID,'evaluation_indices':list(range(VALID)),'job_wall_seconds':job['observed_unix']-job['submitted_unix'],'capture_seconds':sum(x['capture_seconds'] for x in manifest['captures']),'snapshots':files,'history_sha256':sha(root/'logs'/(run+'_history.json')),'conditioning_sha256':sha(root/'audit'/(run+'_conditioning.json')),'noise_sha256':sha(root/'audit'/(run+'_noise.json')),'router_sha256':sha(root/'audit/router'/(run+'.json')),'capture_manifest_sha256':sha(root/'audit/x0'/run/'manifest.json')}
    checks['same_complete_conditions']=semantic_condition(conditions['euler'])==semantic_condition(conditions['res_multistep'])
    checks['same_raw_noise']=noise_manifests['euler']['signature']==noise_manifests['res_multistep']['signature'] and noise_manifests['euler']['actual_noise_streams']==noise_manifests['res_multistep']['actual_noise_streams']
    checks['same_actual_sigmas']=manifests['euler']['sigmas_video']==manifests['res_multistep']['sigmas_video']
    prefix_checks=compare_prefix(prefixes['euler'],prefixes['res_multistep']);checks.update(prefix_checks)
    later=[]
    for a,b in zip(manifests['euler']['captures'][2:],manifests['res_multistep']['captures'][2:]):
        later.append({'step_zero_based':a['step_zero_based'],'normalized_video_equal':a['video']['sha256']==b['video']['sha256'],'normalized_audio_equal':a['audio']['sha256']==b['audio']['sha256']})
    return {'schema':'r106-fresh-native-solver-pair-runtime-gate-v1','passed':all(checks.values()),'checks':checks,'service_owner':owner,'source_id':SOURCES[0],'runs':results,'runtime_profile':runtime,'runtime_profile_sha256':sha(root/'configs/runtime.json'),'producer_seal_sha256':sha(root/'deploy_manifest.json'),'valid_frames':VALID,'evaluation_indices':list(range(VALID)),'evaluation_crop_xywh':[16,8,1280,720],'frame_rate':24,'condition_tensor_files':blob_files,'noise_cache':{'file':str(noise_file),'sha256':sha(noise_file)},'equal_prefix_steps':[0,1],'post_prefix_observation':later,'quality_assessment':'pending root visual and separate temporal event measurement','created_unix':time.time()}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();dest=a.root/'analysis/postrun/PAIR_RUNTIME_GATE.json'
 try:result=verify(a.root)
 except BaseException as error:atomic(dest.with_name('PAIR_RUNTIME_GATE_FAILURE.json'),{'passed':False,'error':repr(error),'unix':time.time()});raise
 atomic(dest,result);print(json.dumps({'receipt':str(dest),'sha256':sha(dest),'passed':result['passed'],'checks':result['checks']},indent=2))
 if not result['passed']:raise SystemExit(2)
