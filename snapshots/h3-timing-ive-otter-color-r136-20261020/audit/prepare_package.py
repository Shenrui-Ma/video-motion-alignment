"""Single animal-color source over the R135 executor; CPU preparation only."""
from pathlib import Path
import copy,hashlib,json,os,re,shutil,sys,time
R=Path(__file__).resolve().parents[1]; P=R.parent/'h3-timing-ive-subject-replacement-r135-20261020'; S='short_0235'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def cp(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
assert not (R/'deploy_manifest.json').exists()
parent_seal=read(P/'deploy_manifest.json');num=read(P/'configs/runtime_kernel_hashes.json')
for rel,item in parent_seal['files'].items():
    assert sha(P/rel)==item['sha256'],rel
    if rel.startswith(('configs/graphs/','configs/prompts/','design/','configs/source_selection/','inputs/')):continue
    dst=rel.replace('r135_contract.py','r136_contract.py'); out=R/dst;out.parent.mkdir(parents=True,exist_ok=True)
    if rel.endswith('.py') and not rel.startswith('source_snapshot/') and rel not in num:
        out.write_text((P/rel).read_text().replace('r135','r136').replace('R135','R136'))
    else:cp(P/rel,out)
for d in ['input','output','temp','user','custom_nodes','processes','logs','configs/graphs','configs/prompts','audit/router','audit/x0','configs/source_selection']:(R/d).mkdir(parents=True,exist_ok=True)
row=read(R/'design/INPUT_PLAN.json')['pairs'][0];official=row['official_task'];version='IVEBench-edit-with-generic-retention-v1'
assert row['input_protocol']['h3_frame_count']==row['input_protocol']['effective_frame_count']==90
prompt="subject_definitions:\n<Video 1> is the source video for this edit.\n\nsummary:\n[video editing] The target video is an edited version of <Video 1>.\n"+official['edit_prompt']+"\n\nretention_analysis:\n<Video 1>: partially_preserved - Preserve the source video's people, scene, framing, camera motion, and actions, except for changes explicitly requested in the summary.\n"
assert official['source_prompt'] not in prompt and official['target_prompt'] not in prompt
event_path=R.parent/'h3-timing-architecture-r2-20261016/audit/new_source_full_review_20261020/short_0235/SOURCE_DECISION.json'
assert sha(event_path)=='f98f0041c706f3cac9a8f76e1eef080e0402f50258296f332da2b6a0168dcc0c'
events=read(event_path);cp(event_path,R/'audit/SOURCE_EVENTS_BEFORE_OUTPUT.json')
brackets={'head_sideways': [17,20], 'head_returns_down': [27,30]}
mapping=row['input_protocol']['input_to_original_frame']
mapped={k:[i for i,n in enumerate(mapping) if bounds[0]<=n<=bounds[1]] for k,bounds in brackets.items()}
put(R/'design/REFERENCE_EVENT_REVIEW_PLAN.json',{'schema':'r136-source-event-review-plan-v1','evaluation_only':True,'items':[{'source_id':S,'reference_original_frame_brackets':brackets,'clip_original_frames':[0,112]}],'source_event_path':str(event_path),'source_event_sha256':sha(event_path),'prepared_frame_supports':mapped,'scope':events['phase_definition'],'observer_scope':'Animal head motion; human arm observer is not used.'})
files={}
for kind,suffix in [('original','original.mp4'),('video','video.mp4'),('provenance','provenance.json'),('prompt','prompt.txt')]:
    f=R/'inputs'/f'{S}_{suffix}';files[kind]={'file':str(f.relative_to(R)),'sha256':sha(f),'bytes':f.stat().st_size}
put(R/'PREPARED_INPUTS_MANIFEST.json',{'schema':'r136-prepared-input-v1','input_plan_sha256':sha(R/'design/INPUT_PLAN.json'),'pairs':[{'pair_id':S,'files':files,'h3_frames':90,'valid_frames':90,'clip':row['clip'],'scope':'animal_color_edit','evaluation_scope':row['evaluation_scope']}]})
for rel in [f'configs/prompts/{S}.txt',f'design/{S}_actual_prompt.txt','design/GENERIC_RETENTION_TEMPLATE.txt']:(R/rel).write_text(prompt)
case=copy.deepcopy(row);case.update(prompt_file=str(R/'configs/prompts'/f'{S}.txt'),prompt_sha256=sha(R/'configs/prompts'/f'{S}.txt'),task_scope='animal_color_edit',source_acceptance=events['task_acceptance'])
put(R/'design/PROPOSAL.json',{'schema':'r136-generic-retention-single-source-v1','created_unix':time.time(),'state':'CPU prepared; no GPU dispatch','cases':[case],'method':'Inherited Native then conditional fixed attention output intervention, steps6..14,20 Euler predictions','prompt_protocol':version,'scope':events['method_scope'],'native_acceptance':events['task_acceptance'],'guide_gate':'Task succeeds and visible temporal deviation is clear; no human-arm observer claim.'})
put(R/'design/PROMPT_PROTOCOL.json',{'version':version,'official_fields':official,'actual_prompt_sha256':case['prompt_sha256'],'rule':'Official edit_prompt verbatim with source binding and generic retention. Source/target captions are metadata only. No added motion narrative or event times. Native and forced use the same prompt.'})
put(R/'configs/source_selection/SELECTED_SOURCE_MANIFEST.json',{'pairs':[row],'root_proposal_sha256':sha(R/'design/PROPOSAL.json'),'root_review_events_sha256':sha(R/'design/REFERENCE_EVENT_REVIEW_PLAN.json')})
put(R/'configs/source_selection_hashes.json',{f.name:sha(f) for f in (R/'configs/source_selection').iterdir()})
runtime=read(P/'configs/runtime.json');runtime.update(remote_root='/home/researcher/h3_runs/timing_ive_otter_color_r136_20261020',port=8614,gpu_uuid='GPU-REDACTED',expected_gpu_index=3,profile='host9_gpu3_r136_normal_reserve8',profile_scope='Single animal color edit; exact R135 GPU2 peer registered',status='CPU_PREPARED');put(R/'configs/runtime.json',runtime)
put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
put(R/'audit/PEER_PLAN.json',{'host':'H3_SERVER_A','own_gpu_index':3,'own_gpu_uuid':runtime['gpu_uuid'],'peer_remote_root':'/home/researcher/h3_runs/timing_ive_subject_replacement_r135_20261020','peer_gpu_index':2,'peer_pid':21602,'peer_start_ticks':'2648509732','max_own_gpus':2,'fresh_identity_capacity_and_port_required':True,'GPU_started':False,'predecessor_release':'R130 and caption/scrubs MF exact release must be recorded.'})
scientific=read(P/'configs/scientific_contract.json');scientific.update(schema='r136-generic-retention-single-source-v1',source_ids=[S],case_order=[],cases=[],purpose='Change the sea otter fur to green while preserving the source scene and visible head motion',prompt_version=version,prompt_sha256={S:case['prompt_sha256']});scientific['screening']['schema']='r136-native-screen-policy-v1'
for old in read(P/'configs/scientific_contract.json')['cases']:
    c=copy.deepcopy(old);arm=c['arm'];c.update(run_id=f'r136_{S}_seed2026101701_{arm}',source_id=S,prompt=prompt,prompt_version=version,prompt_sha256=case['prompt_sha256'],video=f'{S}_video.mp4',video_sha256=files['video']['sha256'],provenance=f'{S}_provenance.json',provenance_sha256=files['provenance']['sha256'],original_source=row['source'],geometry={'width':1312,'height':736,'frames':90,'fps':24},valid_frame_count=90,original_task=official,clip=row['clip'],task_scope='animal_color_edit',evaluation_scope=row['evaluation_scope']);scientific['cases'].append(c);scientific['case_order'].append(c['run_id'])
for k,rel in [('input_plan_sha256','design/INPUT_PLAN.json'),('prepared_input_manifest_sha256','PREPARED_INPUTS_MANIFEST.json'),('source_selection_sha256','configs/source_selection/SELECTED_SOURCE_MANIFEST.json'),('root_proposal_sha256','design/PROPOSAL.json'),('root_event_review_sha256','design/REFERENCE_EVENT_REVIEW_PLAN.json')]:scientific[k]=sha(R/rel)
scientific['evaluation'].update(official='Original short0235 edit_prompt with generic source retention; source/target captions stored as metadata',rules_sha256=scientific['source_selection_sha256'],task_scopes={S:'animal_color_edit'},source_extent_scopes={S:row['evaluation_scope']})
scientific['acceleration_axes']['postprocessing']='112 original frames at30000/1001 fps mapped by nearest physical PTS to90 valid frames at24fps. All90 model frames are valid; no pure padding. No interpolation.'
put(R/'configs/scientific_contract.json',scientific);put(R/'configs/queue.json',{'jobs':scientific['case_order'],'finalize':True})
p=R/'scripts/r136_contract.py';t=p.read_text().replace('short_0084',S).replace('(90, 76)','(90, 90)').replace('One subject replacement','One animal color edit');p.write_text(t)
p=R/'scripts/input_contract.py';p.write_text(p.read_text().replace('short_0084',S).replace('(90, 76)','(90, 90)'))
p=R/'scripts/prepare_inputs.py';t=p.read_text().replace('short_0084',S).replace('Prepare three source-selected official inputs','Prepare one source-selected official input');p.write_text(re.sub(r'^SELECTION_SHA = .*$',f'SELECTION_SHA = {sha(R/"design/INPUT_PLAN.json")!r}',t,flags=re.M))
p=R/'analysis/postrun/verify_pair.py';p.write_text(p.read_text().replace('One complete3.128125-second source','One complete3.737067-second source'))
p=R/'tests/test_single_source_contract.py';t=p.read_text().replace('short_0084',S).replace('Replace the man with a woman',official['edit_prompt']).replace("clip_valid_count('0','1001/320'),76","clip_valid_count('0','14014/3750'),90").replace("clip_nearest_map(row['source']['actual_pts_rational'],0,74,76)+[74]*14","clip_nearest_map(row['source']['actual_pts_rational'],0,111,90)").replace('list(range(76,90))','[]').replace('0,75,0,50,6,15','0,89,0,50,6,15');p.write_text(t)
sys.path.insert(0,str(R/'scripts'));import r136_contract as contract
for c in scientific['cases']:put(R/'configs/graphs'/(c['run_id']+'.json'),contract.expected_graph(R,c))
for rel,v in num.items():v.update(parent_file=str(P/rel),parent_sha256=sha(P/rel),current_sha256=sha(R/rel),byte_equal=sha(P/rel)==sha(R/rel));assert v['byte_equal']
put(R/'configs/runtime_kernel_hashes.json',num);put(R/'configs/input_hashes.json',{f.name:sha(f) for f in (R/'inputs').iterdir()})
put(R/'audit/INHERITED_BYTE_BINDINGS.json',{'parent_r135_seal_sha256':sha(P/'deploy_manifest.json'),'six_numerical_files':num,'inputs':files})
put(R/'audit/ROOT_DESIGN_BINDINGS.json',{str(f.relative_to(R)):sha(f) for f in (R/'design').iterdir() if f.is_file()})
put(R/'audit/SMALL_DIFF.json',{'parent':str(P),'source':S,'changes':['R136 namespace;GPU3 port8614','112 original at30000/1001fps to90 valid/90total24fps','Official otter color edit verbatim; same generic prompt envelope','Source-only head-turn phases; human observer outside scope'],'same_six_numerical_files':True,'GPU_started':False})
print(json.dumps({'root':str(R),'prepared_events':mapped,'prompt_sha256':case['prompt_sha256']}))
