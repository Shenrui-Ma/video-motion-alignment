"""Derive R120 official-edit-prompt comparison from frozen R114; CPU only."""
import copy,hashlib,json,pathlib,re,shutil,sys,time
R=pathlib.Path(__file__).resolve().parents[1];P=R.parent/'h3-timing-ive-three-source-r114-20261019'
S=('long_0059','long_0163','long_0081');L={'long_0059':(158,144),'long_0163':(158,144),'long_0081':(124,120)}
REMOTE='/home/researcher/h3_runs/timing_ive_official_prompt_r120_20261019';PORT=8590
read=lambda p:json.loads(pathlib.Path(p).read_text());sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def cp(p,q):q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
assert not (R/'deploy_manifest.json').exists();seal=read(P/'deploy_manifest.json');numeric=read(P/'configs/runtime_kernel_hashes.json')
for rel,row in seal['files'].items():
 assert sha(P/rel)==row['sha256'],rel
 dest=rel.replace('r114_contract.py','r120_contract.py').replace('test_r114_derivation.py','test_r120_derivation.py');cp(P/rel,R/dest)
 if rel.endswith('.py') and not rel.startswith('source_snapshot/') and rel not in numeric:
  p=R/dest;p.write_text(p.read_text().replace('r114','r120').replace('R114','R120'))
for rel in ['deploy_manifest.json','design/PROPOSAL.json','design/INPUT_PLAN.json','design/REFERENCE_EVENT_REVIEW_PLAN.json','PREPARED_INPUTS_MANIFEST.json','configs/scientific_contract.json','configs/runtime.json']:
 cp(P/rel,R/'source_snapshot/r114'/rel)
for name,digest in read(P/'configs/input_hashes.json').items():
 assert sha(P/'inputs'/name)==digest,name
 cp(P/'inputs'/name,R/'inputs'/name)
for folder in ['input','output','temp','user','custom_nodes','processes','logs','configs/graphs','audit/router','audit/x0']:(R/folder).mkdir(parents=True,exist_ok=True)
# Keep source bytes/clip selection and preregistered source events unchanged; reorder only.
for rel,key in [('design/PROPOSAL.json','cases'),('design/INPUT_PLAN.json','pairs'),('design/REFERENCE_EVENT_REVIEW_PLAN.json','items'),('PREPARED_INPUTS_MANIFEST.json','pairs'),('configs/source_selection/SELECTED_3_MANIFEST.json','pairs')]:
 d=read(P/rel);by={x.get('source_id',x.get('pair_id')):x for x in d[key]};d[key]=[by[s] for s in S];put(R/rel,d)
proposal=read(R/'design/PROPOSAL.json');official={x['source_id']:x['official_task']['edit_prompt'] for x in proposal['cases']}
for row in proposal['cases']:
 s=row['source_id'];prompt=official[s]
 (R/'configs/prompts'/(s+'.txt')).write_text(prompt)
 old=R/'design'/(s+'_P1_candidate.txt');old.unlink()
 new=R/'design'/(s+'_official_prompt.txt');new.write_text(prompt)
 row.update(prompt_file=str(new),prompt_sha256=sha(new),prompt_protocol='IVEBench exact edit_prompt, no additions')
proposal.update(created_unix=time.time(),state='CPU preparation; no output observed for R120',method='inherit R114 fixed routing; paired Native/guide use identical official edit_prompt',next_execution_strategy='0059 and0163 new-source task review first;0081 last as prompt control against older detailed R114')
put(R/'design/PROPOSAL.json',proposal)
put(R/'design/PROMPT_PROTOCOL.json',{'schema':'r120-exact-official-edit-prompt-v1','user_update':'Use the benchmark original prompt without six sections or added motion descriptions.','source_order':list(S),'prompts':official,'pair_rule':'native and forced have identical official prompt, seed, input, geometry and schedules','cross_prompt_comparison':'R114long0081 to R120long0081 is prompt control; it is not a guidance comparison','unchanged':'source media, source-only clip/event selection, numerical modules, sampler and fixed guidance'})
runtime=read(P/'configs/runtime.json');runtime.update(status='CPU_PREPARED_ROOT_REVIEW_PENDING',remote_root=REMOTE,port=PORT,profile='host9_gpu3_r120_normal_reserve8',profile_scope='Exact IVEBench edit_prompt. New0059/0163 first;0081 prompt-control source last. Root scheduling after R114 first-group exactrelease and any allocated metric jobs.')
put(R/'configs/runtime.json',runtime);put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
v=read(R/'PREPARED_INPUTS_MANIFEST.json');v['input_plan_sha256']=sha(R/'design/INPUT_PLAN.json');put(R/'PREPARED_INPUTS_MANIFEST.json',v)
v=read(R/'configs/source_selection/SELECTED_3_MANIFEST.json');v['root_proposal_sha256']=sha(R/'design/PROPOSAL.json');v['root_review_events_sha256']=sha(R/'design/REFERENCE_EVENT_REVIEW_PLAN.json');put(R/'configs/source_selection/SELECTED_3_MANIFEST.json',v)
put(R/'configs/source_selection_hashes.json',{p.name:sha(p) for p in (R/'configs/source_selection').iterdir()})
s=read(P/'configs/scientific_contract.json');old=s['cases'];s.update(schema='r120-official-edit-prompt-three-source-v1',source_ids=list(S),cases=[],case_order=[],prompt_version='IVEBench-original-edit-prompt-v1',purpose='Evaluate same fixed temporal routing using exact official edit_prompt.0059/0163 first;0081 last permits prompt comparison with R114.')
for src in S:
 for arm in ('native','forced'):
  c=copy.deepcopy(next(x for x in old if x['source_id']==src and x['arm']==arm));c.update(run_id=c['run_id'].replace('r114','r120'),prompt=official[src],prompt_sha256=sha(R/'configs/prompts'/(src+'.txt')),prompt_version=s['prompt_version']);s['cases'].append(c);s['case_order'].append(c['run_id'])
