"""Separate ordinary prompt control; preserve the actual R100 source and sampler."""
from pathlib import Path
import copy, hashlib, json, shutil
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'h3-timing-flexiact-p1-control-r90-20261018'
PARENT=ROOT.parent/'h3-timing-ive-task-repair-r100-20261019'
REMOTE='/data5/researcher/h3_runs/timing_ive_basketball_shortprompt_r109_20261019'
SOURCE='short_0114'; RUN='r109_short_0114_seed2026101701_native'
PROMPT='Replace the basketball with a neon-lit basketball.'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def cp(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
assert not (ROOT/'deploy_manifest.json').exists()
numerical=read(PARENT/'configs/runtime_kernel_hashes.json')
for rel,row in read(BASE/'deploy_manifest.json')['files'].items():
    assert sha(BASE/rel)==row['sha256'],rel
    if not rel.startswith(('scripts/','extensions/','source_snapshot/','tests/','analysis/postrun/')) and rel!='audit/root_run_native.py':continue
    if rel.startswith('tests/') and rel not in ['tests/test_cuda_release.py','tests/test_spawn_identity.py','tests/test_watchdog_timers.py','tests/test_http_wait.py','tests/test_resource_peers.py','tests/test_admission_resample.py','tests/test_attempt_cleanup.py']:continue
    target=ROOT/rel.replace('r90_contract','r109_contract');cp(BASE/rel,target)
    if target.suffix=='.py' and not rel.startswith('source_snapshot/'):
        target.write_text(target.read_text().replace('r90','r109').replace('R90','R109').replace('one_leg__movie_man_9','short_0114').replace('r85','r100').replace('R85','R100'))
for rel,row in numerical.items():
    cp(PARENT/rel,ROOT/rel)
    row.update(parent_file=str(PARENT/rel),parent_sha256=sha(PARENT/rel),current_sha256=sha(ROOT/rel),byte_equal=True)
put(ROOT/'configs/runtime_kernel_hashes.json',numerical)
for rel in ['configs/expected_checkpoint_hashes.json','configs/parent_core_hashes.json']:
    cp(PARENT/rel,ROOT/rel)
for d in ['configs/graphs','configs/prompts','inputs','input','output','temp','user','logs','processes','custom_nodes','audit/router','audit/x0']:(ROOT/d).mkdir(parents=True,exist_ok=True)
for p in (PARENT/'inputs').glob(SOURCE+'_*'):cp(p,ROOT/'inputs'/p.name)
(ROOT/'configs/prompts/short_0114_plain.txt').write_text(PROMPT)
cp(PARENT/'configs/graphs/r100_short_0114_seed2026101701_native.json',ROOT/'configs/parent_graphs/r100_actual_native.json')
runtime=read(PARENT/'configs/runtime.json');runtime.update(remote_root=REMOTE,port=8572,gpu_uuid='GPU-REDACTED',expected_gpu_index=3,profile='host9_gpu3_r109_normal_reserve8',profile_scope='Ordinary P1 versus exact short prompt. Same R100 source, AV noise, checkpoint, numerical kernels and 20 Euler. GPU0 to GPU3 on same A800 host is recorded.')
put(ROOT/'configs/runtime.json',runtime)
old=read(PARENT/'configs/scientific_contract.json');case=copy.deepcopy(old['cases'][0]);case.update(run_id=RUN,pair_key=SOURCE,prompt=PROMPT,prompt_file='configs/prompts/short_0114_plain.txt',prompt_sha256=hashlib.sha256(PROMPT.encode()).hexdigest(),prompt_version='plain-exact-v1',parent_graph='configs/parent_graphs/r100_actual_native.json',parent_graph_sha256=sha(ROOT/'configs/parent_graphs/r100_actual_native.json'))
definition={'pair_key':SOURCE,'source':{k:case[k] for k in ['video','video_sha256','provenance','provenance_sha256']}}
definition['source'].update(original='short_0114_original.mp4',original_sha256=sha(ROOT/'inputs/short_0114_original.mp4'))
put(ROOT/'design/CASE_DEFINITION.json',definition)
s={k:old[k] for k in ['NFE_per_job','callback_count','online_observer','CFG','sampler','no_Turbo','blocks_per_job','captures','evaluation']}
s.update(schema='r109-short-prompt-native-control-v1',new_method_claim=False,geometry=case['geometry'],seeds=[2026101701],arms=['native'],cases=[case],case_order=[RUN],source_ids=[SOURCE],pair_keys=[SOURCE],prompt_version='plain-exact-v1',router=dict(mode='native',alpha=1.,blocks=[0,50],steps=[6,15],physical_frames=[0,104],routed_calls=0),continuous=dict(retain_service_between_jobs=False,cache_none=False,idle_hold_seconds=30,max_service_seconds=18000,job_timeout_seconds=14400,root_final_close_releases=True,failure_releases_exact_owned=True),noise_cache_sha256='64ccd6a0e8b0a45035faf5b64f4b6a38104e6b32938341b8adebb394223b9387',scope_note='Only prompt text and administrative IDs/paths change from actual R100 Native. Source/prepared RGB/clean reference/noise equal; text embeddings and layout can change. Both ordinary results; R100 forced is not paired to the new prompt.')
put(ROOT/'configs/scientific_contract.json',s)
put(ROOT/'configs/input_hashes.json',{p.name:sha(p) for p in (ROOT/'inputs').iterdir()})
put(ROOT/'configs/queue.json',dict(jobs=[RUN],finalize=True))
put(ROOT/'configs/storage_policy.json',dict(schema='r109-storage-budget-v1',registered_frames_total=107,estimated_output_bytes=2*1024**3,startup_required_free_bytes=6*1024**3,estimate_status='single107frame ordinary run',large_tensors='remote only'))
put(ROOT/'configs/admission.json',dict(ready_for_launch=False,scope='own_user_video_jobs',existing_comfy_port=None,permitted_compute_processes=[]))
put(ROOT/'configs/predecessor.json',dict(root='/data5/researcher/h3_runs/timing_flexiact_character_guidance_r101_20261019',service_pid=53283,service_start_ticks='2640759591',gpu_uuid=runtime['gpu_uuid'],last_run='r101_human2animal_1__game_man_4_seed2026101701_forced'))
bindings=dict(schema='r109-prompt-parent-bindings-v1',r100_root=read(PARENT/'configs/runtime.json')['remote_root'],r100_run=old['case_order'][0],r100_native_graph_sha256=case['parent_graph_sha256'],p1_file_sha256=case['prompt_sha256'],noise_cache_relative='audit/r100_short_0114_seed2026101701_noise.pt',noise_cache_sha256=s['noise_cache_sha256'],actual_record_sha256={p.name:sha(p) for p in (ROOT/'design/R100_ACTUAL').iterdir()},definition_sha256=sha(ROOT/'design/CASE_DEFINITION.json'))
put(ROOT/'configs/parent_bindings.json',bindings)
g=read(ROOT/case['parent_graph'])
for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=REMOTE+'/'+suffix
g['5']['inputs'].update(prompt=PROMPT,run_id='r109_short_0114_shared');g['51']['inputs']['source_run_id']='r109_short_0114_shared'
for node in ['6','50','51','52']:g[node]['inputs']['run_id']=RUN
g['6']['inputs']['pair_id']='r109_short_0114_seed2026101701';g['14']['inputs']['filename_prefix']=RUN
put(ROOT/'configs/graphs'/f'{RUN}.json',g)
print('R109 scaffold prepared; contract adaptation and tests remain')
