from pathlib import Path
import json,shutil,hashlib,copy
R=Path(__file__).resolve().parents[1];P=R.parent/'h3-timing-flexiact-expanded-r85-20261018';REMOTE='/data5/researcher/h3_runs/timing_flexiact_p1_control_r90_20261018'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
for folder in ('scripts','extensions','source_snapshot'):
 shutil.copytree(P/folder,R/folder,ignore=shutil.ignore_patterns('__pycache__'))
for folder in ('configs/graphs','configs/parent_graphs','configs/prompts','tests','analysis/postrun','inputs','input','output','temp','user','logs','processes','custom_nodes'): (R/folder).mkdir(parents=True,exist_ok=True)
for f in ('capture_checks.py',):shutil.copy2(P/'analysis/postrun'/f,R/'analysis/postrun'/f)
for f in ('expected_checkpoint_hashes.json','parent_core_hashes.json','runtime_kernel_hashes.json'):shutil.copy2(P/'configs'/f,R/'configs'/f)
for f in ('test_cuda_release.py','test_spawn_identity.py','test_watchdog_timers.py','test_http_wait.py','test_resource_peers.py','test_admission_resample.py','test_attempt_cleanup.py'):shutil.copy2(P/'tests'/f,R/'tests'/f)
for p in list((R/'scripts').glob('*.py'))+list((R/'extensions').rglob('__init__.py'))+list((R/'analysis/postrun').glob('*.py'))+list((R/'tests').glob('*.py')):
 p.write_text(p.read_text().replace('r85_contract','r90_contract').replace("'r85_'","'r90_'").replace('h3-timing-flexiact-expanded-r85-20261018','h3-timing-flexiact-p1-control-r90-20261018'))
