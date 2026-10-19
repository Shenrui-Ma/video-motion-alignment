from pathlib import Path
import json,hashlib,shutil,copy,ast,time
R=Path(__file__).resolve().parents[1];B=R.parent
A=B/'h3-timing-ive-task-repair-r100-20261019'
L=B/'h3-timing-flexiact-remaining-repair-r104-20261019'
P=B/'h3-timing-ive-basketball-boundprompt-r110-20261019'
M=B/'h3-ive-basketball-boundprompt-metrics-r110-20261019'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
origins={}
def cp(base,rel,dest=None,rename=None):
 p=base/rel;q=R/(dest or rel);q.parent.mkdir(parents=True,exist_ok=True)
 data=p.read_bytes()
 if rename:data=data.decode().replace(rename,'r117').replace(rename.upper(),'R117').encode()
 q.write_bytes(data);origins[str(q.relative_to(R))]={'source':str(p),'source_sha256':sha(p),'copied_sha256':sha(q)}
for p in (L/'scripts').glob('*.py'):
 if p.name not in ('r104_contract.py','verify_input_timeline.py'):cp(L,str(p.relative_to(L)),rename='r104')
for p in (A/'extensions').rglob('*.py'):cp(A,str(p.relative_to(A)),rename='r100')
for p in (A/'analysis/postrun').glob('*.py'):cp(A,str(p.relative_to(A)),rename='r100')
for p in (L/'tests').glob('*.py'):
 if p.name not in ('test_repair_contract.py','test_flex_support.py','test_pair_verifier.py'):cp(L,str(p.relative_to(L)),rename='r104')
cp(A,'tests/test_pair_verifier.py',rename='r100')
p=R/'tests/test_pair_verifier.py';t=p.read_text().replace("self.source='short_0392'","self.source='short_0114'").replace("'frames':73","'frames':107").replace("'valid_frame_count':61","'valid_frame_count':105").replace("[0,60]","[0,104]").replace("['valid_frames'],61","['valid_frames'],105");p.write_text(t)
for rel in ['audit/root_run_batch.py','audit/remote_cpu_validate.py','audit/check_cpu_imports.py']:cp(L,rel,rename='r104')
cp(P,'scripts/verify_input_timeline.py',rename='r110')
for rel in ['configs/expected_checkpoint_hashes.json','configs/parent_core_hashes.json','configs/runtime_kernel_hashes.json','configs/R54_evidence/short_0210/captures.json','source_snapshot/r59/sealed_r3_core.py']:
 cp(L,rel)
cp(P,'configs/graphs/r110_short_0114_seed2026101701_native.json','configs/parent_graphs/r110_actual_native.json')
for rel in ['configs/runtime.json','configs/scientific_contract.json','deploy_manifest.json']:cp(P,rel,'source_snapshot/r110/'+rel)
for rel in ['scripts/run_queue.py','scripts/execution_gate.py','audit/root_run_batch.py','configs/runtime.json','deploy_manifest.json']:cp(L,rel,'source_snapshot/r104/'+rel)
for rel in ['scripts/job.py','scripts/run_queue.py']:cp(L,rel,'source_snapshot/http_original/'+Path(rel).name)
for rel in ['audit/PRE_OUTPUT_REVIEW_PLAN.json','audit/full105_review/REVIEW.json','incoming/gate.json']:cp(M,rel,'design/R110_EVIDENCE/'+Path(rel).name)
cp(P,'design/CASE_DEFINITION.json','design/CASE_DEFINITION.json')
for k in ('video','original','provenance'):
 definition=read(P/'design/CASE_DEFINITION.json');cp(P,'inputs/'+definition['source'][k])
