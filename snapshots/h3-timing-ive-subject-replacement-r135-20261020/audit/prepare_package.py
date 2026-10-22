"""Single-source configuration over the R128 executor; no GPU operation."""
from pathlib import Path
import copy, hashlib, json, re, shutil, sys, time

R=Path(__file__).resolve().parents[1];P=R.parent/'h3-timing-ive-book-color-r128-20261020';S='short_0084'
VERSION='IVEBench-edit-with-generic-retention-v1'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def cp(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
assert not (R/'deploy_manifest.json').exists()
seal=read(P/'deploy_manifest.json');num=read(P/'configs/runtime_kernel_hashes.json')
for rel,x in seal['files'].items():
    assert sha(P/rel)==x['sha256'],rel
    if rel.startswith(('configs/graphs/','configs/prompts/','design/','configs/source_selection/','inputs/')):continue
    dst=rel.replace('r128_contract.py','r135_contract.py');cp(P/rel,R/dst)
    if rel.endswith('.py') and not rel.startswith('source_snapshot/') and rel not in num:
        p=R/dst;p.write_text(p.read_text().replace('r128','r135').replace('R128','R135'))
for folder in ['input','output','temp','user','custom_nodes','processes','logs','configs/graphs','configs/prompts','audit/router','audit/x0','configs/source_selection']:(R/folder).mkdir(parents=True,exist_ok=True)
row=read(R/'design/INPUT_PLAN.json')['pairs'][0];official=row['official_task']
prompt="subject_definitions:\n<Video 1> is the source video for this edit.\n\nsummary:\n[video editing] The target video is an edited version of <Video 1>.\n"+official['edit_prompt']+"\n\nretention_analysis:\n<Video 1>: partially_preserved - Preserve the source video's people, scene, framing, camera motion, and actions, except for changes explicitly requested in the summary.\n"
assert official['source_prompt'] not in prompt and official['target_prompt'] not in prompt
events_path=R.parent/'h3-oxygen-online-metrics-r133-20261020/audit/source_screen_candidates_20261020/short0084_review/ROOT_SOURCE_DECISION.json'
ev=read(events_path);assert sha(events_path)=='c2fec075f0ca93b6760b93f86eb1c5bd2fc38fa13a5c06b31d709be7acbd2bd7'
cp(events_path,R/'audit/SOURCE_EVENTS_BEFORE_OUTPUT.json')
ev=dict(ev,events=[{'id':k,'original_frame_interval':v} for k,v in ev['reference_intervals_original_frames'].items()],event_scope='Three milestones within one continuous arm lowering; no independent-action count',editing_scope='Woman replacement with comparable full source framing, hand trajectory, background and object presence')
put(R/'design/REFERENCE_EVENT_REVIEW_PLAN.json',{'schema':'r135-source-event-review-plan-v1','evaluation_only':True,'items':[{'source_id':S,'reference_original_frame_brackets':{x['id']:x['original_frame_interval'] for x in ev['events']},'clip_original_frames':[0,75]}],'source_event_path':str(events_path),'source_event_sha256':sha(events_path),'scope':ev['event_scope']})
files={}
for kind,suffix in [('original','original.mp4'),('video','video.mp4'),('provenance','provenance.json'),('prompt','prompt.txt')]:
    f=R/'inputs'/f'{S}_{suffix}';files[kind]={'file':str(f.relative_to(R)),'sha256':sha(f),'bytes':f.stat().st_size}
put(R/'PREPARED_INPUTS_MANIFEST.json',{'schema':'r135-prepared-input-v1','input_plan_sha256':sha(R/'design/INPUT_PLAN.json'),'pairs':[{'pair_id':S,'files':files,'h3_frames':90,'valid_frames':76,'clip':row['clip'],'scope':'subject_replacement','evaluation_scope':row['evaluation_scope']}]})
for rel in [f'configs/prompts/{S}.txt',f'design/{S}_actual_prompt.txt','design/GENERIC_RETENTION_TEMPLATE.txt']:(R/rel).write_text(prompt)
case=copy.deepcopy(row);case.update(prompt_file=str(R/'configs/prompts'/f'{S}.txt'),prompt_sha256=sha(R/'configs/prompts'/f'{S}.txt'),task_scope='subject_replacement',source_acceptance=ev['editing_scope'])
put(R/'design/PROPOSAL.json',{'schema':'r135-generic-retention-single-source-v1','created_unix':time.time(),'state':'CPU prepared; no GPU dispatch','cases':[case],'method':'Inherited Native then conditional fixed attention output intervention, steps6..14, 20 Euler predictions','prompt_protocol':VERSION,'scope':'Subject replacement with one visible continuous arm lowering, measured by three milestones','native_acceptance':'The visible man is replaced with a woman; full source framing, background and arm lowering remain comparable. Guide only if task succeeds and temporal deviation is clear.'})
put(R/'design/PROMPT_PROTOCOL.json',{'version':VERSION,'official_fields':official,'actual_prompt_sha256':case['prompt_sha256'],'rule':'Official edit_prompt verbatim with source binding and generic retention. Source/target captions are metadata only. No added action narrative or event times. Native and forced use the same prompt.'})
put(R/'configs/source_selection/SELECTED_SOURCE_MANIFEST.json',{'pairs':[row],'root_proposal_sha256':sha(R/'design/PROPOSAL.json'),'root_review_events_sha256':sha(R/'design/REFERENCE_EVENT_REVIEW_PLAN.json')})
put(R/'configs/source_selection_hashes.json',{p.name:sha(p) for p in (R/'configs/source_selection').iterdir()})
runtime=read(P/'configs/runtime.json');runtime.update(remote_root='/home/researcher/h3_runs/timing_ive_subject_replacement_r135_20261020',port=8612,profile='host9_gpu2_r135_normal_reserve8',profile_scope='Single subject replacement; R130 GPU3 exact peer registered',status='CPU_PREPARED');put(R/'configs/runtime.json',runtime)
put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
put(R/'audit/PEER_PLAN.json',{'host':'H3_SERVER_A','own_gpu_index':2,'own_gpu_uuid':runtime['gpu_uuid'],'peer_remote_root':'/home/researcher/h3_runs/timing_ive_caption_ablation_r130_20261020','peer_gpu_index':3,'peer_pid':19347,'peer_start_ticks':'2648067964','max_own_gpus':2,'fresh_identity_capacity_and_port_required':True,'GPU_started':False,'predecessor_release_required':'R134 actual service12814/start2648367610 GPU2 must release; no third own GPU'})
scientific=read(P/'configs/scientific_contract.json');scientific.update(schema='r135-generic-retention-single-source-v1',source_ids=[S],case_order=[],cases=[],purpose='Replace the man with a woman while preserving the source framing and continuous motion',prompt_version=VERSION,prompt_sha256={S:case['prompt_sha256']});scientific['screening']['schema']='r135-native-screen-policy-v1'
for old in read(P/'configs/scientific_contract.json')['cases']:
    c=copy.deepcopy(old);arm=c['arm'];c.update(run_id=f'r135_{S}_seed2026101701_{arm}',source_id=S,prompt=prompt,prompt_version=VERSION,prompt_sha256=case['prompt_sha256'],video=f'{S}_video.mp4',video_sha256=files['video']['sha256'],provenance=f'{S}_provenance.json',provenance_sha256=files['provenance']['sha256'],original_source=row['source'],geometry={'width':1312,'height':736,'frames':90,'fps':24},valid_frame_count=76,original_task=official,clip=row['clip'],task_scope='subject_replacement',evaluation_scope=row['evaluation_scope']);scientific['cases'].append(c);scientific['case_order'].append(c['run_id'])
for k,rel in [('input_plan_sha256','design/INPUT_PLAN.json'),('prepared_input_manifest_sha256','PREPARED_INPUTS_MANIFEST.json'),('source_selection_sha256','configs/source_selection/SELECTED_SOURCE_MANIFEST.json'),('root_proposal_sha256','design/PROPOSAL.json'),('root_event_review_sha256','design/REFERENCE_EVENT_REVIEW_PLAN.json')]:scientific[k]=sha(R/rel)
scientific['evaluation'].update(official='Original short0353 edit_prompt with generic source retention; source/target captions stored as metadata',rules_sha256=scientific['source_selection_sha256'],task_scopes={S:'subject_replacement'},source_extent_scopes={S:row['evaluation_scope']})
scientific['acceleration_axes']['postprocessing']='76 valid frames at24fps; last valid sample75 maps original74 by nearest physical PTS. Frames76..89 are repeated padding excluded from evaluation. No interpolation.'
put(R/'configs/scientific_contract.json',scientific);put(R/'configs/queue.json',{'jobs':scientific['case_order'],'finalize':True})
p=R/'scripts/r135_contract.py';t=p.read_text().replace("SOURCES=('short_0362',)","SOURCES=('short_0084',)").replace("SOURCE_LENGTHS={'short_0362': (73, 65)}","SOURCE_LENGTHS={'short_0084': (90, 76)}").replace('IVEBench-official-fields-full-Context-IR-v1',VERSION).replace('FULL_CONTEXT_TEMPLATE.txt','GENERIC_RETENTION_TEMPLATE.txt')
t=t.replace("all(proposal[source]['official_task'][k] in case['prompt'] for k in ('source_prompt','edit_prompt','target_prompt'))","proposal[source]['official_task']['edit_prompt'] in case['prompt'] and all(proposal[source]['official_task'][k] not in case['prompt'] for k in ('source_prompt','target_prompt'))")
t=t.replace('full Context-IR template or official fields differ','generic retention template or original edit differs');p.write_text(t)
p=R/'scripts/input_contract.py';p.write_text(p.read_text().replace("SOURCES=('short_0362',)","SOURCES=('short_0084',)").replace('LENGTHS=((73, 65),)','LENGTHS=((90, 76),)'))
p=R/'scripts/prepare_inputs.py';p.write_text(re.sub(r'^SELECTION_SHA = .*$',f'SELECTION_SHA = {sha(R/"design/INPUT_PLAN.json")!r}',p.read_text().replace('short_0362',S),flags=re.M))
p=R/'analysis/postrun/verify_pair.py';t=p.read_text().replace('IVEBench-official-fields-full-Context-IR-v1',VERSION).replace('One complete2.68-second source; exact official source/edit/target fields in full Context-IR','One complete3.128125-second source; official edit verbatim with source binding and generic retention');p.write_text(t)
p=R/'tests/test_single_source_contract.py';t=p.read_text().replace('short_0362',S).replace('Change the book with a blue cover to a red cover',official['edit_prompt']).replace('FULL_CONTEXT_TEMPLATE.txt','GENERIC_RETENTION_TEMPLATE.txt').replace("clip_valid_count('0','67/25'),65","clip_valid_count('0','1001/320'),76").replace("clip_nearest_map(row['source']['actual_pts_rational'],0,66,65)+[66]*8","clip_nearest_map(row['source']['actual_pts_rational'],0,74,76)+[74]*14").replace('list(range(65,73))','list(range(76,90))').replace('0,64,0,50,6,15','0,75,0,50,6,15');p.write_text(t)
sys.path.insert(0,str(R/'scripts'));import r135_contract as contract
for c in scientific['cases']:put(R/'configs/graphs'/(c['run_id']+'.json'),contract.expected_graph(R,c))
for rel,v in num.items():v.update(parent_file=str(P/rel),parent_sha256=sha(P/rel),current_sha256=sha(R/rel),byte_equal=sha(P/rel)==sha(R/rel));assert v['byte_equal']
put(R/'configs/runtime_kernel_hashes.json',num);put(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()})
put(R/'audit/INHERITED_BYTE_BINDINGS.json',{'parent_r128_seal_sha256':sha(P/'deploy_manifest.json'),'six_numerical_files':num,'inputs':files})
put(R/'audit/ROOT_DESIGN_BINDINGS.json',{str(p.relative_to(R)):sha(p) for p in (R/'design').iterdir() if p.is_file()})
put(R/'audit/SMALL_DIFF.json',{'parent':str(P),'source':S,'changes':['R135 run/output namespace','90total76valid complete75frame23.976fpssource','Official edit verbatim plus H3 binding and generic retention; no caption narratives','GPU2 port8612 with exact R130 GPU3 peer'],'same_six_numerical_files':True,'GPU_started':False})
print(R)
