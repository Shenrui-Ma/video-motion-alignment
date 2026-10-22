from pathlib import Path
import copy,hashlib,json,os,shutil,sys,time
R=Path(__file__).resolve().parents[1];P=R.parent/'h3-timing-ive-full-context-r124-20261020';C=R.parent/'h3-ive-full-context-metrics-r124-20261020';S='long_0163';VER='IVEBench-subject-bound-edit-no-caption-narrative-v1'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def cp(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
assert not(R/'deploy_manifest.json').exists();seal=read(P/'deploy_manifest.json');num=read(P/'configs/runtime_kernel_hashes.json')
for rel,v in seal['files'].items():
 assert sha(P/rel)==v['sha256'],rel
 dst=rel.replace('r124_contract.py','r130_contract.py');cp(P/rel,R/dst)
 if rel.endswith('.py') and not rel.startswith('source_snapshot/') and rel not in num:
  p=R/dst;p.write_text(p.read_text().replace('r124','r130').replace('R124','R130'))
for f in ['input','output','temp','user','custom_nodes','processes','logs','audit/router','audit/x0']:(R/f).mkdir(parents=True,exist_ok=True)
for f in (P/'inputs').iterdir():
 if f.is_file():
  dst=R/'inputs'/f.name;dst.parent.mkdir(exist_ok=True)
  if f.suffix=='.mp4':os.link(f,dst)
  else:cp(f,dst)
actual=read(C/'incoming/long_0163/native_graph.json');hist=read(C/'incoming/long_0163/native_history.json');old=actual['5']['inputs']['prompt'];assert hist['prompt'][2]['5']['inputs']['prompt']==old
prompt=(C/'audit/caption_narrative_control_plan/CANDIDATE_PROMPT.txt').read_text();official=read(P/'configs/scientific_contract.json')['cases'][0]['original_task'];expect=old.replace('Source caption: '+official['source_prompt']+'\n','').replace('[Shot 1] '+official['target_prompt']+'\n','[Shot 1] ');assert prompt==expect
for rel in ['configs/prompts/long_0163.txt','design/long_0163_actual_prompt.txt','design/FULL_CONTEXT_TEMPLATE.txt']:(R/rel).write_text(prompt)
pr=read(P/'design/PROPOSAL.json');pr.update(schema='r130-caption-narrative-control-v1',created_unix=time.time(),state='CPU_ONLY_AFTER_R126_EXACT_RELEASE',method='Native prompt ablation; fixed guide remains conditional after actual review',prompt_protocol=VER)
for row in pr['cases']:row.update(prompt_file=str(R/'configs/prompts/long_0163.txt'),prompt_sha256=sha(R/'configs/prompts/long_0163.txt'))
pr['hypothesis']='Official standing/handing caption may conflict with current seated reference excerpt; removing the two caption narratives may preserve the actual reference better. Single prompt difference experiment.'
put(R/'design/PROPOSAL.json',pr);put(R/'design/PROMPT_PROTOCOL.json',{'version':VER,'original_task':official,'actual_R124_graph':str(C/'incoming/long_0163/native_graph.json'),'actual_R124_graph_sha256':sha(C/'incoming/long_0163/native_graph.json'),'actual_R124_history_sha256':sha(C/'incoming/long_0163/native_history.json'),'changes':['delete literal source caption','delete literal target caption'],'edit_prompt_preserved_verbatim':True,'no_added_action_description':True})
sel=read(P/'configs/source_selection/SELECTED_SOURCE_MANIFEST.json');sel['root_proposal_sha256']=sha(R/'design/PROPOSAL.json');put(R/'configs/source_selection/SELECTED_SOURCE_MANIFEST.json',sel);put(R/'configs/source_selection_hashes.json',{f.name:sha(f) for f in (R/'configs/source_selection').iterdir() if f.is_file()})
rt=read(P/'configs/runtime.json');rt.update(remote_root='/home/researcher/h3_runs/timing_ive_caption_ablation_r130_20261020',gpu_uuid='GPU-REDACTED',port=8606,expected_gpu_index=3,profile='host9_gpu3_r130_normal_reserve8',profile_scope='After R126 actual release; register current GPU2 peer',status='CPU_PREPARED');put(R/'configs/runtime.json',rt);put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
s=read(P/'configs/scientific_contract.json');s.update(schema='r130-caption-narrative-control-v1',purpose='R124 same-source same-noise Native prompt ablation deleting source/target narratives',prompt_version=VER,prompt_protocol='Original edit with H3 subject binding and generic retention; source/target caption narratives omitted',prompt_sha256={S:sha(R/'configs/prompts/long_0163.txt')});s['case_order']=[v.replace('r124','r130') for v in s['case_order']];s['screening']['schema']='r130-native-review-policy-v1'
for case in s['cases']:case.update(run_id=case['run_id'].replace('r124','r130'),prompt=prompt,prompt_sha256=s['prompt_sha256'][S],prompt_version=VER)
s['source_selection_sha256']=sha(R/'configs/source_selection/SELECTED_SOURCE_MANIFEST.json');s['root_proposal_sha256']=sha(R/'design/PROPOSAL.json');s['evaluation']['rules_sha256']=s['source_selection_sha256'];s['evaluation']['official']='Original long0163 task and same2.08–8.08s source; prompt control omits source/target caption narrative';s['acceleration_axes']['postprocessing']='144 valid frames at24fps; frames144–157 repeated padding excluded';put(R/'configs/scientific_contract.json',s);put(R/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
p=R/'scripts/r130_contract.py';t=p.read_text().replace('IVEBench-official-fields-full-Context-IR-v1',VER);oldcheck="all(proposal[source]['official_task'][k] in case['prompt'] for k in ('source_prompt','edit_prompt','target_prompt'))";newcheck="proposal[source]['official_task']['edit_prompt'] in case['prompt'] and all(proposal[source]['official_task'][k] not in case['prompt'] for k in ('source_prompt','target_prompt'))";assert oldcheck in t;t=t.replace(oldcheck,newcheck).replace('full Context-IR template or official fields differ','subject-bound edit-only template differs');p.write_text(t)
for q in [R/'analysis/postrun/verify_native.py',R/'analysis/postrun/verify_pair.py']:
 if q.exists():q.write_text(q.read_text().replace('IVEBench-original-edit-prompt-v1',VER).replace('IVEBench-official-fields-full-Context-IR-v1',VER))
sys.path.insert(0,str(R/'scripts'));import r130_contract as contract
for case in s['cases']:put(R/'configs/graphs'/(case['run_id']+'.json'),contract.expected_graph(R,case))
for f in (R/'configs/graphs').glob('r124*'):f.unlink()
for rel,v in num.items():v.update(parent_file=str(P/rel),parent_sha256=sha(P/rel),current_sha256=sha(R/rel),byte_equal=sha(P/rel)==sha(R/rel));assert v['byte_equal']
put(R/'configs/runtime_kernel_hashes.json',num);put(R/'configs/input_hashes.json',{f.name:sha(f) for f in (R/'inputs').iterdir() if f.is_file()})
put(R/'audit/INHERITED_BYTE_BINDINGS.json',{'parent_r124_seal_sha256':sha(P/'deploy_manifest.json'),'six_numerical_files':num,'inputs':'same R124 files; MP4 hardlinked locally'})
noise={'source_remote':'/home/researcher/h3_runs/timing_ive_full_context_r124_20261020/audit/r124_long_0163_seed2026101701_noise.pt','target_remote':rt['remote_root']+'/audit/r130_long_0163_seed2026101701_noise.pt','actual_noise_receipt':read(C/'audit/caption_narrative_control_plan/REMOTE_ACTUAL_AUDIT.json')['R124_actual_noise'],'rule':'Before launch copy actual AV noise and assert tensor and file hashes; prompt encoding naturally differs.'};put(R/'design/NOISE_REUSE_PLAN.json',noise)
cp(C/'audit/caption_narrative_control_plan/CANDIDATE_PROMPT.txt',R/'audit/APPROVED_PROMPT_DRAFT.txt');cp(C/'audit/caption_narrative_control_plan/PROPOSAL.json',R/'audit/ORIGINAL_PROPOSAL.json')
event=R.parent/'h3-ive-short-source-selection-20261020/source_events_long0163/SOURCE_EVENTS_BEFORE_OUTPUT.json';cp(event,R/'audit/SOURCE_EVENTS_BEFORE_OUTPUT.json')
put(R/'audit/ROOT_DESIGN_BINDINGS.json',{str(f.relative_to(R)):sha(f) for f in (R/'design').iterdir() if f.is_file()})
put(R/'audit/SMALL_DIFF.json',{'parent':str(P),'actual_prompt_parent_graph':str(C/'incoming/long_0163/native_graph.json'),'source':S,'changes':['R130 isolated output/runtime namespace GPU3/port8606','delete exactly2caption narratives','correct copied144/158 documentation'],'same_numerical_files':True,'same_source_geometry':True,'planned_actual_noise_reuse':True,'GPU_started':False})
print(R)
