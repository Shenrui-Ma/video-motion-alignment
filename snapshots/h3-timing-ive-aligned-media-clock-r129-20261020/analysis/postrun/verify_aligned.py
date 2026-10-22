"""CPU actual-output verifier, one fresh Native/ON pair. Quality is assessed separately."""
import argparse,copy,json,os,subprocess,sys,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import torch
from capture_checks import inspect_capture,checked_snapshot,inspect_blob,condition_files,signature,expected_routing
from r129_contract import read,sha,require,registry,validate_job,SOURCES,RUN_ID,geometry,latent_shapes,routing_layout
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

def check_alignment(a,run,original_position_sha):
 require(a['schema']=='h3-r129-aligned-media-clock-v1' and a['run_id']==run,'alignment audit identity differs')
 require(a['enabled'] is True and a['status']=='complete' and a['completed_sampling_steps']==20,'alignment incomplete')
 require(a['completed_calls']==1000 and a['calls_by_block']==[20]*50 and a['calls_by_forward']==[50]*20,'alignment not applied at every registered block/step')
 require(a['rotation_table_builds']==1 and a['first_six_prediction_equality_required'] is False,'alignment cache/scope differs')
 layout=a['layout']
 require(layout['original_position_sha256']==original_position_sha and layout['aligned_position_sha256']!=original_position_sha,'original/derived positions differ from contract')
 require(layout['reference_origin']==4839.0 and layout['original_target_origin']>4839.0 and layout['aligned_target_origin']==4839.0,'actual clock origins differ')
 require(abs(layout['target_time_displacement']+178.33333333333334)<1e-8,'actual clock displacement differs')
 require(all(layout[k] is True for k in ('reference_text_unchanged','spatial_unchanged','target_video_matches_reference_all_coordinates','target_audio_video_common_origin')),'alignment altered unsupported coordinates')
 require(layout['canonical_reconstruction_max_translation_roundoff']<=1e-8,'alignment displacement inconsistent')
 return True

