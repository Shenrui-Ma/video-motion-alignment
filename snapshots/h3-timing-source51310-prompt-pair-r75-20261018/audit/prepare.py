"""Prepare an isolated prompt-protocol diagnostic; no GPU/service operations."""
import copy,hashlib,json,shutil
from pathlib import Path
B=Path('/Users/researcher/DevProjects');R=Path(__file__).resolve().parents[1]
P=B/'h3-timing-ivebench-prompt-pair-r71-20261018';Q=B/'h3-timing-flexiact-prompt-pair-r72-20261018'
D=P/'analysis/legacy_prompt_audit';OLD=B/'h3-timing-new-actions-native-r38-20261017'
REMOTE='/data5/researcher/h3_runs/timing_source51310_prompt_pair_r75_20261018'
(R/'configs').mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def adapted(src,dst,old='r71'):
 dst.parent.mkdir(parents=True,exist_ok=True)
 text=src.read_text().replace(old,'r75').replace(old.upper(),'R75')
 dst.write_text(text)
for folder in ('scripts','extensions'):
 for f in (P/folder).rglob('*.py'):
  rel=f.relative_to(P);target=R/str(rel).replace('r71_contract.py','r75_contract.py');adapted(f,target)
for name in ('capture_checks.py','verify_pair.py'):
 adapted(Q/'analysis/postrun'/name,R/'analysis/postrun'/name,'r72')
for name in ('test_spawn_identity.py','test_prompt_pair.py'):
 adapted(P/'tests'/name,R/'tests'/name)
adapted(Q/'tests/test_pair_verifier.py',R/'tests/test_pair_verifier.py','r72')
for name in ('parent_core_hashes.json','runtime_kernel_hashes.json','expected_checkpoint_hashes.json'):
 shutil.copy2(P/'configs'/name,R/'configs'/name)
for p in ('configs/prompts','configs/graphs','configs/parent_graphs','design','inputs','tests/fixtures'):(R/p).mkdir(parents=True,exist_ok=True)
for source,dest in [('P0_EXACT.txt','configs/prompts/p0.txt'),('P1_PROPOSED.txt','configs/prompts/p1.txt'),('FRESH_P0_P1_CONTROL_DESIGN.json','design/CONTROL_DESIGN.json'),('ORIGINAL_NOISE_READBACK.json','design/ORIGINAL_NOISE_READBACK.json'),('AUDIT_FREEZE.json','design/LEGACY_AUDIT_FREEZE.json')]:shutil.copy2(D/source,R/dest)
for name in ('source_51310_video.mp4','source_51310_portrait.jpg','source_51310_provenance.json'):shutil.copy2(OLD/'inputs'/name,R/'inputs'/name)
captures=read(D/'HISTORICAL_INPUT_AND_PROMPT_BINDINGS.json');native=captures['Native'];parent=native['actual_graph']
put(R/'configs/parent_graphs/r38_source51310_native.json',parent)
arc=Path(native['archive'])
shutil.copy2(arc/'audit/x0/r38_source_51310_seed2026101701_native/manifest.json',R/'tests/fixtures/R38_captures.json')
put(R/'design/HISTORICAL_CONDITION_SIGNATURES.json',{k:native[k]for k in ('input_video','native_vae_calls','qwen_presentation','target_latent_shapes','actual_noise_streams','noise_signature')})
runtime=read(P/'configs/runtime.json');runtime.update(status='CPU_PREPARING_ROOT_LAUNCH_PENDING',remote_root=REMOTE,gpu_uuid='GPU-REDACTED',port=8542,expected_gpu_index=1,profile='host9_gpu1_normal_reserve8',profile_scope='Fresh source51310 P0/P1 Native protocol bundle control; root capacity trial requires at least40GiB actual free;141frame full trajectory pending.')
put(R/'configs/runtime.json',runtime)
put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
hashes={p.name:sha(p)for p in (R/'inputs').iterdir()};put(R/'configs/input_hashes.json',hashes)
ancestor={a:{'file':f'configs/prompts/{a}.txt','sha256':sha(R/f'configs/prompts/{a}.txt')}for a in ('p0','p1')}
ancestor.update(control_design_sha256=sha(R/'design/CONTROL_DESIGN.json'),historical_noise_readback_sha256=sha(R/'design/ORIGINAL_NOISE_READBACK.json'),historical_conditions_sha256=sha(R/'design/HISTORICAL_CONDITION_SIGNATURES.json'),parent_graph_sha256=sha(R/'configs/parent_graphs/r38_source51310_native.json'))
put(R/'configs/prompt_ancestry.json',ancestor)
cases=[]
for arm in ('p0','p1'):
 run=f'r75_source_51310_seed2026101701_{arm}';prompt=(R/f'configs/prompts/{arm}.txt').read_text()
 case={'run_id':run,'source_id':'source_51310','seed':2026101701,'arm':arm,'prompt_version':arm.upper(),'prompt':prompt,'prompt_file':f'configs/prompts/{arm}.txt','prompt_sha256':ancestor[arm]['sha256'],'reference_cache_id':f'r75_source_51310_{arm}_shared','parent_graph':'configs/parent_graphs/r38_source51310_native.json','parent_graph_sha256':ancestor['parent_graph_sha256'],'reference_video_count':1,'reference_image_count':1,'valid_frame_count':141,'geometry':{'width':1312,'height':736,'frames':141,'fps':24},'evaluation_indices':list(range(141)),'evaluation_fps':24,'evaluation_crop_xywh':[0,0,1312,736],'reference_image_expected':{'expected_native_ref_image_size_match_width_height':[800,1216],'expected_clean_reference_latent_shape':[1,24,1,76,50],'expected_DiT_visual_patch_tokens':950}}
 for key,suffix in [('video','video.mp4'),('portrait','portrait.jpg'),('provenance','provenance.json')]:case[key]='source_51310_'+suffix;case[key+'_sha256']=hashes[case[key]]
 cases.append(case)
