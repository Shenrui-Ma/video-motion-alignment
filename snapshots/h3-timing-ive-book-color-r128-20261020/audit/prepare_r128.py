"""Prepare one new source using the existing R125 executor; no GPU action."""
from pathlib import Path
import copy,hashlib,json,re,shutil,sys,time
R=Path(__file__).resolve().parents[1];P=R.parent/'h3-timing-ive-board-edit-r125-20261020';B=R.parent/'h3-ive-short-source-selection-20261020';S='short_0362'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def cp(a,b):
 b.parent.mkdir(parents=True,exist_ok=True)
 if Path(a).suffix=='.mp4':
  import os;os.link(a,b)
 else:shutil.copy2(a,b)
assert not (R/'deploy_manifest.json').exists();seal=read(P/'deploy_manifest.json');num=read(P/'configs/runtime_kernel_hashes.json')
for rel,x in seal['files'].items():
 assert sha(P/rel)==x['sha256'],rel
 if rel.startswith(('configs/graphs/','configs/prompts/','design/','configs/source_selection/','inputs/')):continue
 dst=rel.replace('r125_contract.py','r128_contract.py');cp(P/rel,R/dst)
 if rel.endswith('.py') and not rel.startswith('source_snapshot/') and rel not in num:
  p=R/dst;p.write_text(p.read_text().replace('r125','r128').replace('R125','R128'))
for f in ['input','output','temp','user','custom_nodes','processes','logs','configs/graphs','configs/prompts','audit/router','audit/x0','design','configs/source_selection']:(R/f).mkdir(parents=True,exist_ok=True)
row=copy.deepcopy(next(x for x in read(B/'R122_SIX_SOURCE_INPUT_PLAN.json')['pairs'] if x['source_id']==S));official=row['official_task'];draft=B/'full_context_draft_20261020'/S
prompt=(draft/'context_ir_draft.txt').read_text()
for k in ['source_prompt','edit_prompt','target_prompt']:assert (draft/(k+'.txt')).read_text()==official[k] and official[k] in prompt
plan={'schema':'r128-source-selected-excerpt-v1','pairs':[row],'created_unix':time.time()};put(R/'design/INPUT_PLAN.json',plan)
evpath=B/'audit/short0362_source_events/SOURCE_EVENTS_BEFORE_OUTPUT.json';ev=read(evpath)
events={'schema':'r128-source-event-review-plan-v1','evaluation_only':True,'items':[{'source_id':S,'reference_original_frame_brackets':{x['event_id']:x['source_original_frame_interval_inclusive'] for x in ev['events']},'clip_original_frames':[0,67]}]};put(R/'design/REFERENCE_EVENT_REVIEW_PLAN.json',events);cp(evpath,R/'audit/SOURCE_EVENTS_BEFORE_OUTPUT.json')
files={}
for kind,src in [('original',Path(row['source']['file'])),('video',B/'prepared_media'/f'{S}_video.mp4'),('provenance',B/'prepared_media'/f'{S}_provenance.json')]:
 name=f'{S}_{kind}.mp4' if kind in ['video','original'] else f'{S}_provenance.json';cp(src,R/'inputs'/name);files[kind]={'file':'inputs/'+name,'sha256':sha(src),'bytes':src.stat().st_size}
(R/'inputs'/f'{S}_prompt.txt').write_text(official['edit_prompt']);f=R/'inputs'/f'{S}_prompt.txt';files['prompt']={'file':str(f.relative_to(R)),'sha256':sha(f),'bytes':f.stat().st_size}
prepared={'schema':'r128-prepared-input-v1','input_plan_sha256':sha(R/'design/INPUT_PLAN.json'),'pairs':[{'pair_id':S,'files':files,'h3_frames':73,'valid_frames':65,'clip':row['clip'],'scope':'held_object_color','evaluation_scope':'IVEBench完整短片探索'}]};put(R/'PREPARED_INPUTS_MANIFEST.json',prepared)
for rel in [f'configs/prompts/{S}.txt',f'design/{S}_actual_prompt.txt','design/FULL_CONTEXT_TEMPLATE.txt']:(R/rel).write_text(prompt)
pr=copy.deepcopy(row);pr.update(prompt_file=str(R/'configs/prompts'/f'{S}.txt'),prompt_sha256=sha(R/'configs/prompts'/f'{S}.txt'),task_scope='held_object_color',source_acceptance=ev['task_acceptance'])
proposal={'schema':'r128-full-context-single-source-v1','created_unix':time.time(),'state':'CPU prepared; after root CPU review; concurrent with exact R126 peer','cases':[pr],'method':'Inherited fixed6..14 routing; identical full Context-IR per pair','prompt_protocol':'IVEBench-official-fields-full-Context-IR-v1'};put(R/'design/PROPOSAL.json',proposal)
put(R/'design/PROMPT_PROTOCOL.json',{'version':proposal['prompt_protocol'],'official_fields':official,'template_source':str(draft/'context_ir_draft.txt'),'template_sha256':sha(draft/'context_ir_draft.txt'),'rule':'Same prompt for Native and forced, official source/edit/target text verbatim; generic retention, no action timings'})
selected={'pairs':[row],'root_proposal_sha256':sha(R/'design/PROPOSAL.json'),'root_review_events_sha256':sha(R/'design/REFERENCE_EVENT_REVIEW_PLAN.json')};put(R/'configs/source_selection/SELECTED_SOURCE_MANIFEST.json',selected);put(R/'configs/source_selection_hashes.json',{p.name:sha(p) for p in (R/'configs/source_selection').iterdir()})
runtime=read(P/'configs/runtime.json');runtime.update(remote_root='/home/researcher/h3_runs/timing_ive_book_color_r128_20261020',gpu_uuid='GPU-REDACTED',port=8602,expected_gpu_index=2,profile='host9_gpu2_r128_normal_reserve8',profile_scope='Single book color edit; R126 GPU3 exact peer registered',status='CPU_PREPARED');put(R/'configs/runtime.json',runtime);put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
s=read(P/'configs/scientific_contract.json');s.update(schema='r128-full-context-single-source-v1',source_ids=[S],case_order=[],cases=[],purpose='Blue book cover changed to red, preserving people and paper movement',prompt_sha256={S:sha(R/'configs/prompts'/f'{S}.txt')});s['screening']['schema']='r128-native-screen-policy-v1'
for old in read(P/'configs/scientific_contract.json')['cases']:
 c=copy.deepcopy(old);arm=c['arm'];c.update(run_id=f'r128_{S}_seed2026101701_{arm}',source_id=S,prompt=prompt,prompt_sha256=s['prompt_sha256'][S],video=f'{S}_video.mp4',video_sha256=files['video']['sha256'],provenance=f'{S}_provenance.json',provenance_sha256=files['provenance']['sha256'],original_source=row['source'],geometry={'width':1312,'height':736,'frames':73,'fps':24},valid_frame_count=65,original_task=official,clip=row['clip'],task_scope='held_object_color',evaluation_scope='IVEBench完整短片探索');s['cases'].append(c);s['case_order'].append(c['run_id'])