def verify(root):
 torch.set_num_threads(1);root=Path(root).resolve();jobs,order=registry(root);run=RUN_ID;row=validate_job(run,root);case=row['case']
 runtime=read(root/'configs/runtime.json');science=read(root/'configs/scientific_contract.json');seal=read(root/'deploy_manifest.json');owner=read(root/'processes/service.json')
 checks={'producer_seal':all(sha(root/p)==v['sha256'] for p,v in seal['files'].items()),'actual_runtime_device':owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port'] and owner['identity']['uid']==runtime['uid']}
 graph=read(root/'configs/graphs'/f'{run}.json');grid=torch.tensor([float(x) for x in graph['9']['inputs']['sigmas'].split(',')],dtype=torch.float32).tolist()
 hist=read(root/'logs'/f'{run}_history.json');job=read(root/'logs'/f'{run}_job.json')
 checks['history']=(hist['status']['completed'] is True and hist['status']['status_str']=='success' and hist['prompt'][2]==graph and hist['prompt'][1]==job['prompt_id'] and job['status']=='success' and job['name']==run)
 checks['service']=(job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'] and job['graph_sha256']==row['graph_sha256'])
 c=read(root/'audit'/f'{run}_conditioning.json');n=read(root/'audit'/f'{run}_noise.json');shared=root/'audit/r129_long_0039_shared_conditioning.json';shared_value=read(shared)
 parent_path=root/'design/r122_long_0039_shared_conditioning.json';parent=read(parent_path)
 checks['shared_conditions']=(c['run_id']==run and c['pair_snapshot']['verified'] is True and c['pair_snapshot']['source_run_id']=='r129_long_0039_shared' and c['pair_snapshot']['source_manifest_sha256']==sha(shared) and c['prompt']==case['prompt'])
 # The original position tensor is also unchanged: alignment uses a derived table.
 checks['all_six_original_conditions_equal_R122']=clean_condition(c)==clean_condition(parent)
 require(len(condition_files(c))==6,'expected all six original condition blobs')
 blobs=[];seen=set()
 for record in walk_blobs(shared_value):
  if record['tensor_file'] not in seen:
   seen.add(record['tensor_file']);blobs.append(inspect_blob(root/'audit',record))
 router_path=root/'audit/router'/f'{run}.json';router=read(router_path)
 expect={'run_id':run,'mode':'native','alpha':1.,'radius':0,'time_offset':0,'block_interval_half_open':[0,50],'step_interval_half_open':[6,15],'pixel_interval_inclusive':[0,105],'started_calls':1000,'completed_calls':1000,'completed_forward_calls':20,'native_override_calls':1000,'routed_calls':0,'calls_by_forward':[50]*20,'calls_by_block':[20]*50,'routed_by_forward':[0]*20,'routed_by_block':[0]*50,'sample_sigmas':grid,'expected_sampling_steps':20}
 checks['Native_attention_execution_counts']=all(router.get(k)==v for k,v in expect.items())
 plan=router['validated_layout'];seq=c['packed_layout']['seq_len'];route=routing_layout(case);shapes=latent_shapes(case);bins=32;rows=943
 checks['actual_layout']=(router['first_attention']['qkv_shape']==[1,56,seq,128] and plan['frame_rows']==rows and plan['latent_interval_half_open']==route['latent_interval_half_open'] and plan['position_bin_coverage_inclusive']==route['position_bin_coverage_inclusive'] and plan['pixel_interval_inclusive']==route['pixel_interval_inclusive'] and plan['query_interval_half_open']==[plan['target_video_segment'][0],plan['target_video_segment'][0]+bins*rows] and plan['key_interval_half_open']==[plan['reference_video_segment'][0],plan['reference_video_segment'][0]+bins*rows] and plan['target_video_segment'][1]-plan['target_video_segment'][0]==32*rows and plan['reference_video_segment'][1]-plan['reference_video_segment'][0]==32*rows and plan['signature'][1:]==[32,46,82,178] and plan['reference_image_segments']==[])
 checks['sampled_finite']=all(x.get('sampled_finite',True) for x in router['forward_summaries'])
 alignment_path=root/'audit/router'/f'{run}_alignment.json';alignment=read(alignment_path)
 checks['actual_all_step_all_block_alignment']=check_alignment(alignment,run,c['packed_layout']['position_ids']['sha256'])
 from types import SimpleNamespace
 import importlib.util
 spec=importlib.util.spec_from_file_location('r129_positions_cpu',root/'extensions/H3TemporalRouter/alignment.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 position_record=c['packed_layout']['position_ids'];position_tensor=torch.load(root/'audit'/position_record['tensor_file'],map_location='cpu',weights_only=True)
 original_layout=SimpleNamespace(signature=tuple(router['validated_layout']['signature']),segments=[tuple(x) for x in c['packed_layout']['segments']],seq_len=seq,position_ids=position_tensor)
 derived,derived_audit=module.aligned_positions(original_layout,router['metadata'])
 checks['derived_positions_recomputed_from_actual_original']=derived_audit==alignment['layout']
 checks['actual_rotation_table_audited']=alignment['table_shape']==[1,seq,1,48,2,2] and alignment['table_device'].startswith('cuda') and len(alignment['table_probe_float32_sha256'])==64
 del position_tensor,derived
 m,files,prefix=inspect_capture(root/'audit/x0'/run,run,grid,row['seed'],case);del prefix
 cache=root/'audit/r129_long_0039_seed2026101701_noise.pt';saved=torch.load(cache,map_location='cpu',weights_only=True)
 hashes=[{k:signature(t)[k] for k in ('shape','dtype','sha256')} for t in saved['tensors']]
 parent_noise=read(root/'design/r122_long_0039_seed2026101701_native_noise.json')
 checks['actual_R122_AV_noise']=(sha(cache)==science['parent_noise_sha256'] and sha(Path(science['parent_noise_file']))==science['parent_noise_sha256'] and n['run_id']==run and n['pair_id']=='r129_long_0039_seed2026101701' and n['signature']['seed']==row['seed'] and len(hashes)==2 and [tuple(x.shape) for x in saved['tensors']]==[shapes[k] for k in ('video','audio')] and saved['signature']==n['signature']==parent_noise['signature'] and saved['hashes']==hashes==n['actual_noise_streams']==parent_noise['actual_noise_streams'])
 video=output_file(root,hist);properties=video_properties(video,case)
 record={'run_id':run,'video':{'file':str(video),'sha256':sha(video),'properties':properties},'valid_frames':106,'evaluation_crop_xywh':case['evaluation_crop_xywh'],'NFE':20,'Euler_updates':20,'routed_blocks':0,'aligned_blocks':1000,'job_wall_seconds':job['observed_unix']-job['submitted_unix'],'snapshots':files,'capture_seconds':sum(x['capture_seconds'] for x in m['captures']),'router_file_sha256':sha(router_path),'alignment_file_sha256':sha(alignment_path),'history_sha256':sha(root/'logs'/f'{run}_history.json'),'job_sha256':sha(root/'logs'/f'{run}_job.json')}
 record['binding_artifacts']={str(p.relative_to(root)):sha(p) for p in (root/'configs/graphs'/f'{run}.json',root/'logs'/f'{run}_history.json',root/'logs'/f'{run}_job.json',root/'audit'/f'{run}_conditioning.json',root/'audit'/f'{run}_noise.json',shared,cache,root/'audit/x0'/run/'manifest.json',alignment_path)}
 return {'schema':'r129-aligned-runtime-gate-v1','source_id':'long_0039','producer_seal_sha256':sha(root/'deploy_manifest.json'),'runtime_profile_sha256':sha(root/'configs/runtime.json'),'runtime_profile':runtime,'service_owner':owner,'runs':{'aligned':record},'checks':checks,'passed':all(checks.values()),'condition_tensor_files':blobs,'alignment':alignment,'first_six_prediction_equality_required':False,'first_six_prediction_equality_reason':'All-step positional intervention begins at step zero. Original six conditioning blobs and actual starting AV noise are required equal.','parent_condition_manifest_sha256':sha(parent_path),'evaluation_plan_sha256':science['evaluation_plan_sha256'],'created_unix':time.time()}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT);args=parser.parse_args();dest=args.root/'analysis/postrun/long_0039/ALIGNED_RUNTIME_GATE.json'
 try:result=persist_gate(dest,verify(args.root))
 except BaseException as error:
  atomic(dest.with_name('ALIGNED_RUNTIME_GATE_FAILURE.json'),{'passed':False,'error':repr(error),'unix':time.time()});raise
 print(json.dumps({'receipt':str(dest),'sha256':sha(dest),'passed':result['passed'],'checks':result['checks']},indent=2))
 if not result['passed']:raise SystemExit(2)
if __name__=='__main__':main()
