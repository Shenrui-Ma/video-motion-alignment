"""CPU actual single-output gate: identical fixed prefix0..14, extension first at15."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import torch
from capture_checks import inspect_capture,checked_snapshot,inspect_blob,condition_files,signature
from r97_contract import read,sha,require,registry,validate_job,GEOMETRY,SHAPES,RUN_ID,routing_layout
from parent_evidence import verify_parent,comparable_conditions
from execution_gate import atomic

def walk_blobs(value):
 if isinstance(value,dict):
  if 'tensor_file' in value:yield value
  for v in value.values():yield from walk_blobs(v)
 elif isinstance(value,list):
  for v in value:yield from walk_blobs(v)
def output_file(root,hist):
 images=hist['outputs']['14']['images'];require(len(images)==1,'expected one outputvideo');r=images[0]
 require(r.get('type')=='output','wrong output type');rel=Path(r.get('subfolder',''))/r['filename']
 require(not rel.is_absolute() and '..' not in rel.parts,'unsafe output path');p=root/'output'/rel
 require(p.is_file() and not p.is_symlink(),'output absent');return p

def compare_prefix(current_folder,current_manifest,current_run,parent_folder,parent_manifest,parent_run,shapes=SHAPES):
 results=[]
 for i in range(15):
  a,af=checked_snapshot(current_folder,current_manifest['captures'][i],current_run,shapes)
  b,bf=checked_snapshot(parent_folder,parent_manifest['captures'][i],parent_run,shapes)
  require(a['metadata']['step_zero_based']==b['metadata']['step_zero_based']==i and a['metadata']['model_call_one_based']==b['metadata']['model_call_one_based']==i+1,'prefix prediction index mismatch')
  results.append({'step_zero_based':i,'model_call_one_based':i+1,'video':torch.equal(a['video'],b['video']),'audio':torch.equal(a['audio'],b['audio']),'current_file_sha256':af['sha256'],'parent_file_sha256':bf['sha256']})
 return results

def verify(root=ROOT):
 root=Path(root).resolve();torch.set_num_threads(1);row=validate_job(RUN_ID,root);case=row['case'];b=read(root/'configs/parent_bindings.json');prior=Path(b['parent_root']);oldrun=b['parent_run']
 parent_proof=verify_parent(root,include_snapshots=True);parent_gate=read(root/'design/R89_ACTUAL/PAIR_RUNTIME_GATE.json')
 checks={};runtime=read(root/'configs/runtime.json');seal=read(root/'deploy_manifest.json');checks['producer_seal']=all(sha(root/p)==v['sha256'] for p,v in seal['files'].items())
 runtime_keys=('host','gpu_uuid','core','python','dependencies','models','kj_nodes','reserve_vram','memory_mode')
 checks['same_host_numerical_runtime']=all(runtime[k]==parent_gate['runtime_profile'][k] for k in runtime_keys)
 owner=read(root/'processes/service.json');checks['actual_runtime_device']=owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port']
 graph=read(root/'configs/graphs'/(RUN_ID+'.json'));grid=torch.tensor([float(x) for x in graph['9']['inputs']['sigmas'].split(',')],dtype=torch.float32).tolist()
 hist=read(root/'logs'/(RUN_ID+'_history.json'));job=read(root/'logs'/(RUN_ID+'_job.json'))
 checks['actual_history']=(hist['status']['completed'] is True and hist['status']['status_str']=='success' and hist['prompt'][2]==graph and hist['prompt'][1]==job['prompt_id'] and job['status']=='success' and job['name']==RUN_ID)
 checks['actual_service_generation']=(job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'] and job['graph_sha256']==row['graph_sha256'])
 c=read(root/'audit'/(RUN_ID+'_conditioning.json'));oldc=read(prior/'audit'/(oldrun+'_conditioning.json'));shared=root/'audit/r97_short_0358_shared_conditioning.json'
 checks['actual_condition_snapshot']=(c['run_id']==RUN_ID and c['pair_snapshot']['verified'] is True and c['pair_snapshot']['source_run_id']=='r97_short_0358_shared' and c['pair_snapshot']['source_manifest']=='r97_short_0358_shared_conditioning.json' and c['pair_snapshot']['source_manifest_sha256']==sha(shared) and c['prompt']==case['prompt'])
 checks['all_conditions_equal_R89_fixed']=comparable_conditions(c,oldc)
 require(len(condition_files(c))==6,'expected six condition blobs');blob_files=[];seen=set()
 for record in walk_blobs(read(shared)):
  if record['tensor_file'] not in seen:seen.add(record['tensor_file']);blob_files.append(inspect_blob(root/'audit',record))
 checks['historical_condition_blob_files_unchanged']=all(sha(Path(x['file']))==x['sha256'] for x in parent_gate['condition_tensor_files'])
 router=read(root/'audit/router'/(RUN_ID+'.json'))
 expect={'run_id':RUN_ID,'mode':'mass_preserve','alpha':1.,'radius':0,'time_offset':0,'block_interval_half_open':[0,50],'step_interval_half_open':[6,20],'pixel_interval_inclusive':[0,104],'started_calls':1000,'completed_calls':1000,'completed_forward_calls':20,'native_override_calls':1000,'routed_calls':700,'calls_by_forward':[50]*20,'calls_by_block':[20]*50,'routed_by_forward':[0]*6+[50]*14,'routed_by_block':[14]*50,'sample_sigmas':grid,'expected_sampling_steps':20}
 checks['actual20NFE20Euler700routes']=all(router.get(k)==v for k,v in expect.items())
 plan=router['validated_layout'];oldrouter=read(prior/'audit/router'/(oldrun+'.json'));route=routing_layout(case)
 checks['same_actual_layout_R89_fixed']=(plan==oldrouter['validated_layout'] and router['first_attention']==oldrouter['first_attention'])
 checks['valid_physical_support']=(plan['frame_rows']==943 and plan['latent_interval_half_open']==route['latent_interval_half_open'] and plan['position_bin_coverage_inclusive']==route['position_bin_coverage_inclusive'] and plan['pixel_interval_inclusive']==[0,104] and plan['reference_image_segments']==[])
 checks['sampled_finite']=all(x.get('sampled_finite',True) for x in router['forward_summaries'])
 manifest,files,prefix=inspect_capture(root/'audit/x0'/RUN_ID,RUN_ID,grid,row['seed'],case);del prefix
 oldmanifest=read(prior/'audit/x0'/oldrun/'manifest.json');checks['same_sampler_grid_and_initial_packed_noise']=(manifest['noise']==oldmanifest['noise'] and manifest['sigmas_video']==oldmanifest['sigmas_video'] and [c['sigma_audio'] for c in manifest['captures']]==[c['sigma_audio'] for c in oldmanifest['captures']])
 comparisons=compare_prefix(root/'audit/x0'/RUN_ID,manifest,RUN_ID,prior/'audit/x0'/oldrun,oldmanifest,oldrun)
 checks['AV_prediction_prefix_0_14_bitwise_equal']=all(r[k] for r in comparisons for k in ('video','audio'))
 n=read(root/'audit'/(RUN_ID+'_noise.json'));oldn=read(prior/'audit'/(oldrun+'_noise.json'));noise=root/b['new_noise_relative'];saved=torch.load(noise,map_location='cpu',weights_only=True)
 actual=[{k:signature(t)[k] for k in ('shape','dtype','sha256')} for t in saved['tensors']]
 checks['actual_raw_AV_noise_equal_R89_fixed']=(sha(noise)==b['noise_cache_sha256'] and n['run_id']==RUN_ID and n['pair_id']=='r97_short_0358_seed2026101701' and saved['signature']==n['signature']==oldn['signature'] and actual==saved['hashes']==n['actual_noise_streams']==oldn['actual_noise_streams'] and [list(t.shape) for t in saved['tensors']]==[list(SHAPES[k]) for k in ('video','audio')]);del saved
 video=output_file(root,hist);v=json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames','-of','json',str(video)],capture_output=True,text=True,timeout=120,check=True).stdout)['streams'];require(len(v)==1,'onevideo required');v=v[0]
 checks['output_geometry']=(v['width']==1312 and v['height']==736 and v['avg_frame_rate']=='24/1' and int(v['nb_read_frames'])==107)
 return {'schema':'r97-schedule-control-runtime-gate-v1','passed':all(checks.values()),'checks':checks,'run_id':RUN_ID,'source_id':'short_0358','prompt_version':'P1-local-v1','parent_evidence':parent_proof,'parent_fixed_video':b['parent_video'],'runtime_profile':runtime,'runtime_profile_sha256':sha(root/'configs/runtime.json'),'video':{'file':str(video),'sha256':sha(video),'properties':v},'valid_frames':105,'evaluation_crop_xywh':[16,8,1280,720],'NFE':20,'Euler_updates':20,'routed_blocks':700,'job_wall_seconds':job['observed_unix']-job['submitted_unix'],'capture_seconds':sum(x['capture_seconds'] for x in manifest['captures']),'snapshots':files,'condition_tensor_files':blob_files,'prefix_tensor_comparison':comparisons,'first_allowed_prediction_divergence_index':15,'quality_assessment':'Three preregistered manual events, eyeglasses/identity/scene and artefacts; descriptive control only.','created_unix':time.time()}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();dest=a.root/'analysis/postrun/CONTROL_RUNTIME_GATE.json'
 try:result=verify(a.root)
 except BaseException as e:atomic(dest.with_name('CONTROL_RUNTIME_GATE_FAILURE.json'),{'passed':False,'error':repr(e),'unix':time.time()});raise
 atomic(dest,result);print(json.dumps({'receipt':str(dest),'sha256':sha(dest),'passed':result['passed'],'checks':result['checks']},indent=2))
 if not result['passed']:raise SystemExit(2)