for k,rel in [('input_plan_sha256','design/INPUT_PLAN.json'),('prepared_input_manifest_sha256','PREPARED_INPUTS_MANIFEST.json'),('source_selection_sha256','configs/source_selection/SELECTED_SOURCE_MANIFEST.json'),('root_proposal_sha256','design/PROPOSAL.json'),('root_event_review_sha256','design/REFERENCE_EVENT_REVIEW_PLAN.json')]:s[k]=sha(R/rel)
s['evaluation'].update(official='Original short0362 source/edit/target fields, complete short source',rules_sha256=s['source_selection_sha256'],task_scopes={S:'held_object_color'},source_extent_scopes={S:'IVEBench完整短片探索'})
s['acceleration_axes']['postprocessing']='65 valid frames at24fps; frames65..72 are repeated padding and excluded from evaluation. No interpolation.';put(R/'configs/scientific_contract.json',s);put(R/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
p=R/'scripts/r128_contract.py';p.write_text(p.read_text().replace("SOURCES=('long_0031',)","SOURCES=('short_0362',)").replace("SOURCE_LENGTHS={'long_0031': (107, 106)}","SOURCE_LENGTHS={'short_0362': (73, 65)}"))
p=R/'scripts/input_contract.py';p.write_text(p.read_text().replace("SOURCES=('long_0031',)","SOURCES=('short_0362',)").replace('LENGTHS=((107, 106),)','LENGTHS=((73, 65),)'))
p=R/'scripts/prepare_inputs.py';p.write_text(re.sub(r'^SELECTION_SHA = .*$',f'SELECTION_SHA = {sha(R/"design/INPUT_PLAN.json")!r}',p.read_text().replace('long_0031','short_0362'),flags=re.M))
p=R/'analysis/postrun/verify_pair.py';p.write_text(p.read_text().replace('One preselected4.4-second source excerpt','One complete2.68-second source'))
p=R/'tests/test_single_source_contract.py';t=p.read_text().replace('long_0031','short_0362').replace('Replace the wooden cutting board with a marble cutting board',official['edit_prompt']).replace("clip_valid_count('0','22/5'),106","clip_valid_count('0','67/25'),65").replace("clip_nearest_map(row['source']['actual_pts_rational'],0,109,106)+[109]","clip_nearest_map(row['source']['actual_pts_rational'],0,66,65)+[66]*8").replace("p['padding_indices'],[106]","p['padding_indices'],list(range(65,73))").replace('0,105,0,50,6,15','0,64,0,50,6,15');p.write_text(t)
sys.path.insert(0,str(R/'scripts'));import r128_contract as c
for row in s['cases']:put(R/'configs/graphs'/(row['run_id']+'.json'),c.expected_graph(R,row))
for rel,v in num.items():v.update(parent_file=str(P/rel),parent_sha256=sha(P/rel),current_sha256=sha(R/rel),byte_equal=sha(P/rel)==sha(R/rel));assert v['byte_equal']
put(R/'configs/runtime_kernel_hashes.json',num);put(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()});put(R/'audit/INHERITED_BYTE_BINDINGS.json',{'parent_r125_seal_sha256':sha(P/'deploy_manifest.json'),'six_numerical_files':num,'inputs':files});put(R/'audit/ROOT_DESIGN_BINDINGS.json',{str(p.relative_to(R)):sha(p) for p in (R/'design').iterdir() if p.is_file()})
put(R/'audit/SMALL_DIFF.json',{'parent':str(P),'source':S,'changes':['namespace/output R128','73total65valid full source0–2.68s','full Context-IR exact official fields for book cover color edit','GPU2 port8602 with R126 GPU3 peer'],'same_numerical_files':True,'GPU_started':False})
print(R)
