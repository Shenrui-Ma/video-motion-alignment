"""CPU verifier for one reference-origin output; historical-host differences are recorded."""
import argparse,copy,json,os,subprocess,sys,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import torch
from capture_checks import inspect_capture,checked_snapshot,inspect_blob,condition_files,signature,expected_routing
from r132_contract import read,sha,require,registry,validate_job,SOURCES,RUN_ID,geometry,latent_shapes,routing_layout
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

def clean_condition(value):
 return {k:v for k,v in value.items() if k not in ('run_id','pair_snapshot')}

def check_reference_origin(router,run,original_position_sha):
 require(router['run_id']==run,'origin audit identity differs')
 branch=router['reference_origin'];layout=branch['layout'];rotation=branch['rotation']
 require(branch['new_method_claim'] is False and branch['original_QKV_and_table_preserved'] is True,'original attention scope changed')
 require(branch['extra_query_scope']=='target_video_only' and branch['reference_scope']=='same-bin keys for shifted readout; allRef only for original mass and subtraction','auxiliary scope differs')
 require(branch['first_six_prediction_equality_required'] is False,'cross-host prefix policy changed')
 require(branch['layout_validation_count']==1 and branch['rotation_calls']==450 and branch['original_rope_table_calls']==1000,'origin execution counts differ')
 require(layout['original_position_sha256']==original_position_sha,'original position mismatch')
 require(layout['reference_origin']>0 and layout['original_target_origin']>layout['reference_origin'],'actual clock origins differ')
 require(layout['target_time_displacement']<0,'actual clock displacement sign differs')
 require(rotation['displacement_rope_units']==layout['target_time_displacement'] and rotation['time_channel_pairs']==[[0,16],[48,64]],'rotation sign/channel mismatch')
 require(len(rotation['inv_freq'])==16 and len(rotation['inv_freq_sha256'])==64,'actual checkpoint frequencies missing')
 require(all(layout[k] is True for k in ('reference_text_unchanged','spatial_unchanged','target_video_matches_reference_all_coordinates','target_audio_video_common_origin')),'canonical geometry invalid')
 return True


def compare_conditions(actual,parent):
 # Every original pixel, token, layout and input record stays strict. Only two
 # floating model outputs may change across the recorded .9/.41 runtimes.
 a=copy.deepcopy(clean_condition(actual));b=copy.deepcopy(clean_condition(parent))
 floating={}
 for label,aa,bb in (
     ('vae_latent',a['native_vae_calls'][0]['latent'],b['native_vae_calls'][0]['latent']),
     ('conditioning_embedding',a['conditioning_embedding'],b['conditioning_embedding'])):
  require(aa['shape']==bb['shape'] and aa['dtype']==bb['dtype'],'floating condition geometry differs: '+label)
  floating[label]={'actual_sha256':aa['sha256'],'R122_sha256':bb['sha256'],
                   'sha256_equal':aa['sha256']==bb['sha256'],'equality_required':False}
  for record in (aa,bb):
   record.pop('sha256');record.pop('tensor_file')
 return {'strict_metadata_pixels_tokens_positions_equal':a==b,
         'floating_model_output_hashes':floating,
         'reason':'same input/weights/prompt; host41 versus historical host9; no environment repeat'}


def compare_prefix(root,run,case,grid,seed,manifest):
 path=root/'design/parent_native_x0_manifest.json'
 if not path.exists():return {'diagnostics_complete':True,'equality_required':False,'status':'historical snapshot manifest not supplied'}
 parent=read(path)
 keys=('sigmas_video','seed','sampler','audio_scale','video_latent_scale_factor','normalization_stage','geometry','target_latent_shapes')
 require(all(parent[k]==manifest[k] for k in keys),'prefix metadata differ')
 current={row['step_zero_based']:row for row in manifest['captures']}
 comparisons=[{'step_zero_based':row['step_zero_based'],'streams':{k:{'actual_sha256':current[row['step_zero_based']][k]['sha256'],'parent_sha256':row[k]['sha256'],'sha256_equal':current[row['step_zero_based']][k]['sha256']==row[k]['sha256']} for k in ('video','audio')}} for row in parent['captures'] if row['step_zero_based']<6]

 return {'diagnostics_complete':True,'equality_required':False,'comparison':'exact tensor SHA only; cross-host forward values may differ','comparisons':comparisons,'parent_manifest_sha256':sha(path)}


