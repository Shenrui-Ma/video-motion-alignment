"""Bindings for one actual reference-origin branch output and existing R122 comparisons."""
from pathlib import Path
import json,hashlib,time,copy,math
ROOT=Path(__file__).resolve().parents[1]
REQUIRED_CHECKS=('producer_seal','actual_runtime_device','history','service','shared_conditions','original_input_pixels_tokens_positions_equal_R122','fixed_reference_origin_execution_counts','actual_layout','sampled_finite','actual_reference_branch_origin','origin_recomputed_from_actual_original','first_six_cross_host_diagnostics_complete','actual_R122_AV_noise')
def require(v,message):
 if not v:raise ValueError(message)
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+'.tmp');q.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n');q.replace(p)
def bound(p):return {'file':str(p),'sha256':sha(p)}
def config():return read(ROOT/'configs/contract.json')
def safe_path(path):
 p=Path(path);require(p.is_relative_to(config()['producer_remote'])and'..'not in p.parts,'unsafe producer path');return p

def validate_static():
 c=config();freeze=read(ROOT/'CONSUMER_FREEZE.json')
 for rel,h in freeze['files'].items():require(sha(ROOT/rel)==h,'consumer binding changed '+rel)
 p=Path(c['producer_local']);require(sha(p/'deploy_manifest.json')==c['producer_seal_sha256'],'producer seal changed')
 for rel,v in read(p/'deploy_manifest.json')['files'].items():require(sha(p/rel)==v['sha256'],'producer sealed file changed '+rel)
 for b in list(c['parent_media'].values())+[c['parent_collection'],c['parent_gate'],c['parent_full_frame_review'],c['source_provenance'],c['source_original']]:require(sha(b['file'])==b['sha256'],'parent binding changed')
 q=c['case'];require(q['valid_frame_count']==106 and q['geometry']=={'width':1312,'height':736,'frames':107,'fps':24}and q['evaluation_crop_xywh']==[16,8,1280,720]and q['evaluation_indices']==list(range(106)),'domain differs')
 require(c['parent_media']['source']['sha256']==q['video_sha256'],'source differs from R122')
 return c

def verify_gate(g,started,complete,release):
 c=config();runtime=read(ROOT/'configs/runtime.json');case=c['case'];run=case['run_id'];owner=started['owner']
 require(g['schema']=='r132-reference-origin-runtime-gate-v1' and g['source_id']=='long_0039' and g['passed']is True,'actual gate failed')
 require(set(g['checks'])==set(REQUIRED_CHECKS)and all(g['checks'][k]is True for k in REQUIRED_CHECKS),'gate checks missing or failed')
 require(g['producer_seal_sha256']==c['producer_seal_sha256']and g['runtime_profile_sha256']==c['runtime_sha256']and g['runtime_profile']==runtime,'producer/runtime binding differs')
 require(g['service_owner']==owner==complete['service_owner']==release['owner'],'actual owner mismatch')
 require(owner['gpu_uuid']==runtime['gpu_uuid']and owner['port']==runtime['port']and owner['identity']['uid']==runtime['uid']and owner['identity']['start_ticks'],'owner runtime differs')
 require(str(Path(c['producer_remote'])/'scripts/service_entry.py')in owner['identity']['cmdline'],'owner executable differs')
 require(complete['schema']=='r132-one-output-completion-v1'and complete['passed']is True and complete['GPU_released']is True and complete['jobs']==[run]and complete['remaining']==[],'completion differs')
 require(release['passed']is True and release['process_absent']is True and release['CUDA_allocation_absent']is True,'exact release missing')
 require(set(g['runs'])=={'reference_origin'} and g['first_six_prediction_equality_required']is False,'comparison scope differs')
 r=g['runs']['reference_origin'];require(r['run_id']==run and r['valid_frames']==106 and r['evaluation_crop_xywh']==[16,8,1280,720]and r['NFE']==20 and r['Euler_updates']==20 and r['routed_blocks']==450 and r['original_rope_table_blocks']==1000,'actual run count/domain differs')
 a=g['reference_origin'];layout=a['layout'];rotation=a['rotation']
 require(a['new_method_claim'] is False and a['original_QKV_and_table_preserved'] is True,'reference branch scope differs')
 require(a['extra_query_scope']=='target_video_only' and a['reference_scope']=='all_video_reference_keys','auxiliary token scope differs')
 require(a['first_six_prediction_equality_required'] is False and a['layout_validation_count']==1 and a['rotation_calls']==450 and a['original_rope_table_calls']==1000,'reference-origin execution counts differ')
 parent=read(ROOT/'design/r122_long_0039_shared_conditioning.json');pos=parent['packed_layout']['position_ids']
 require(layout['original_position_sha256']==pos['sha256'],'original position binding differs')
 require(layout['reference_origin']==4839 and layout['original_target_origin']>4839 and abs(layout['target_time_displacement']+178.33333333333334)<1e-8,'actual origin differs')
 require(rotation['displacement_rope_units']==layout['target_time_displacement'] and rotation['time_channel_pairs']==[[0,16],[48,64]] and len(rotation['inv_freq'])==16 and len(rotation['inv_freq_sha256'])==64,'checkpoint frequency or rotation sign differs')
 require(all(layout[k]is True for k in ('reference_text_unchanged','spatial_unchanged','target_video_matches_reference_all_coordinates','target_audio_video_common_origin')),'canonical geometry differs')
 verify_prefix_diagnostics(g['prefix_comparison'])
 require(g['condition_comparison']['strict_metadata_pixels_tokens_positions_equal'] is True,'strict original inputs differ')
 require(g['evaluation_plan_sha256']==sha(ROOT/'design/R129_EVALUATION_PLAN.json'),'event evaluation plan differs')
 safe_path(r['video']['file']);return r