g=read(P/'configs/scientific_contract.json');g.update(schema='r75-preregistered-prompt-pair-v1',cases=cases,case_order=[c['run_id']for c in cases],source_ids=['source_51310'],geometry=cases[0]['geometry'],purpose='Same-host fresh Native prompt protocol bundle diagnostic on a previously selected development sample; not temporal-intervention efficacy.',condition_scope='Actual original media/clean reference/AVnoise fixed; P0/P1 text cache separate. Prompt formatting, task tag and explicit reference bindings vary jointly.',source_event_annotations='Historical windows64–95 and96–127 retained only for evaluation; no action window supplied to either Native model.',evaluation={'fps':24,'valid_frames':141,'crop':[0,0,1312,736],'primary_window_inclusive':[64,95],'secondary_window_inclusive':[96,127],'additional_windows':[[0,31],[32,63],[125,140]],'unknown':'retain','method':'frozen R41 pose/lag plus edit/action visual review; development diagnostic'},router={'mode':'native','alpha':1.,'blocks':[0,50],'steps':[0,20],'physical_frames':[0,140],'query_support':'all42 temporal bins and all spatial queries'})
g['continuous']['idle_hold_seconds']=1800;g['routed_blocks_per_job']={'p0':0,'p1':0}
put(R/'configs/scientific_contract.json',g);put(R/'configs/queue.json',{'jobs':g['case_order'],'finalize':True})
for c in cases:
 graph=copy.deepcopy(parent);run=c['run_id']
 for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:graph[node]['inputs'][key]=str(Path(REMOTE)/suffix)
 graph['5']['inputs'].update(run_id=c['reference_cache_id'],prompt=c['prompt']);graph['51']['inputs']['source_run_id']=c['reference_cache_id']
 for node in ('6','50','51','52'):graph[node]['inputs']['run_id']=run
 graph['6']['inputs']['pair_id']='r75_source_51310_seed2026101701';graph['14']['inputs']['filename_prefix']=run
 put(R/'configs/graphs'/f'{run}.json',graph)
print(R)
