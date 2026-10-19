"""Independent host9 migration of the sealed R83 scientific queue. CPU only."""
from pathlib import Path
import copy,hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'h3-timing-subject-edits-r83-20261018'
ADMIN=ROOT.parent/'h3-timing-flexiact-expanded-r85-20261018'
REMOTE='/data5/researcher/h3_runs/timing_ivebench_subject_host9_r87_20261018'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def cp(a,b):b=Path(b);b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
assert not(ROOT/'deploy_manifest.json').exists()
oldseal=read(OLD/'deploy_manifest.json');adminseal=read(ADMIN/'deploy_manifest.json')
assert all(sha(OLD/p)==v['sha256'] for p,v in oldseal['files'].items())
assert all(sha(ADMIN/p)==v['sha256'] for p,v in adminseal['files'].items())
protected=set(read(OLD/'configs/runtime_kernel_hashes.json'))
for folder in ['scripts','extensions','source_snapshot','tests','configs/parent_graphs','configs/source_selection','configs/prompts','configs/R54_evidence','design','inputs']:
 for p in (OLD/folder).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:cp(p,ROOT/p.relative_to(OLD))
for p in (OLD/'analysis/postrun').glob('*.py'):cp(p,ROOT/'analysis/postrun'/p.name)
for folder in ['scripts','extensions','tests','analysis/postrun']:
 for p in (ROOT/folder).rglob('*.py'):
  if str(p.relative_to(ROOT)) not in protected:p.write_text(p.read_text().replace('r83','r87').replace('R83','R87'))
(ROOT/'scripts/r83_contract.py').rename(ROOT/'scripts/r87_contract.py')
# Reuse reviewed process identity, exact cleanup, timeout handling and bounded watchdog.
admin_files=['service.py','launch_remote.py','service_entry.py','supervise_service.py','process_identity.py','start_controller.py','run_queue.py','job.py','resource_gate.py','lease_watchdog.py']
for name in admin_files:
 p=ROOT/'scripts'/name;p.write_text((ADMIN/'scripts'/name).read_text().replace('r85','r87').replace('R85','R87').replace('h3-timing-flexiact-expanded-r87','h3-timing-ivebench-subject-host9-r87'))
