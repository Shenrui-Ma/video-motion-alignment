"""Prepare one new source using the existing R124 executor; no GPU action."""
from pathlib import Path
import copy,hashlib,json,re,shutil,sys,time
R=Path(__file__).resolve().parents[1];P=R.parent/'h3-timing-ive-full-context-r124-20261020';B=R.parent/'h3-timing-ive-official-prompt-r120-20261019';S='long_0059'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def cp(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
assert not (R/'deploy_manifest.json').exists();seal=read(P/'deploy_manifest.json');num=read(P/'configs/runtime_kernel_hashes.json')
for rel,x in seal['files'].items():
 assert sha(P/rel)==x['sha256'],rel
 if rel.startswith(('configs/graphs/','configs/prompts/','design/','configs/source_selection/','inputs/')):continue
 dst=rel.replace('r124_contract.py','r126_contract.py');cp(P/rel,R/dst)
 if rel.endswith('.py') and not rel.startswith('source_snapshot/') and rel not in num:
  p=R/dst;p.write_text(p.read_text().replace('r124','r126').replace('R124','R126'))
for f in ['input','output','temp','user','custom_nodes','processes','logs','configs/graphs','configs/prompts','audit/router','audit/x0','design','configs/source_selection']:(R/f).mkdir(parents=True,exist_ok=True)
row=copy.deepcopy(next(x for x in read(B/'design/INPUT_PLAN.json')['pairs'] if x['source_id']==S));official=row['official_task']
parent_case=read(P/'configs/scientific_contract.json')['cases'][0];prompt=(P/'configs/prompts/long_0163.txt').read_text()
for k in ['source_prompt','edit_prompt','target_prompt']:prompt=prompt.replace(parent_case['original_task'][k],official[k])
prompt=prompt.replace('the person wearing the light blue suit in <Video 1>.','the hand of the bald man in the black shirt in <Video 1>.').replace('the other person in <Video 1>.','the bald man, including his face and black shirt, in <Video 1>.').replace('the office scene, desk, laptop, and documents in <Video 1>.','the remaining source scene and objects in <Video 1>.')
for k in ['source_prompt','edit_prompt','target_prompt']:assert official[k] in prompt

plan={'schema':'r126-source-selected-excerpt-v1','pairs':[row],'created_unix':time.time()};put(R/'design/INPUT_PLAN.json',plan)
evpath=B/'design/REFERENCE_EVENT_REVIEW_PLAN.json';ev=read(evpath);events=copy.deepcopy(ev);events['items']=[x for x in ev['items'] if x['source_id']==S];events['evaluation_only']=True;put(R/'design/REFERENCE_EVENT_REVIEW_PLAN.json',events);cp(evpath,R/'audit/PREVIOUS_SOURCE_EVENT_REVIEW_PLAN.json')
files={}
for kind,src in [('original',Path(row['source']['file'])),('video',B/'inputs'/f'{S}_video.mp4'),('provenance',B/'inputs'/f'{S}_provenance.json')]:
 name=f'{S}_{kind}.mp4' if kind in ['video','original'] else f'{S}_provenance.json';cp(src,R/'inputs'/name);files[kind]={'file':'inputs/'+name,'sha256':sha(src),'bytes':src.stat().st_size}
(R/'inputs'/f'{S}_prompt.txt').write_text(official['edit_prompt']);f=R/'inputs'/f'{S}_prompt.txt';files['prompt']={'file':str(f.relative_to(R)),'sha256':sha(f),'bytes':f.stat().st_size}
prepared={'schema':'r126-prepared-input-v1','input_plan_sha256':sha(R/'design/INPUT_PLAN.json'),'pairs':[{'pair_id':S,'files':files,'h3_frames':158,'valid_frames':144,'clip':row['clip'],'scope':'hand_object_addition','evaluation_scope':'IVEBench素材片段探索'}]};put(R/'PREPARED_INPUTS_MANIFEST.json',prepared)
for rel in [f'configs/prompts/{S}.txt',f'design/{S}_actual_prompt.txt','design/FULL_CONTEXT_TEMPLATE.txt']:(R/rel).write_text(prompt)
pr=copy.deepcopy(row);pr.update(prompt_file=str(R/'configs/prompts'/f'{S}.txt'),prompt_sha256=sha(R/'configs/prompts'/f'{S}.txt'),task_scope='hand_object_addition',source_acceptance='Add the white handkerchief while retaining the same man, camera, scene and visible wiping action.')
proposal={'schema':'r126-full-context-single-source-v1','created_unix':time.time(),'state':'CPU prepared; after current R124/R125 scheduling and exact release','cases':[pr],'method':'Inherited fixed6..14 routing; identical full Context-IR per pair','prompt_protocol':'IVEBench-official-fields-full-Context-IR-v1'};put(R/'design/PROPOSAL.json',proposal)
put(R/'design/PROMPT_PROTOCOL.json',{'version':proposal['prompt_protocol'],'official_fields':official,'template_source':str(P/'configs/prompts/long_0163.txt'),'template_sha256':sha(P/'configs/prompts/long_0163.txt'),'rule':'Same prompt for Native and forced, official source/edit/target text verbatim; generic retention, no action timings'})
selected={'pairs':[row],'root_proposal_sha256':sha(R/'design/PROPOSAL.json'),'root_review_events_sha256':sha(R/'design/REFERENCE_EVENT_REVIEW_PLAN.json')};put(R/'configs/source_selection/SELECTED_SOURCE_MANIFEST.json',selected);put(R/'configs/source_selection_hashes.json',{p.name:sha(p) for p in (R/'configs/source_selection').iterdir()})
runtime=read(P/'configs/runtime.json');runtime.update(remote_root='/home/researcher/h3_runs/timing_ive_handkerchief_full_context_r126_20261020',gpu_uuid='GPU-REDACTED',port=8598,expected_gpu_index=3,profile='host9_gpu3_r126_normal_reserve8',profile_scope='Single handkerchief edit after R125 release; current own peer registered at dispatch',status='CPU_PREPARED');put(R/'configs/runtime.json',runtime);put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
s=read(P/'configs/scientific_contract.json');s.update(schema='r126-full-context-single-source-v1',source_ids=[S],case_order=[],cases=[],purpose='Add white handkerchief with full Context-IR; keep the visible wiping action',prompt_sha256={S:sha(R/'configs/prompts'/f'{S}.txt')});s['screening']['schema']='r126-native-screen-policy-v1'
for old in read(P/'configs/scientific_contract.json')['cases']:
 c=copy.deepcopy(old);arm=c['arm'];c.update(run_id=f'r126_{S}_seed2026101701_{arm}',source_id=S,prompt=prompt,prompt_sha256=s['prompt_sha256'][S],video=f'{S}_video.mp4',video_sha256=files['video']['sha256'],provenance=f'{S}_provenance.json',provenance_sha256=files['provenance']['sha256'],original_source=row['source'],geometry={'width':1312,'height':736,'frames':158,'fps':24},valid_frame_count=144,original_task=official,clip=row['clip'],task_scope='hand_object_addition',evaluation_scope='IVEBench素材片段探索');s['cases'].append(c);s['case_order'].append(c['run_id'])
for k,rel in [('input_plan_sha256','design/INPUT_PLAN.json'),('prepared_input_manifest_sha256','PREPARED_INPUTS_MANIFEST.json'),('source_selection_sha256','configs/source_selection/SELECTED_SOURCE_MANIFEST.json'),('root_proposal_sha256','design/PROPOSAL.json'),('root_event_review_sha256','design/REFERENCE_EVENT_REVIEW_PLAN.json')]:s[k]=sha(R/rel)
s['evaluation'].update(official='Original long0059 source/edit/target fields, same7–13second excerpt as R120',rules_sha256=s['source_selection_sha256'],task_scopes={S:'hand_object_addition'},source_extent_scopes={S:'IVEBench素材片段探索'})
s['acceleration_axes']['postprocessing']='144 valid frames at24fps; frames144–157 are repeated padding and excluded from evaluation. No interpolation.';put(R/'configs/scientific_contract.json',s);put(R/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
p=R/'scripts/r126_contract.py';p.write_text(p.read_text().replace("SOURCES=('long_0163',)","SOURCES=('long_0059',)").replace("SOURCE_LENGTHS={'long_0163': (158, 144)}","SOURCE_LENGTHS={'long_0059': (158, 144)}"))
p=R/'scripts/input_contract.py';p.write_text(p.read_text().replace("SOURCES=('long_0163',)","SOURCES=('long_0059',)").replace('LENGTHS=((158, 144),)','LENGTHS=((158, 144),)'))
p=R/'scripts/prepare_inputs.py';p.write_text(re.sub(r'^SELECTION_SHA = .*$',f'SELECTION_SHA = {sha(R/"design/INPUT_PLAN.json")!r}',p.read_text().replace('long_0163','long_0059'),flags=re.M))
p=R/'analysis/postrun/verify_pair.py';p.write_text(p.read_text().replace('One preselected six-second source excerpt','One preselected six-second source excerpt'))
p=R/'tests/test_single_source_contract.py';t=p.read_text().replace('long_0163','long_0059').replace('Change the light blue suit to black',official['edit_prompt'].replace("'","\\'")).replace("clip_valid_count('52/25','202/25'),144","clip_valid_count('7','13'),144").replace("clip_nearest_map(row['source']['actual_pts_rational'],52,201,144)+[201]*14","clip_nearest_map(row['source']['actual_pts_rational'],175,324,144)+[324]*14").replace("p['padding_indices'],list(range(144,158))","p['padding_indices'],list(range(144,158))").replace('0,143,0,50,6,15','0,143,0,50,6,15');p.write_text(t)
sys.path.insert(0,str(R/'scripts'));import r126_contract as c
for row in s['cases']:put(R/'configs/graphs'/(row['run_id']+'.json'),c.expected_graph(R,row))
for rel,v in num.items():v.update(parent_file=str(P/rel),parent_sha256=sha(P/rel),current_sha256=sha(R/rel),byte_equal=sha(P/rel)==sha(R/rel));assert v['byte_equal']
put(R/'configs/runtime_kernel_hashes.json',num);put(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()});put(R/'audit/INHERITED_BYTE_BINDINGS.json',{'parent_r124_seal_sha256':sha(P/'deploy_manifest.json'),'six_numerical_files':num,'inputs':files});put(R/'audit/ROOT_DESIGN_BINDINGS.json',{str(p.relative_to(R)):sha(p) for p in (R/'design').iterdir() if p.is_file()})
put(R/'audit/SMALL_DIFF.json',{'parent':str(P),'source':S,'changes':['namespace/output R126','158total144valid originalR120source7–13s','full Context-IR exact official fields for handkerchief edit','GPU3 port8598 after R125 release'],'same_numerical_files':True,'GPU_started':False})
print(R)