s['screening']['schema']='r120-native-screen-policy-v1';s['evaluation']['rules_sha256']=sha(R/'configs/source_selection/SELECTED_3_MANIFEST.json');s['prompt_sha256']={src:sha(R/'configs/prompts'/(src+'.txt')) for src in S}
s['prompt_protocol']='Exact official edit_prompt UTF-8 text; no added subject definitions, preservation prose or motion description.'
for k,rel in [('input_plan_sha256','design/INPUT_PLAN.json'),('prepared_input_manifest_sha256','PREPARED_INPUTS_MANIFEST.json'),('source_selection_sha256','configs/source_selection/SELECTED_3_MANIFEST.json'),('root_proposal_sha256','design/PROPOSAL.json'),('root_event_review_sha256','design/REFERENCE_EVENT_REVIEW_PLAN.json')]:s[k]=sha(R/rel)
put(R/'configs/scientific_contract.json',s);put(R/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
# Active namespace/registry changes; frozen numerical files remain byte exact.
p=R/'scripts/r120_contract.py';t=p.read_text();t=re.sub(r'^SOURCES=.*$',f'SOURCES={S!r}',t,flags=re.M);t=re.sub(r'^SOURCE_LENGTHS=.*$',f'SOURCE_LENGTHS={L!r}',t,flags=re.M);t=t.replace('P1-local-v1','IVEBench-original-edit-prompt-v1').replace('_P1_candidate.txt','_official_prompt.txt').replace("proposal[source]['official_task']['edit_prompt'] in case['prompt']","proposal[source]['official_task']['edit_prompt'] == case['prompt']").replace('original edit text absent','prompt must equal official edit_prompt exactly').replace('root P1 candidate bytes changed','official prompt bytes changed');p.write_text(t)
p=R/'scripts/input_contract.py';t=p.read_text();t=re.sub(r'^SOURCES=.*$',f'SOURCES={S!r}',t,flags=re.M);t=re.sub(r'^LENGTHS=.*$',f'LENGTHS={tuple(L[k] for k in S)!r}',t,flags=re.M);p.write_text(t)
p=R/'scripts/prepare_inputs.py';t=p.read_text();t=re.sub(r'^SELECTION_SHA = .*$',f'SELECTION_SHA = {sha(R/"design/INPUT_PLAN.json")!r}',t,flags=re.M);p.write_text(t)
# Rebuild fresh run graphs; only namespaces and prompt differ per same-source old/new pair.
for p in (R/'configs/graphs').glob('*.json'):p.unlink()
sys.path.insert(0,str(R/'scripts'));import r120_contract as contract
for row in s['cases']:put(R/'configs/graphs'/(row['run_id']+'.json'),contract.expected_graph(R,row))
for rel,row in numeric.items():row.update(parent_file=str(P/rel),parent_sha256=sha(P/rel),current_sha256=sha(R/rel),byte_equal=sha(P/rel)==sha(R/rel));assert row['byte_equal']
put(R/'configs/runtime_kernel_hashes.json',numeric)
# Preserve old source/input bytes. inputs/*_prompt.txt is original official metadata, not actual model conditioning.
put(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()})
put(R/'audit/INHERITED_BYTE_BINDINGS.json',{'parent_r114_seal_sha256':sha(P/'deploy_manifest.json'),'six_numerical_files':numeric,'inputs':{p.name:{'parent_sha256':sha(P/'inputs'/p.name),'sha256':sha(p),'equal':sha(P/'inputs'/p.name)==sha(p)} for p in (R/'inputs').iterdir()},'prompts':{src:sha(R/'configs/prompts'/(src+'.txt')) for src in S},'prompt_delta':'replaced detailed R114 prompt with exact original_task.edit_prompt'})
(R/'design/README.txt').write_text('R120：直接使用IVEBench原edit_prompt。顺序long0059、long0163、long0081。前两条为既定6秒素材片段，末条约5秒完整片。普通/引导同提示词，媒体、几何、seed和6–14步固定引导沿R114。R114long0081与本轮对应普通版仅构成prompt对照。CPU准备，等待root审核及R114释放。\n')
# Update only obsolete prose in the report helper; no score/metric function changes.
p=R/'analysis/postrun/verify_pair.py';t=p.read_text().replace('Five source-selected official IVE tasks; P1 preserves local edit intent; style transfer remains an extension.','Three official edit_prompt tasks; source/task scope comes from the exact registry.');p.write_text(t)
put(R/'audit/ROOT_DESIGN_BINDINGS.json',{str(p.relative_to(R)):sha(p) for p in (R/'design').iterdir() if p.is_file()})
put(R/'audit/PREPARE_RECEIPT.json',{'parent':str(P),'parent_seal_sha256':sha(P/'deploy_manifest.json'),'source_ids':list(S),'jobs':s['case_order'],'official_prompt_only':True,'local_only':True,'remote_deployed':False,'gpu_started':False,'port':PORT})
print('PREPARED',R)