def verify_collection():
 validate_static();D=ROOT/'incoming';m=read(D/'COLLECTION.json')
 for rel,h in m['files'].items():require(sha(D/rel)==h,'actual file changed '+rel)
 g=read(D/'REFERENCE_ORIGIN_RUNTIME_GATE.json');complete=read(D/'COMPLETE.json');require(complete['runtime_gate_sha256']==sha(D/'REFERENCE_ORIGIN_RUNTIME_GATE.json'),'completion gate mismatch')
 r=verify_gate(g,read(D/'STARTED.json'),complete,read(D/'ROOT_EXIT_RECEIPT.json'));require(sha(D/'reference_origin.mp4')==r['video']['sha256'],'output video differs')
 c=config();run=c['case']['run_id'];graph=read(D/'graph.json');history=read(D/'history.json');job=read(D/'job.json')
 require(graph==read(ROOT/'configs/graphs'/f'{run}.json')and graph['5']['inputs']['prompt']==c['case']['prompt'],'actual prompt/graph differs')
 require(history['status']['completed']is True and history['status']['status_str']=='success'and history['prompt'][2]==graph and history['prompt'][1]==job['prompt_id'],'history differs')
 require(job['name']==run and job['status']=='success'and job['service_pid']==g['service_owner']['pid']and job['service_identity']==g['service_owner']['identity'],'job ownership differs')
 entry=history['outputs']['14']['images'];require(len(entry)==1 and entry[0]['type']=='output','history output differs');e=entry[0];require(str(Path(c['producer_remote'])/'output'/e.get('subfolder','')/e['filename'])==r['video']['file'],'output path differs')
 require(compare_condition_metadata(read(D/'conditioning.json'),read(ROOT/'design/r122_long_0039_shared_conditioning.json'))==g['condition_comparison']['floating_model_output_hashes'],'actual condition diagnostic differs')
 n=read(D/'noise.json');parent=read(ROOT/'design/r122_long_0039_seed2026101701_native_noise.json');require(n['signature']==parent['signature']and n['actual_noise_streams']==parent['actual_noise_streams'],'actual starting noise differs')
 router=read(D/'router.json');require(router['reference_origin']==g['reference_origin'] and router['routed_calls']==450 and router['routed_by_forward']==[0]*6+[50]*9+[0]*5 and router['routed_by_block']==[9]*50,'actual operator audit differs');return m


def compare_condition_metadata(actual,parent):
 clean=lambda x:{k:v for k,v in copy.deepcopy(x).items()if k not in ('run_id','pair_snapshot')}
 a,b=clean(actual),clean(parent);out={}
 for label,x,y in [('vae_latent',a['native_vae_calls'][0]['latent'],b['native_vae_calls'][0]['latent']),('conditioning_embedding',a['conditioning_embedding'],b['conditioning_embedding'])]:
  require(x['shape']==y['shape'] and x['dtype']==y['dtype'],'floating condition geometry differs')
  out[label]={'actual_sha256':x['sha256'],'R122_sha256':y['sha256'],'sha256_equal':x['sha256']==y['sha256'],'equality_required':False}
  for z in (x,y):z.pop('sha256');z.pop('tensor_file')
 require(a==b,'original pixels/tokens/positions or other metadata differ')
 return out

def verify_prefix_diagnostics(p):
 require(p['diagnostics_complete'] is True and p['equality_required'] is False and p['steps_zero_based']==list(range(6)) and p['streams']==['video','audio'],'prefix diagnostic coverage differs')
 require(p['parent_manifest_sha256']==sha(ROOT/'design/R122_native_x0_manifest.json') and p['parent_statistics_sha256']==sha(ROOT/'design/R122_native_prefix_statistics.json'),'historical diagnostic binding differs')
 stats=read(ROOT/'design/R122_native_prefix_statistics.json');rows=p['comparisons'];require(len(rows)==6,'prefix diagnostic row count differs')
 for i,row in enumerate(rows):
  require(row['step_zero_based']==i and set(row['streams'])=={'video','audio'},'prefix step/stream differs')
  for key,d in row['streams'].items():
   require(d['equality_required'] is False and d['sample_count']==1024 and d['parent_tensor_sha256']==stats['captures'][i]['streams'][key]['tensor_sha256'],'prefix source binding differs')
   require(len(d['actual_tensor_sha256'])==64 and d['full_tensor_sha256_equal']==(d['actual_tensor_sha256']==d['parent_tensor_sha256']),'prefix hash equality record differs')
   require(all(math.isfinite(d[k]) and d[k]>=0 for k in ('sample_difference_rms','sample_difference_max_abs','actual_whole_tensor_rms','parent_whole_tensor_rms')),'invalid prefix difference statistic')
   require(all(math.isfinite(d[k]) for k in ('actual_whole_tensor_mean','parent_whole_tensor_mean')),'invalid prefix mean')
 return p
