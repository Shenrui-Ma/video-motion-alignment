from pathlib import Path
import copy,hashlib,json,shutil
R=Path(__file__).resolve().parents[1];B=R.parent;P=B/'h3-timing-local-edit-protocol-r78-20261018';R69=B/'h3-timing-ivebench-remaining-r69-20261018';R73=B/'h3-timing-ivebench-expanded-r73-20261018'
REMOTE='/data5/researcher/h3_runs/timing_local_edit_repair_r80_20261018';SOURCES=['short_0230','short_0352']
def read(p):return json.loads(p.read_text())
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for folder in ['scripts','extensions','analysis/postrun']:
 shutil.copytree(P/folder,R/folder,ignore=shutil.ignore_patterns('__pycache__'))
for name in ['test_spawn_identity.py','test_cuda_release.py','test_attempt_cleanup.py']:
 (R/'tests').mkdir(exist_ok=True);shutil.copyfile(P/'tests'/name,R/'tests'/name)
for p in R.rglob('*.py'):
 if p==Path(__file__):continue
 p.write_text(p.read_text().replace('r78','r80').replace('R78','R80'))
(R/'scripts/r78_contract.py').rename(R/'scripts/r80_contract.py')
for d in ['design','configs/graphs','configs/parent_graphs','configs/prompts','configs/ancestors','inputs','audit/consumer','tests/fixtures']:(R/d).mkdir(parents=True,exist_ok=True)
for f in ['runtime_kernel_hashes.json','expected_checkpoint_hashes.json','parent_core_hashes.json']:
 shutil.copyfile(R73/'configs'/f,R/'configs'/f)
for f in ['EVALUATION_RULES.txt','EVALUATION_RULES_BINDING.json','OFFICIAL_REF_EN.txt']:
 shutil.copyfile(P/'design'/f,R/'design'/f)
runtime=read(R73/'configs/runtime.json');runtime.update(remote_root=REMOTE,gpu_uuid='GPU-REDACTED',expected_gpu_index=0,port=8547,profile='host9_gpu0_normal_reserve8',profile_scope='Two known development tasks, P1-local-v1 Native repair; original R69 inputs/seed/geometry/sampler on fresh host9. Cross-host historical P0 comparison is descriptive, not prompt-isolated causal evidence.')
save(R/'configs/runtime.json',runtime);save(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
old=read(R69/'configs/scientific_contract.json');cases=[];official=[]
for source in SOURCES:
 c=copy.deepcopy(next(c for c in old['cases'] if c['source_id']==source and c['arm']=='native'));parent=R69/'configs/graphs'/(c['run_id']+'.json')
 shutil.copyfile(parent,R/'configs/parent_graphs'/parent.name)
 for suffix in ['video.mp4','original.mp4','provenance.json','prompt.txt']:shutil.copyfile(R69/'inputs'/(source+'_'+suffix),R/'inputs'/(source+'_'+suffix))
 official.append({'source_id':source,'official_task':c['original_task'],'historical_host':'.41','historical_run':c['run_id'],'parent_graph_sha256':sha(parent)})
 c.update(run_id=f'r80_{source}_seed2026101701_native',parent_graph='configs/parent_graphs/'+parent.name,parent_graph_sha256=sha(parent),prompt_version='P1',prompt_protocol='P1-local-v1',historical_native_run=c['run_id'],reference_cache_id=f'r80_{source}_shared',prompt_file=f'configs/prompts/{source}.txt')
 cases.append(c)
science=read(P/'configs/scientific_contract.json');science.update(schema='r80-preregistered-local-edit-repair-v1',arms=['native'],source_ids=SOURCES,cases=cases,case_order=[c['run_id'] for c in cases],prompt_protocol='P1-local-v1',routed_blocks_per_job={'native':0},purpose='Retry two known failed IVEBench local edits with complete official full-reference prompt structure. Native only before task-fidelity review.',condition_scope='Dense reference video and actual noise retained independently for each source. No comparison across different source conditions.',first_pair='short_0230 Native then short_0352 Native',review_after_pair='Two Native outputs; exact service release then task-fidelity review. Any forced follow-up requires separate explicit registration.',task_fidelity={'assessment_order':['edit success','scene/object retention','action content correspondence','timing only for corresponding retained action']},comparison_scope={'historical_R69':'Host41 P0 vs Host9 P1 is descriptive task repair; not a prompt-only causal comparison.','controlled_prompt_evidence':'R71/R78 same-host prompt controls.','future_method_comparison':'Only new host9 Native/forced with same inputs, prompt, actual AV noise and runtime can measure temporal-guidance increment.'})
science.pop('prompt_protocols',None);science['acceleration_axes']['runtime']=runtime['profile_scope'];science['acceleration_axes']['postprocessing']='Both 90 frames24fps; original valid prefixes86/78 and fixed16/8 spatial crop.';science['acceleration_axes']['cache']='Per-source P1 condition cache and actual AV noise cache retained for any explicit future paired follow-up.'
save(R/'configs/scientific_contract.json',science);save(R/'design/OFFICIAL_TASKS.json',{'sources':official});save(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()});save(R/'configs/queue.json',{'jobs':science['case_order'],'finalize':True})
shutil.copyfile(P/'audit/root_run_pair.py',R/'audit/root_run_pair.py')
p=R/'audit/root_run_pair.py';p.write_text(p.read_text().replace('r78','r80').replace('R78','R80'))
save(R/'audit/ANCESTRY.json',{'administrative_parent':str(P),'numerical_runtime_parent':str(R73),'original_sources_and_graphs':str(R69),'GPU_started':False})
print(R)
