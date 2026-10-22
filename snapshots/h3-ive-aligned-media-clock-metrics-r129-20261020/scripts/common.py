"""Bindings for one actual aligned-clock output and existing R122 comparisons."""
from pathlib import Path
import json,hashlib,time
ROOT=Path(__file__).resolve().parents[1]
REQUIRED_CHECKS=('producer_seal','actual_runtime_device','history','service','shared_conditions','all_six_original_conditions_equal_R122','Native_attention_execution_counts','actual_layout','sampled_finite','actual_all_step_all_block_alignment','derived_positions_recomputed_from_actual_original','actual_rotation_table_audited','actual_R122_AV_noise')
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
 require(g['schema']=='r129-aligned-runtime-gate-v1' and g['source_id']=='long_0039' and g['passed']is True,'actual gate failed')
 require(set(g['checks'])==set(REQUIRED_CHECKS)and all(g['checks'][k]is True for k in REQUIRED_CHECKS),'gate checks missing or failed')
 require(g['producer_seal_sha256']==c['producer_seal_sha256']and g['runtime_profile_sha256']==c['runtime_sha256']and g['runtime_profile']==runtime,'producer/runtime binding differs')
 require(g['service_owner']==owner==complete['service_owner']==release['owner'],'actual owner mismatch')
 require(owner['gpu_uuid']==runtime['gpu_uuid']and owner['port']==runtime['port']and owner['identity']['uid']==runtime['uid']and owner['identity']['start_ticks'],'owner runtime differs')
 require(str(Path(c['producer_remote'])/'scripts/service_entry.py')in owner['identity']['cmdline'],'owner executable differs')
 require(complete['schema']=='r129-one-output-completion-v1'and complete['passed']is True and complete['GPU_released']is True and complete['jobs']==[run]and complete['remaining']==[],'completion differs')
 require(release['passed']is True and release['process_absent']is True and release['CUDA_allocation_absent']is True,'exact release missing')
 require(set(g['runs'])=={'aligned'} and g['first_six_prediction_equality_required']is False,'comparison scope differs')
 r=g['runs']['aligned'];require(r['run_id']==run and r['valid_frames']==106 and r['evaluation_crop_xywh']==[16,8,1280,720]and r['NFE']==20 and r['Euler_updates']==20 and r['routed_blocks']==0 and r['aligned_blocks']==1000,'actual run count/domain differs')
 a=g['alignment'];require(a['run_id']==run and a['enabled']is True and a['status']=='complete'and a['completed_calls']==1000 and a['completed_sampling_steps']==20 and a['calls_by_block']==[20]*50 and a['calls_by_forward']==[50]*20 and a['rotation_table_builds']==1,'alignment scope differs')
 parent=read(ROOT/'design/r122_long_0039_shared_conditioning.json');pos=parent['packed_layout']['position_ids'];layout=a['layout']
 require(layout['original_position_sha256']==pos['sha256']and layout['aligned_position_sha256']!=pos['sha256'],'original/derived coordinate binding differs')
 require(layout['reference_origin']==layout['aligned_target_origin']==4839 and abs(layout['target_time_displacement']+178.33333333333334)<1e-8,'actual origin differs')
 require(all(layout[k]is True for k in ('reference_text_unchanged','spatial_unchanged','target_video_matches_reference_all_coordinates','target_audio_video_common_origin')),'unsupported coordinate change')
 require(g['evaluation_plan_sha256']==sha(ROOT/'design/R129_EVALUATION_PLAN.json'),'event evaluation plan differs')
 safe_path(r['video']['file']);return r

def verify_collection():
 validate_static();D=ROOT/'incoming';m=read(D/'COLLECTION.json')
 for rel,h in m['files'].items():require(sha(D/rel)==h,'actual file changed '+rel)
 g=read(D/'ALIGNED_RUNTIME_GATE.json');complete=read(D/'COMPLETE.json');require(complete['runtime_gate_sha256']==sha(D/'ALIGNED_RUNTIME_GATE.json'),'completion gate mismatch')
 r=verify_gate(g,read(D/'STARTED.json'),complete,read(D/'ROOT_EXIT_RECEIPT.json'));require(sha(D/'aligned.mp4')==r['video']['sha256'],'output video differs')
 c=config();run=c['case']['run_id'];graph=read(D/'graph.json');history=read(D/'history.json');job=read(D/'job.json')
 require(graph==read(ROOT/'configs/graphs'/f'{run}.json')and graph['5']['inputs']['prompt']==c['case']['prompt'],'actual prompt/graph differs')
 require(history['status']['completed']is True and history['status']['status_str']=='success'and history['prompt'][2]==graph and history['prompt'][1]==job['prompt_id'],'history differs')
 require(job['name']==run and job['status']=='success'and job['service_pid']==g['service_owner']['pid']and job['service_identity']==g['service_owner']['identity'],'job ownership differs')
 entry=history['outputs']['14']['images'];require(len(entry)==1 and entry[0]['type']=='output','history output differs');e=entry[0];require(str(Path(c['producer_remote'])/'output'/e.get('subfolder','')/e['filename'])==r['video']['file'],'output path differs')
 clean=lambda x:{k:v for k,v in x.items()if k not in ('run_id','pair_snapshot')}
 require(clean(read(D/'conditioning.json'))==clean(read(ROOT/'design/r122_long_0039_shared_conditioning.json')),'six original conditions differ')
 n=read(D/'noise.json');parent=read(ROOT/'design/r122_long_0039_seed2026101701_native_noise.json');require(n['signature']==parent['signature']and n['actual_noise_streams']==parent['actual_noise_streams'],'actual starting noise differs')
 require(read(D/'alignment.json')==g['alignment']and read(D/'router.json')['routed_calls']==0,'actual operator audit differs');return m