runner=(ADMIN/'audit/root_run_batch.py').read_text().replace('r85','r87').replace('R85','R87').replace('three pairs','seven pairs').replace('three-pair','seven-pair').replace('completed,43200,','completed,57600,')
begin=runner.index('def verify_predecessor():');end=runner.index('\ndef main():',begin);runner=runner[:begin]+runner[end+1:]
runner=runner.replace("        service.write_json(audit/'PREDECESSOR_RELEASE.json',verify_predecessor())\n",'')
(ROOT/'audit/root_run_batch.py').write_text(runner)
runtime=read(ADMIN/'configs/runtime.json');runtime.update(status='CPU_PREPARED_ROOT_LAUNCH_PENDING',remote_root=REMOTE,gpu_uuid='GPU-REDACTED',port=8552,expected_gpu_index=0,profile='host9_gpu0_r87_normal_reserve8',profile_scope='R83 seven source-selected tasks; fresh host9 Native and fixed-route pair per source.40GiB startup capacity gate,normal reserve8; allow exact R85 GPU3 peer and foreign users with free headroom. OwnGPUcap2.')
put(ROOT/'configs/runtime.json',runtime)
put(ROOT/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[],'note':'Root binds actual live R85 GPU3 service before preCUDA GO; at most2 owned cards, foreign users may coexist with sufficient actual memory.'})
for name in ['input_hashes.json','source_selection_hashes.json','storage_policy.json']:cp(OLD/'configs'/name,ROOT/'configs'/name)
for name in ['parent_core_hashes.json','expected_checkpoint_hashes.json']:cp(ADMIN/'configs'/name,ROOT/'configs'/name)
cp(OLD/'PREPARED_INPUTS_MANIFEST.json',ROOT/'PREPARED_INPUTS_MANIFEST.json')
s=read(OLD/'configs/scientific_contract.json');s['schema']='r87-fixed-time-route-seven-paired-v1'
for case in s['cases']:case['run_id']=case['run_id'].replace('r83_','r87_',1)
s['case_order']=[c['run_id'] for c in s['cases']]
s['acceleration_axes']['runtime']='Host9 core/runtime binding; same six numerical kernels as R83. Normal memory,reserve8,disable dynamic VRAM.'
s['acceleration_axes']['cache']='Same-host shared conditions/noise within each of fourteen sequential jobs; each source has independent pair caches.'
s['acceleration_axes']['postprocessing']='Original R83 exact per-source24fps physical mapping; lengths56/107/73/73/73/107/124,valid43/97/61/72/66/105/121; fixed16/8pad crop.'
put(ROOT/'configs/scientific_contract.json',s);put(ROOT/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
put(ROOT/'configs/runtime_kernel_hashes.json',{p:{'parent_file':str(OLD/p),'parent_sha256':sha(OLD/p),'current_sha256':sha(ROOT/p),'byte_equal':sha(OLD/p)==sha(ROOT/p)} for p in protected})
p=ROOT/'scripts/execution_gate.py';p.write_text(p.read_text().replace('30*1024**3','40*1024**3').replace('30720','40960').replace('30GiB','40GiB'))
for name in ['test_capacity_trial.py','test_first_pair.py']:
 p=ROOT/'tests'/name;p.write_text(p.read_text().replace('30*1024**3','40*1024**3').replace('30720','40960').replace('30719','40959').replace('30gib','40gib'))
# Administrative tests are carried over alongside the implementation they exercise.
for name in ['test_watchdog_timers.py','test_http_wait.py','test_resource_peers.py','test_launch_cleanup.py','test_launch_wait.py']:
 src=ADMIN/'tests'/name
 if src.exists():(ROOT/'tests'/name).write_text(src.read_text().replace('r85','r87').replace('R85','R87'))
shutil.copytree(ADMIN/'source_snapshot/http_original',ROOT/'source_snapshot/http_original')
sys.path.insert(0,str(ROOT/'scripts'));import r87_contract as c
for case in s['cases']:put(ROOT/'configs/graphs'/(case['run_id']+'.json'),c.expected_graph(ROOT,case))
# Record exact scientific invariants against the old sealed queue before generating anything.
comparisons=[]
oldcases=read(OLD/'configs/scientific_contract.json')['cases']
for before,after in zip(oldcases,s['cases']):
 expect=copy.deepcopy(before);expect['run_id']=expect['run_id'].replace('r83_','r87_',1);assert expect==after
 oldgraph=read(OLD/'configs/graphs'/(before['run_id']+'.json'));newgraph=read(ROOT/'configs/graphs'/(after['run_id']+'.json'))
 normalized=json.loads(json.dumps(newgraph).replace('r87_','r83_').replace(REMOTE,read(OLD/'configs/runtime.json')['remote_root']))
 # Replace remote root before the run-id prefix normalization since root itself includes r87.
 normalized=json.loads(json.dumps(newgraph).replace(REMOTE,read(OLD/'configs/runtime.json')['remote_root']).replace('r87_','r83_'))
 assert oldgraph==normalized
 comparisons.append({'old_run_id':before['run_id'],'new_run_id':after['run_id'],'old_graph_sha256':sha(OLD/'configs/graphs'/(before['run_id']+'.json')),'new_graph_sha256':sha(ROOT/'configs/graphs'/(after['run_id']+'.json')),'only_run_names_and_audit_paths_changed':True,'prompt_sha256':hashlib.sha256(after['prompt'].encode()).hexdigest(),'same_input_bytes':True})
receipt={'schema':'r87-host-migration-v1','old_root':str(OLD),'old_seal_sha256':sha(OLD/'deploy_manifest.json'),'admin_root':str(ADMIN),'admin_seal_sha256':sha(ADMIN/'deploy_manifest.json'),'scientific_cases':comparisons,'numerical_kernels_byte_equal':all(v['byte_equal'] for v in read(ROOT/'configs/runtime_kernel_hashes.json').values()),'original_inputs_prompts_and_source_selection_byte_equal':True,'same_host_new_native_and_forced':True,'copied_prior_outputs_noise_or_condition_blobs':False,'old_service_modified':False,'GPU_started':False}
put(ROOT/'audit/MIGRATION_RECEIPT.json',receipt)
for folder in ['processes','logs','input','output','temp','user','custom_nodes']:(ROOT/folder).mkdir(exist_ok=True)
verifier=(ADMIN/'audit/verify_passive_deployment.py').read_text();(ROOT/'audit/verify_passive_deployment.py').write_text(verifier)
print('R87 fourteen-job fresh host9 package built')