(R/'scripts/r85_contract.py').rename(R/'scripts/r90_contract.py')
prompt=P/'audit/root_prompt_control_proposal/one_leg__movie_man_9_P1_candidate.txt';shutil.copy2(prompt,R/'configs/prompts/one_leg__movie_man_9_p1.txt')
shutil.copy2(P/'configs/graphs/r85_one_leg__movie_man_9_seed2026101701_native.json',R/'configs/parent_graphs/r85_actual_native.json')
shutil.copy2(P/'design/official_ref-en.txt',R/'design/official_ref-en.txt')
old=read(P/'configs/scientific_contract.json');case=copy.deepcopy(old['cases'][0]);run='r90_one_leg__movie_man_9_seed2026101701_native';case.update(run_id=run,prompt=prompt.read_text(),prompt_file='configs/prompts/one_leg__movie_man_9_p1.txt',prompt_sha256=sha(prompt),prompt_version='P1',parent_graph='configs/parent_graphs/r85_actual_native.json',parent_graph_sha256=sha(R/'configs/parent_graphs/r85_actual_native.json'))
definition=copy.deepcopy(read(P/'design/PAIR_DEFINITIONS.json')['pairs'][0]);definition.update(prompt=case['prompt'],prompt_file=case['prompt_file'],prompt_sha256=case['prompt_sha256'],prompt_version='P1');definition.pop('p0_ancestry',None)
put(R/'design/CASE_DEFINITION.json',definition)
for name in (case['video'],case['portrait'],case['provenance'],definition['source']['original']):shutil.copy2(P/'inputs'/name,R/'inputs'/name)
put(R/'configs/input_hashes.json',{p.name:sha(p) for p in sorted((R/'inputs').iterdir())})
runtime=read(P/'configs/runtime.json');runtime.update(remote_root=REMOTE,port=8555,profile='host9_gpu3_r90_normal_reserve8',profile_scope='One P1 Native-only prompt-bundle control against actual R85 P0 one_leg. Same host9/core/inputs/rawAVnoise/20Euler; exact R85 release and fresh40GiB admission; own cap2. Actual P1 text count/runtime cost pending.');put(R/'configs/runtime.json',runtime)
owner=read(R/'design/R85_ACTUAL/service.json');put(R/'configs/predecessor.json',dict(root=read(P/'configs/runtime.json')['remote_root'],service_pid=owner['pid'],service_start_ticks=owner['identity']['start_ticks'],gpu_uuid=runtime['gpu_uuid'],last_run=old['case_order'][-1],required='R85 final job history success, original service identity and exact PID/CUDA release required. No automatic takeover.'))
put(R/'configs/admission.json',dict(ready_for_launch=False,scope='own_user_video_jobs',existing_comfy_port=None,permitted_compute_processes=[]))
put(R/'configs/queue.json',dict(jobs=[run],finalize=True))
contract={k:old[k] for k in ['geometry','NFE_per_job','callback_count','online_observer','CFG','sampler','no_Turbo','blocks_per_job','captures','evaluation']}
contract.update(schema='r90-flexiact-p1-native-control-v1',new_method_claim=False,seeds=[2026101701],arms=['native'],cases=[case],case_order=[run],source_ids=[case['source_id']],pair_keys=[case['pair_key']],prompt_version='P1',router=dict(mode='native',alpha=1.,blocks=[0,50],steps=[0,20],physical_frames=[0,146],routed_calls=0),continuous=dict(retain_service_between_jobs=False,cache_none=False,idle_hold_seconds=30,max_service_seconds=18000,job_timeout_seconds=14400,root_final_close_releases=True,failure_releases_exact_owned=True),scope_note='Same-host prompt-bundle P0/P1 control; target image provides identity and scene; video provides full motion. No temporal guidance. Native current source/Qwen encode recomputed; actual clean references and original AV noise must match R85 P0 exactly. Text embedding, packed text length and all x0 may change.',noise_cache_sha256='22880b550e06ce06bb9f23bf203e47e1351863a35487fee66716b9f35c363b01')
put(R/'configs/scientific_contract.json',contract)
put(R/'configs/storage_policy.json',dict(schema='r90-storage-budget-v1',registered_frames_total=158,estimated_output_bytes=2*1024**3,startup_required_free_bytes=6*1024**3,estimate_status='one158frame run approximate2GiB; large preparedRGB and all21x0 remote only',large_tensors='retain remote only'))
ancestry=dict(schema='r90-prompt-parent-bindings-v1',r85_root=read(P/'configs/runtime.json')['remote_root'],r85_run=old['case_order'][0],r85_parent_seal_sha256=sha(P/'deploy_manifest.json'),r85_native_graph_sha256=sha(R/'configs/parent_graphs/r85_actual_native.json'),p1_file_sha256=sha(prompt),p1_text_bytes_policy='Use exact full file contents including trailing newline; no strip.',p1_text_without_final_newline_sha256=hashlib.sha256(prompt.read_text().rstrip('\n').encode()).hexdigest(),p1_origin=str(prompt),original_r72_file='/Users/researcher/DevProjects/h3-timing-flexiact-prompt-pair-r72-20261018/configs/prompts/one_leg__movie_man_9_p1.txt',noise_cache_relative='audit/r85_one_leg__movie_man_9_seed2026101701_noise.pt',noise_cache_sha256=contract['noise_cache_sha256'],actual_record_sha256={p.name:sha(p) for p in (R/'design/R85_ACTUAL').iterdir()},definition_sha256=sha(R/'design/CASE_DEFINITION.json'))
put(R/'configs/parent_bindings.json',ancestry)
g=read(R/'configs/parent_graphs/r85_actual_native.json');g['5']['inputs'].update(prompt=case['prompt'],run_id='r90_one_leg__movie_man_9_shared');g['51']['inputs']['source_run_id']='r90_one_leg__movie_man_9_shared'
for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=REMOTE+'/'+suffix
for node in ('6','50','51','52'):g[node]['inputs']['run_id']=run
g['6']['inputs']['pair_id']='r90_one_leg__movie_man_9_seed2026101701';g['14']['inputs']['filename_prefix']=run
put(R/'configs/graphs'/f'{run}.json',g)
kernels=read(R/'configs/runtime_kernel_hashes.json')
for path,v in kernels.items():v.update(parent_file=str(P/path),parent_sha256=sha(P/path),current_sha256=sha(R/path),byte_equal=sha(P/path)==sha(R/path))
put(R/'configs/runtime_kernel_hashes.json',kernels)
print('prepared',run,'P1',sha(prompt),'6kernels',all(v['byte_equal'] for v in kernels.values()))
