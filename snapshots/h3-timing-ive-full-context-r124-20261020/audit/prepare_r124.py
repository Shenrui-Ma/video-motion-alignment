"""R124 single source deployment; frozen R122 executor, R120 media, full Context-IR."""
from pathlib import Path
import copy, hashlib, json, re, shutil, sys, time
R=Path(__file__).resolve().parents[1]
P=R.parent/'h3-timing-ive-generic-retention-r122-20261020'
I=R.parent/'h3-timing-ive-official-prompt-r120-20261019'
D=R.parent/'h3-ive-short-source-selection-20261020/full_context_draft_20261020/long_0163'
S='long_0163'; VERSION='IVEBench-official-fields-full-Context-IR-v1'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def cp(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
def selected(v,key):return next(x for x in v[key] if x.get('source_id',x.get('pair_id'))==S)
assert not (R/'deploy_manifest.json').exists()
seal=read(P/'deploy_manifest.json');num=read(P/'configs/runtime_kernel_hashes.json')
for rel,meta in seal['files'].items():
 assert sha(P/rel)==meta['sha256'],rel
 if rel.startswith(('configs/graphs/','configs/prompts/','design/','configs/source_selection/')):continue
 dest=rel.replace('r122_contract.py','r124_contract.py');cp(P/rel,R/dest)
 if rel.endswith('.py') and not rel.startswith('source_snapshot/') and rel not in num:
  p=R/dest;p.write_text(p.read_text().replace('r122','r124').replace('R122','R124'))
for folder in ['input','output','temp','user','custom_nodes','processes','logs','configs/graphs','configs/prompts','audit/router','audit/x0','design','configs/source_selection']:(R/folder).mkdir(parents=True,exist_ok=True)
for rel in ['deploy_manifest.json','configs/scientific_contract.json','configs/runtime.json']:cp(P/rel,R/'source_snapshot/r122'/rel)
row=copy.deepcopy(selected(read(I/'design/INPUT_PLAN.json'),'pairs'))
plan={'schema':'r124-existing-source-clip-v1','created_unix':time.time(),'source':'Exact R120 source clip; no resampling changes','pairs':[row]};put(R/'design/INPUT_PLAN.json',plan)
events=read(I/'design/REFERENCE_EVENT_REVIEW_PLAN.json');events['items']=[selected(events,'items')];put(R/'design/REFERENCE_EVENT_REVIEW_PLAN.json',events)
prepared=read(I/'PREPARED_INPUTS_MANIFEST.json');prepared['pairs']=[selected(prepared,'pairs')];prepared['schema']='r124-existing-input-manifest-v1';prepared['input_plan_sha256']=sha(R/'design/INPUT_PLAN.json')
for v in prepared['pairs'][0]['files'].values():
 name=Path(v['file']).name;assert sha(I/'inputs'/name)==v['sha256'];cp(I/'inputs'/name,R/'inputs'/name)
put(R/'PREPARED_INPUTS_MANIFEST.json',prepared)
prompt=(D/'context_ir_draft.txt').read_text();official=row['official_task']
for field in ['source_prompt','edit_prompt','target_prompt']:assert (D/(field+'.txt')).read_text()==official[field]
for rel in ['configs/prompts/long_0163.txt','design/long_0163_actual_prompt.txt','design/FULL_CONTEXT_TEMPLATE.txt']:(R/rel).write_text(prompt)
proposalrow=copy.deepcopy(row);proposalrow.update(prompt_file=str(R/'configs/prompts/long_0163.txt'),prompt_sha256=sha(R/'configs/prompts/long_0163.txt'),task_scope='main_subject_attribute',source_acceptance='Source-only selection reviewed before generation; preserve original people/desk/document action')
proposal={'schema':'r124-full-context-single-source-v1','created_unix':time.time(),'state':'CPU prepared; root conditioned launch on R123 format review','cases':[proposalrow],'method':'Fixed6..14 temporal routing inherited; Native and forced use identical full Context-IR','prompt_protocol':VERSION}
put(R/'design/PROPOSAL.json',proposal)
put(R/'design/PROMPT_PROTOCOL.json',{'version':VERSION,'official_fields':official,'template_source':str(D/'context_ir_draft.txt'),'template_sha256':sha(D/'context_ir_draft.txt'),'rule':'Official edit/source/target text preserved verbatim. Generic retention and asset links only. Same prompt both arms. No added event timing.'})
sel=read(P/'configs/source_selection/SELECTED_SOURCE_MANIFEST.json');sel['pairs']=[copy.deepcopy(row)];sel['root_proposal_sha256']=sha(R/'design/PROPOSAL.json');sel['root_review_events_sha256']=sha(R/'design/REFERENCE_EVENT_REVIEW_PLAN.json');put(R/'configs/source_selection/SELECTED_SOURCE_MANIFEST.json',sel)
put(R/'configs/source_selection_hashes.json',{p.name:sha(p) for p in (R/'configs/source_selection').iterdir() if p.is_file()})
runtime=read(P/'configs/runtime.json');runtime.update(status='CPU_PREPARED',remote_root='/home/researcher/h3_runs/timing_ive_full_context_r124_20261020',gpu_uuid='GPU-REDACTED',port=8594,expected_gpu_index=2,profile='host9_gpu2_r124_normal_reserve8',profile_scope='Single long0163 full Context-IR, concurrent R122 GPU3 registered peer')
put(R/'configs/runtime.json',runtime);put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
s=read(P/'configs/scientific_contract.json');old=read(I/'configs/scientific_contract.json');s.update(schema='r124-full-context-single-source-v1',source_ids=[S],cases=[],case_order=[],prompt_version=VERSION,purpose='Test original clothing color edit with full Context-IR and original reference action preserved',prompt_protocol='Verbatim official source/edit/target fields in six-section Context-IR; same prompt for Native and forced')
for arm in ['native','forced']:
 c=copy.deepcopy(next(c for c in old['cases'] if c['source_id']==S and c['arm']==arm));c.update(run_id=f'r124_{S}_seed2026101701_{arm}',prompt=prompt,prompt_sha256=sha(R/'configs/prompts/long_0163.txt'),prompt_version=VERSION);s['cases'].append(c);s['case_order'].append(c['run_id'])
s['prompt_sha256']={S:sha(R/'configs/prompts/long_0163.txt')};s['screening']['schema']='r124-native-screen-policy-v1'
for k,rel in [('input_plan_sha256','design/INPUT_PLAN.json'),('prepared_input_manifest_sha256','PREPARED_INPUTS_MANIFEST.json'),('source_selection_sha256','configs/source_selection/SELECTED_SOURCE_MANIFEST.json'),('root_proposal_sha256','design/PROPOSAL.json'),('root_event_review_sha256','design/REFERENCE_EVENT_REVIEW_PLAN.json')]:s[k]=sha(R/rel)
s['evaluation']['rules_sha256']=s['source_selection_sha256'];put(R/'configs/scientific_contract.json',s);put(R/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
p=R/'scripts/r124_contract.py';t=p.read_text().replace("SOURCES=('long_0039',)","SOURCES=('long_0163',)").replace("SOURCE_LENGTHS={'long_0039': (107, 106)}","SOURCE_LENGTHS={'long_0163': (158, 144)}").replace('IVEBench-edit-with-generic-retention-v1',VERSION)
oldcheck="require(case['prompt'] == (root/'design/GENERIC_RETENTION_TEMPLATE.txt').read_text().replace('Add a pair of glasses to the man.', proposal[source]['official_task']['edit_prompt']),'shared generic-retention template or official edit differs')"
newcheck="require(case['prompt'] == (root/'design/FULL_CONTEXT_TEMPLATE.txt').read_text() and all(proposal[source]['official_task'][k] in case['prompt'] for k in ('source_prompt','edit_prompt','target_prompt')),'full Context-IR template or official fields differ')"
assert oldcheck in t;t=t.replace(oldcheck,newcheck);p.write_text(t)
p=R/'scripts/input_contract.py';p.write_text(p.read_text().replace("SOURCES=('long_0039',)","SOURCES=('long_0163',)").replace('LENGTHS=((107, 106),)','LENGTHS=((158, 144),)'))
p=R/'scripts/prepare_inputs.py';p.write_text(re.sub(r'^SELECTION_SHA = .*$',f'SELECTION_SHA = {sha(R/"design/INPUT_PLAN.json")!r}',p.read_text().replace('long_0039','long_0163'),flags=re.M))
p=R/'analysis/postrun/verify_pair.py';t=p.read_text().replace("'prompt_version':'IVEBench-original-edit-prompt-v1'", "'prompt_version':read(root/'configs/scientific_contract.json')['prompt_version']");t=t.replace('One complete source and two preselected six-second excerpts. Exact official edit_prompt per source; task completion and motion assessed separately.','One preselected six-second source excerpt; exact official source/edit/target fields in full Context-IR; task completion and motion assessed separately.');p.write_text(t)
sys.path.insert(0,str(R/'scripts'));import r124_contract as c
for row in s['cases']:put(R/'configs/graphs'/(row['run_id']+'.json'),c.expected_graph(R,row))
for rel,v in num.items():v.update(parent_file=str(P/rel),parent_sha256=sha(P/rel),current_sha256=sha(R/rel),byte_equal=sha(P/rel)==sha(R/rel));assert v['byte_equal']
put(R/'configs/runtime_kernel_hashes.json',num);put(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()})
put(R/'audit/INHERITED_BYTE_BINDINGS.json',{'parent_r122_seal_sha256':sha(P/'deploy_manifest.json'),'source_r120_seal_sha256':sha(I/'deploy_manifest.json'),'six_numerical_files':num,'inputs':prepared['pairs'][0]['files']})
put(R/'audit/ROOT_DESIGN_BINDINGS.json',{str(p.relative_to(R)):sha(p) for p in (R/'design').iterdir() if p.is_file()})
put(R/'audit/SMALL_DIFF.json',{'parent':str(P),'changes':['namespace r124; single source long0163','R120 exact input/clip158 total144 valid','full Context-IR official fields','GPU2 port8594 separate output root','runtime gate prompt_version read from sealed scientific contract'],'unchanged':'six numerical files and sampling/routing policy','gpu_started':False})
print(R)
