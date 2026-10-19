"""Administrative .41 alternative of sealed R116. Root launches exactly one host."""
from pathlib import Path
import copy,hashlib,json,shutil,sys
R=Path(__file__).resolve().parents[1];P=R.parent/'h3-timing-flexiact-h2a1-game4-repair-r116-20261019';H=R.parent/'h3-timing-flexiact-p1-repair-r103-20261019'
REMOTE='/data4/researcher/h3_runs/timing_flexiact_h2a1_game4_repair_r116_host41_20261019'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def cp(p,q):q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
assert not(R/'deploy_manifest.json').exists()
for rel,row in read(P/'deploy_manifest.json')['files'].items():assert sha(P/rel)==row['sha256'];cp(P/rel,R/rel)
for p in (P/'inputs').iterdir():cp(p,R/'inputs'/p.name)
cp(P/'configs/queue.json',R/'configs/queue.json')
for rel in ('audit/check_cpu_imports.py','audit/remote_cpu_validate.py'):cp(P/rel,R/rel)
for rel in ('scripts/cgroup_memory.py','scripts/working_set_capacity.py','tests/test_cgroup_memory.py','tests/test_working_set_capacity.py'):
 cp(H/rel,R/rel);p=R/rel;p.write_text(p.read_text().replace('r103','r116').replace('R103','R116'))
cp(H/'scripts/service.py',R/'scripts/service.py');p=R/'scripts/service.py';p.write_text(p.read_text().replace('r103','r116').replace('R103','R116'))
# Restore only the proven administrative .41 guards/telemetry in the inherited controller and root wrapper.
p=R/'scripts/run_queue.py';t=p.read_text();needle="    with (service.RUN/'logs/resources.jsonl').open('a') as handle:handle.write(json.dumps(sample)+'\\n')";assert needle in t;t=t.replace(needle,"    import cgroup_memory\n    sample['cgroup_memory']=cgroup_memory.observe(service.RUN)\n"+needle);p.write_text(t)
p=R/'audit/root_run_batch.py';t=p.read_text();needle='        peers=live_peers(args.peer_root)\n';assert t.count(needle)==1;t=t.replace(needle,needle+"        require(not peers,'R116 host41 permits one own H3 and requires official MF to finish before loading')\n");needle="        service.write_json(ROOT/'processes/cuda_gate_go.json',ready)";assert needle in t;t=t.replace(needle,"        import cgroup_memory\n        service.write_json(audit/'CGROUP_PRE_GO.json',cgroup_memory.check(ROOT))\n"+needle);needle='    finally:\n';assert t.count(needle)==1;t=t.replace(needle,needle+"        try:\n            import cgroup_memory\n            best_effort_receipt(audit/'CGROUP_EXIT_OBSERVATION.json',cgroup_memory.observe(ROOT))\n        except BaseException as error:\n            best_effort_receipt(audit/'CGROUP_OBSERVATION_ERROR.json',{'error':repr(error)})\n");p.write_text(t)
runtime=read(H/'configs/runtime.json');runtime.update(remote_root=REMOTE,port=8576,profile='host41_gpu2_r116_normal_reserve8',profile_scope='Administrative host41 alternative of sealed R116; root launches either host9 or host41 exactly once. Same prompt, source, image, seed, model/core SHAs, six numerical modules and scientific parameters. One own H3 after MF release.');put(R/'configs/runtime.json',runtime)
policy=read(H/'configs/cgroup_policy.json');policy['schema']='r116-host41-reviewed-working-set-admission-v1';put(R/'configs/cgroup_policy.json',policy)
put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
# Cross-host completion evidence is immutable evidence; fresh .41 GPU/CPU admission remains independent.
release=R.parent/'h3-flexiact-remaining-repair-metrics-r104-20261019/audit/actual_full_release'
for n in ('STARTED.json','ROOT_EXIT_RECEIPT.json','COMPLETE.json','VERIFIED.json'):cp(release/n,R/'source_snapshot/r104_actual_release'/n)
put(R/'configs/predecessor.json',{'schema':'r116-host41-cross-host-completion-v1','required':[],'source_completion_evidence':{n:sha(R/'source_snapshot/r104_actual_release'/n) for n in ('STARTED.json','ROOT_EXIT_RECEIPT.json','COMPLETE.json','VERIFIED.json')},'source_completion_note':'R104 host9 full screen and exact release verified locally. Fresh host41 GPU/CPU gates and root dispatch apply independently.'})
put(R/'design/HOST_ALTERNATIVE.json',{'status':'CPU_PREPARED_ROOT_DISPATCH_PENDING','mutually_exclusive_with':str(P),'mutually_exclusive_remote':read(P/'configs/runtime.json')['remote_root'],'root_dispatch_rule':'Launch exactly one R116 host. No comparison inference solely for environment testing.','parent_host9_seal_sha256':sha(P/'deploy_manifest.json'),'host41_runtime_parent':str(H),'host41_runtime_parent_seal_sha256':sha(H/'deploy_manifest.json'),'science':'Prompt/source/image/seed/sampler/router/geometry and six numerical modules identical to parent R116; output accepted and paired only within this actual service.','resource_gate':policy})
p=R/'scripts/execution_gate.py';t=p.read_text();needle="'runtime.json','scientific_contract.json'";assert needle in t;t=t.replace(needle,"'queue.json','cgroup_policy.json','runtime.json','scientific_contract.json'");p.write_text(t)
for folder in ('input','output','temp','user','custom_nodes','processes','logs','audit/router','audit/x0'):(R/folder).mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(R/'scripts'));import r116_contract as c
for row in read(R/'configs/scientific_contract.json')['cases']:put(R/'configs/graphs'/(row['run_id']+'.json'),c.expected_graph(R,row))
numeric=read(R/'configs/runtime_kernel_hashes.json')
for rel,row in numeric.items():assert sha(R/rel)==sha(P/rel)==sha(H/rel)==row['current_sha256'],rel
assert read(R/'configs/parent_core_hashes.json')==read(H/'configs/parent_core_hashes.json')
assert read(R/'configs/expected_checkpoint_hashes.json')==read(H/'configs/expected_checkpoint_hashes.json')
assert read(R/'configs/scientific_contract.json')==read(P/'configs/scientific_contract.json')
put(R/'audit/HOST41_PREPARE_RECEIPT.json',{'parent_host9_seal_sha256':sha(P/'deploy_manifest.json'),'scientific_contract_byte_equal':sha(R/'configs/scientific_contract.json')==sha(P/'configs/scientific_contract.json'),'numerical_modules_byte_equal':True,'core_and_checkpoint_hashes_equal':True,'gpu_started':False,'only_administrative_host_change':True})
print('Prepared',R)
