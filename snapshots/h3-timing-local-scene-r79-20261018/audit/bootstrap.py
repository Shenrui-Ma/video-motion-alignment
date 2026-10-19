from pathlib import Path
from fractions import Fraction
import shutil,json,hashlib,math,re
ROOT=Path(__file__).resolve().parents[1]
OLD=Path('/Users/researcher/DevProjects/h3-timing-ivebench-body-r76-20261018')
SOURCE=Path('/Users/researcher/DevProjects/h3-ivebench-expanded-metrics-r73-20261018/audit/benchmark_task_scope_20261018/source_candidate_review')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
manifest=read(OLD/'deploy_manifest.json'); kernels=read(OLD/'configs/runtime_kernel_hashes.json')
for rel,spec in manifest['files'].items():
 p=OLD/rel
 assert sha(p)==spec['sha256'],rel
 if rel=='PREPARED_INPUTS_MANIFEST.json' or rel.startswith(('configs/graphs/','configs/prompts/','configs/source_selection/','design/')):continue
 dest=ROOT/rel;dest.parent.mkdir(parents=True,exist_ok=True)
 if rel.startswith('source_snapshot/') or rel in kernels:shutil.copyfile(p,dest);continue
 if p.suffix in ('.py','.json','.txt'):
  s=p.read_text().replace('r76','r79').replace('R76','R79').replace('timing_ivebench_body_r79','timing_local_scene_r79').replace('h3-timing-ivebench-body-r79','h3-timing-local-scene-r79')
  dest.write_text(s)
 else:shutil.copyfile(p,dest)
for name in ['admission.json','queue.json']:
 put(ROOT/'configs'/name,read(OLD/'configs'/name))
(ROOT/'scripts/r76_contract.py').rename(ROOT/'scripts/r79_contract.py')
ids=['short_0144','short_0166']; lengths=[(107,104),(124,123)]
for name in ['P1_TEMPLATE.txt','P1_TEMPLATE_DRAFT.txt']:
 (ROOT/'design').mkdir(exist_ok=True);shutil.copyfile(OLD/'design'/name,ROOT/'design'/name)
put(ROOT/'design/PROMPT_DECISION.json',dict(status='ROOT_APPROVED_AFTER_R71_ACTUAL_P1_VISUAL_REVIEW',template_sha256=sha(ROOT/'design/P1_TEMPLATE.txt'),template_origin=str(OLD/'design/P1_TEMPLATE.txt'),current_scope='Root authorized official full 0144/0166 original-scene local edits with unchanged R73/R76 P1 metadata template; Native individually reviewed before forced submission.'))
records={x['id']:x for x in read(SOURCE/'INPUT_RECORDS.json')}; reviews={x['source_id']:x for x in read(SOURCE/'SOURCE_REVIEW.json')['reviews']}
selected=[];plans=[]
for key,(T,N) in zip(ids,lengths):
 x=records[key];pts=[Fraction(str(p)) for p in x['original_pts_s']]; assert all(p==Fraction(i,25) for i,p in enumerate(pts)); assert N==math.ceil(pts[-1]*24)+1
 mapping=[min(range(len(pts)),key=lambda k:(abs(pts[k]-Fraction(i,24)),k)) for i in range(N)]
 assert mapping[-1]==x['frame_count']-1
 selected.append(dict(source_id=key,official_task=x['official_task'],source_file=dict(file=x['source'],sha256=x['source_sha256'],url=x['url'],bytes=x['bytes']),source_only_review=reviews[key],generated_h3_results_consulted=0,generated_outputs_consulted=0))
 plans.append(dict(pair_id=key,**x['official_task'],source=dict(file=x['source'],sha256=x['source_sha256'],frame_count=x['frame_count'],actual_pts_s=x['original_pts_s'],actual_pts_rational=[str(p) for p in pts],width=x['geometry'][0],height=x['geometry'][1],time_base='1/12800'),input_protocol=dict(fps=24,effective_frame_count=N,h3_frame_count=T,input_to_original_frame=mapping+[mapping[-1]]*(T-N),effective_input_to_original_frame=mapping,terminal_padding_count=T-N,rule='N=ceil(last original rational PTS*24)+1; nearest original PTS for each t/24, ties earlier; repeat final frame to minimum T=17k+5; exclude padded indices from evaluation.',max_nearest_source_pts_distance_s=max(float(abs(pts[k]-Fraction(i,24))) for i,k in enumerate(mapping))),source_only_review=reviews[key]))