prompt=(R/'audit/prompt_geometry_diagnosis/CANDIDATE.txt').read_text().strip()
(R/'configs/prompts').mkdir(parents=True,exist_ok=True);(R/'configs/prompts/short_0114.txt').write_text(prompt)
runtime=read(P/'configs/runtime.json');runtime.update(remote_root='/home/researcher/h3_runs/timing_ive_basketball_framing_repair_r117_20261019',port=8580,profile='host9_gpu3_r117_normal_reserve8',profile_scope='R110 original input/numerical graph; explicit per-frame composition preservation prompt. Native acceptance before fixed6..14. Root scheduling required.')
write(R/'configs/runtime.json',runtime)
write(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
old=read(P/'configs/scientific_contract.json');case=old['cases'][0];cases=[]
for arm in ('native','forced'):
 c=copy.deepcopy(case);c.update(run_id='r117_short_0114_seed2026101701_'+arm,arm=arm,prompt=prompt,prompt_sha256=sha(R/'configs/prompts/short_0114.txt'),prompt_file='configs/prompts/short_0114.txt',prompt_version='frame-preservation-short-v1',parent_graph='configs/parent_graphs/r110_actual_native.json',parent_graph_sha256=sha(R/'configs/parent_graphs/r110_actual_native.json'),evaluation_indices=list(range(105)));cases.append(c)
router=read(A/'configs/scientific_contract.json')['router']
s=copy.deepcopy(old);s.update(schema='r117-basketball-prompt-repair-v1',cases=cases,case_order=[c['run_id'] for c in cases],arms=['native','forced'],prompt_version='frame-preservation-short-v1',router=router,continuous={'retain_service_between_jobs':True,'cache_none':False,'idle_hold_seconds':1800,'max_service_seconds':32400,'job_timeout_seconds':14400,'root_final_close_releases':True,'failure_releases_exact_owned':True},scope_note='R110 only prompt/admin fields change for Native. Task acceptance precedes matched fixed6..14; aligned Native can be retained as a neutral pair.')
s.pop('noise_cache_sha256',None)
write(R/'configs/scientific_contract.json',s);write(R/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
write(R/'configs/input_hashes.json',{p.name:sha(p) for p in sorted((R/'inputs').iterdir())})
write(R/'configs/parent_bindings.json',{'r110_root':str(P),'r110_native_graph_sha256':sha(R/'configs/parent_graphs/r110_actual_native.json'),'r110_producer_seal_sha256':sha(P/'deploy_manifest.json'),'definition_sha256':sha(R/'design/CASE_DEFINITION.json'),'prompt_sha256':sha(R/'configs/prompts/short_0114.txt'),'r110_runtime_sha256':sha(R/'source_snapshot/r110/configs/runtime.json')})
# Preserve original source evidence, while recording only current input files.
write(R/'PREPARED_INPUTS_MANIFEST.json',{'schema':'r117-byte-reused-inputs-v1','source_id':'short_0114','source_producer':str(P),'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in (R/'inputs').iterdir()},'valid_frames':105,'total_frames':107,'fps':24,'spatial_crop_xywh':[16,8,1280,720]})
write(R/'configs/storage_policy.json',{'schema':'r117-storage-budget-v1','startup_required_free_bytes':12*1024**3,'estimated_output_bytes':4*1024**3,'expected_new_runs':2,'expected_total_frames':214,'minimum_free_gib':12,'large_tensors':'remote retained; compact consumer receives MP4/JSON only'})
write(R/'configs/predecessor.json',{'schema':'r117-actual-predecessor-v1','required':[{'key':'R104','remote_root':read(L/'configs/runtime.json')['remote_root'],'producer_seal_sha256':sha(L/'deploy_manifest.json'),'runtime_sha256':sha(L/'configs/runtime.json'),'kind':'screen','required_sources':read(L/'configs/scientific_contract.json')['source_ids']}],'scheduling':'Root schedules after R115/R104 current work; R104 exact release mandatory for the same GPU3.'})
# Copy frozen original visual-input signatures for the new actual gate.
c=read(P/'design/R100_ACTUAL/r100_short_0114_seed2026101701_native_conditioning.json');n=read(P/'design/R100_ACTUAL/r100_short_0114_seed2026101701_native_noise.json')
write(R/'design/EXPECTED_SOURCE_SIGNATURES.json',{'provenance':'R100 actual input, independently reproduced by R110 actual gate','input_video':c['input_video'],'native_vae_calls':c['native_vae_calls'],'qwen_presentation':c['qwen_presentation'],'references':c['pair_snapshot']['actual']['references'],'target_latent_shapes':c['pair_snapshot']['actual']['target_latent_shapes'],'target_latent_dtypes':c['pair_snapshot']['actual']['target_latent_dtypes'],'noise_signature':n['signature'],'actual_noise_streams':n['actual_noise_streams']})
write(R/'audit/INHERITED_BYTE_BINDINGS.json',{'schema':'r117-source-file-origins-v1','files':origins,'note':'Module/run identifiers renamed in lifecycle/integration. Numerical kernels retain exact parent bytes; final changed files listed in deployment seal.'})
for d in ['logs','processes','output','input','analysis/postrun/short_0114']:(R/d).mkdir(parents=True,exist_ok=True)
print('prepared',len(origins),'copied files')