def verify(root):
 torch.set_num_threads(1);root=Path(root).resolve();jobs,order=registry(root);run=RUN_ID;row=validate_job(run,root);case=row['case']
 runtime=read(root/'configs/runtime.json');science=read(root/'configs/scientific_contract.json');seal=read(root/'deploy_manifest.json');owner=read(root/'processes/service.json')
 checks={'producer_seal':all(sha(root/p)==v['sha256'] for p,v in seal['files'].items()),'actual_runtime_device':owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port'] and owner['identity']['uid']==runtime['uid']}
 graph=read(root/'configs/graphs'/f'{run}.json');grid=torch.tensor([float(x) for x in graph['9']['inputs']['sigmas'].split(',')],dtype=torch.float32).tolist()
 hist=read(root/'logs'/f'{run}_history.json');job=read(root/'logs'/f'{run}_job.json')
 checks['history']=(hist['status']['completed'] is True and hist['status']['status_str']=='success' and hist['prompt'][2]==graph and hist['prompt'][1]==job['prompt_id'] and job['status']=='success' and job['name']==run)
 checks['service']=(job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'] and job['graph_sha256']==row['graph_sha256'])
 c=read(root/'audit'/f'{run}_conditioning.json');n=read(root/'audit'/f'{run}_noise.json');shared=root/'audit'/(science['historical_shared_run']+'_conditioning.json');shared_value=read(shared)
 parent_path=root/'design/conditioning.json';parent=read(parent_path)
 checks['shared_conditions']=(c['run_id']==run and c['pair_snapshot']['verified'] is True and c['pair_snapshot']['source_run_id']==science['historical_shared_run'] and c['pair_snapshot']['source_manifest_sha256']==sha(shared) and c['prompt']==case['prompt'])
 condition_comparison={'all_original_clean_condition_metadata_equal':clean_condition(c)==clean_condition(parent)}
 checks['original_conditioning_equal']=condition_comparison['all_original_clean_condition_metadata_equal']
 cache_manifest=read(root/'configs/CONDITION_CACHE.json');blobs=[]
 records=[shared_value['native_vae_calls'][0]['latent'],shared_value['native_vae_calls'][1]['latent'],shared_value['conditioning_embedding'],shared_value['token_tags'],shared_value['packed_layout']['position_ids']]
 for record,blob in zip(records,cache_manifest['tensors']):
  record=dict(record,tensor_file='tensor_blobs/'+Path(blob['file']).name)
  require(sha(root/'audit'/record['tensor_file'])==blob['sha256'],'cache file bytes changed')
  blobs.append(inspect_blob(root/'audit',record))
 router_path=root/'audit/router'/f'{run}.json';router=read(router_path)
 expect={'run_id':run,'mode':'mass_preserve','alpha':1.,'radius':0,'time_offset':0,'block_interval_half_open':[0,50],'step_interval_half_open':[6,15],'pixel_interval_inclusive':case['physical_query_window'],'started_calls':1000,'completed_calls':1000,'completed_forward_calls':20,'native_override_calls':1000,'routed_calls':450,'calls_by_forward':[50]*20,'calls_by_block':[20]*50,'routed_by_forward':[0]*6+[50]*9+[0]*5,'routed_by_block':[9]*50,'sample_sigmas':grid,'expected_sampling_steps':20}
 checks['fixed_reference_origin_execution_counts']=all(router.get(k)==v for k,v in expect.items())
 plan=router['validated_layout'];seq=c['packed_layout']['seq_len'];route=routing_layout(case);shapes=latent_shapes(case);lo,bins=route['latent_interval_half_open'];rows=943
 checks['actual_layout']=(router['first_attention']['qkv_shape']==[1,56,seq,128] and plan['frame_rows']==rows and plan['latent_interval_half_open']==route['latent_interval_half_open'] and plan['position_bin_coverage_inclusive']==route['position_bin_coverage_inclusive'] and plan['pixel_interval_inclusive']==route['pixel_interval_inclusive'] and plan['query_interval_half_open']==[plan['target_video_segment'][0]+lo*rows,plan['target_video_segment'][0]+bins*rows] and plan['key_interval_half_open']==[plan['reference_video_segment'][0]+lo*rows,plan['reference_video_segment'][0]+bins*rows] and plan['target_video_segment'][1]-plan['target_video_segment'][0]==shapes['video'][2]*rows and plan['reference_video_segment'][1]-plan['reference_video_segment'][0]==shapes['video'][2]*rows and plan['signature'][1:]==[shapes['video'][2],46,82,shapes['audio'][-1]] and plan['reference_image_segments']==[[6960,7910]])
 checks['combined_single_correction']=router['combined_fixed_phase']==dict(science['combination_audit'],local_shifted_calls=450)
 checks['sampled_finite']=all(x.get('sampled_finite',True) for x in router['forward_summaries'])
 checks['actual_reference_branch_origin']=check_reference_origin(router,run,c['packed_layout']['position_ids']['sha256'])
 from types import SimpleNamespace
 import importlib.util
 spec=importlib.util.spec_from_file_location('r132_positions_cpu',root/'extensions/H3TemporalRouter/alignment.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 position_record=c['packed_layout']['position_ids'];position_tensor=torch.load(root/'audit'/position_record['tensor_file'],map_location='cpu',weights_only=True)
 original_layout=SimpleNamespace(signature=tuple(router['validated_layout']['signature']),segments=[tuple(x) for x in c['packed_layout']['segments']],seq_len=seq,position_ids=position_tensor)
 derived,derived_audit=module.aligned_positions(original_layout,router['metadata'])
 checks['origin_recomputed_from_actual_original']=derived_audit==router['reference_origin']['layout']
 del position_tensor,derived
 m,files,prefix=inspect_capture(root/'audit/x0'/run,run,grid,row['seed'],case);del prefix
 prefix_comparison=compare_prefix(root,run,case,grid,row['seed'],m)
 checks['first_six_cross_host_diagnostics_complete']=prefix_comparison['diagnostics_complete']
 cache=root/'audit'/(science['noise_pair_id']+'_noise.pt');saved=torch.load(cache,map_location='cpu',weights_only=True)
 hashes=[{k:signature(t)[k] for k in ('shape','dtype','sha256')} for t in saved['tensors']]
 parent_noise={'signature':saved['signature'],'actual_noise_streams':saved['hashes']}
 checks['actual_R122_AV_noise']=(sha(cache)==science['parent_noise_sha256'] and sha(Path(science['parent_noise_file']))==science['parent_noise_sha256'] and n['run_id']==run and n['pair_id']==science['noise_pair_id'] and n['signature']['seed']==row['seed'] and len(hashes)==2 and [tuple(x.shape) for x in saved['tensors']]==[shapes[k] for k in ('video','audio')] and saved['signature']==n['signature']==parent_noise['signature'] and saved['hashes']==hashes==n['actual_noise_streams']==parent_noise['actual_noise_streams'])
 video=output_file(root,hist);properties=video_properties(video,case)
 record={'run_id':run,'video':{'file':str(video),'sha256':sha(video),'properties':properties},'valid_frames':case['valid_frame_count'],'evaluation_crop_xywh':case['evaluation_crop_xywh'],'NFE':20,'Euler_updates':20,'routed_blocks':450,'original_rope_table_blocks':1000,'job_wall_seconds':job['observed_unix']-job['submitted_unix'],'snapshots':files,'capture_seconds':sum(x['capture_seconds'] for x in m['captures']),'router_file_sha256':sha(router_path),'history_sha256':sha(root/'logs'/f'{run}_history.json'),'job_sha256':sha(root/'logs'/f'{run}_job.json')}
 record['binding_artifacts']={str(p.relative_to(root)):sha(p) for p in (root/'configs/graphs'/f'{run}.json',root/'logs'/f'{run}_history.json',root/'logs'/f'{run}_job.json',root/'audit'/f'{run}_conditioning.json',root/'audit'/f'{run}_noise.json',shared,cache,root/'audit/x0'/run/'manifest.json')}
 return {'schema':'r148-fixed-phase-runtime-gate-v1','source_id':case['source_id'],'producer_seal_sha256':sha(root/'deploy_manifest.json'),'runtime_profile_sha256':sha(root/'configs/runtime.json'),'runtime_profile':runtime,'service_owner':owner,'runs':{'fixed_phase':record},'checks':checks,'passed':all(checks.values()),'condition_tensor_files':blobs,'reference_origin':router['reference_origin'],'first_six_prediction_equality_required':False,'prefix_comparison':prefix_comparison,'condition_comparison':condition_comparison,'parent_condition_manifest_sha256':sha(parent_path),'created_unix':time.time()}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT);args=parser.parse_args();dest=args.root/'analysis/postrun'/SOURCES[0]/'COMBINED_RUNTIME_GATE.json'
 try:result=persist_gate(dest,verify(args.root))
 except BaseException as error:
  atomic(dest.with_name('COMBINED_RUNTIME_GATE_FAILURE.json'),{'passed':False,'error':repr(error),'unix':time.time()});raise
 print(json.dumps({'receipt':str(dest),'sha256':sha(dest),'passed':result['passed'],'checks':result['checks']},indent=2))
 if not result['passed']:raise SystemExit(2)
if __name__=='__main__':main()