sel=ROOT/'configs/source_selection/SELECTED_2_MANIFEST.json';put(sel,dict(schema='r79-source-only-selected-two-v1',selected_order=ids,selection_before_generation=True,source_candidate_manifest_sha256=sha(SOURCE/'MANIFEST.json'),groups={'background_object':['short_0144'],'animal_subject':['short_0166']},pairs=selected))
put(ROOT/'configs/source_selection_hashes.json',{sel.name:sha(sel)})
plan=ROOT/'design/INPUT_PLAN.json';put(plan,dict(schema='r79-source-input-plan-v1',selection_before_generation=True,generated_h3_results_consulted=0,selected_order=ids,pairs=plans))
for rel in ['scripts/r79_contract.py','scripts/input_contract.py','scripts/prepare_inputs.py','scripts/preflight.py']:
 p=ROOT/rel;s=p.read_text()
 s=s.replace("('short_0131','short_0178','short_0090','short_0055','short_0321')",repr(tuple(ids)))
 s=s.replace("['short_0131','short_0178','short_0090','short_0055','short_0321']",repr(ids))
 s=s.replace("['all','short_0131','short_0178','short_0090','short_0055','short_0321']",repr(['all']+ids))
 s=re.sub(r'^SOURCE_LENGTHS=.*$', 'SOURCE_LENGTHS='+repr(dict(zip(ids,lengths))),s,flags=re.M)
 s=re.sub(r'^LENGTHS=.*$', 'LENGTHS='+repr(tuple(lengths)),s,flags=re.M)
 s=re.sub(r"^SELECTION_SHA = '[^']+'$",'SELECTION_SHA = '+repr(sha(plan)),s,flags=re.M)
 s=s.replace('len(s[\'cases\'])==10','len(s[\'cases\'])==4').replace('SELECTED_5_MANIFEST','SELECTED_2_MANIFEST').replace("'sources':5","'sources':2").replace('fixed five paired','fixed two paired').replace('five source-selected','two source-selected').replace('Five source-selected','Two source-selected')
 p.write_text(s)
runtime=read(OLD/'configs/runtime.json');runtime.update(remote_root='/data3/researcher/h3_runs/timing_local_scene_r79_20261018',gpu_uuid='GPU-REDACTED',expected_gpu_index=7,port=8545,profile='host41_gpu7_r79_normal_reserve8',profile_scope='R76 numerical runtime inherited; actual R79 main capacity and quality pending. Manual individual submissions only.');put(ROOT/'configs/runtime.json',runtime)
put(ROOT/'configs/queue.json',dict(jobs=[f'r79_{s}_seed2026101701_{a}' for s in ids for a in ['native','forced']],finalize=False))
a=read(ROOT/'configs/admission.json');a['ready_for_launch']=False;put(ROOT/'configs/admission.json',a)
rules=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/audit/task_fidelity_review_20261018/NEXT_EVALUATION_RULES.txt');shutil.copyfile(rules,ROOT/'design/NEXT_EVALUATION_RULES.txt')
put(ROOT/'design/EVALUATION_RULES_BINDING.json',dict(source=str(rules),sha256=sha(rules),fixed_case_denominator=2,priorities=['requested edit completion','unedited scene and subject preservation','source action content preservation','physical timing for valid retained-action pairs'],visibility_notes={k:reviews[k]['visibility'] for k in ids}))
put(ROOT/'audit/PARENT_INHERITANCE.json',dict(parent=str(OLD),seal_sha256=sha(OLD/'deploy_manifest.json'),numeric_modules={k:dict(before=sha(OLD/k),after=sha(ROOT/k)) for k in kernels}))
print('prepared initial files',sha(plan))
