from pathlib import Path
import json,hashlib,shutil
R=Path(__file__).resolve().parents[1];B=R.parent
A=B/'h3-timing-subject-edits-r83-20261018';V=B/'h3-timing-flexiact-forced-r84-20261018/audit/watchdog_recovery_v2'
def put(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
p=R/'configs/runtime.json';x=json.loads(p.read_text());x.update(gpu_uuid='GPU-REDACTED',expected_gpu_index=3,profile='host9_gpu3_r85_normal_reserve8',profile_scope='Two official Flex P1 pairs after exact release of R73 GPU3. Fresh Native/forced same service; actual40GiB admission, reserve8; own GPU cap2; foreign coexistence allowed.');put(p,x)
p=R/'tests/test_official_six.py';s=p.read_text().replace("(0,'GPU-REDACTED',8550)","(3,'GPU-REDACTED',8550)");p.write_text(s)
for name in ('test_attempt_cleanup.py','test_admission_resample.py','test_cuda_release.py','test_launch_cleanup.py','test_launch_wait.py'):
 src=A/'tests'/name
 if src.exists():(R/'tests'/name).write_text(src.read_text().replace('r83','r85').replace('R83','R85'))
s=(V/'test_watchdog_v2.py').read_text().replace("Path(__file__).with_name('watchdog_v2.py')","Path(__file__).resolve().parents[1]/'scripts/lease_watchdog.py'")
(R/'tests/test_watchdog_timers.py').write_text(s)
p=R/'audit/ancestry/http_original';p.mkdir(parents=True,exist_ok=True)
for name in ('job.py','run_queue.py'):(p/name).write_text((A/'audit/http_observation_recovery_v2/original'/name).read_text().replace('r83','r85').replace('R83','R85'))
s=(A/'audit/http_observation_recovery_v2/test_http_wait.py').read_text().replace('r83','r85').replace('R83','R85').replace("HERE=Path(__file__).resolve().parent","HERE=Path(__file__).resolve().parents[1]")
s=s.replace("HERE/'candidate/job.py'","HERE/'scripts/job.py'").replace("HERE/('original' if original else 'candidate')/'run_queue.py'","HERE/('audit/ancestry/http_original' if original else 'scripts')/'run_queue.py'")
(R/'tests/test_http_wait.py').write_text(s)
put(R/'configs/predecessor.json',{'root':'/data5/researcher/h3_runs/timing_ivebench_expanded_r73_20261018','service_pid':38065,'service_start_ticks':'2633723201','gpu_uuid':'GPU-REDACTED','last_run':'r73_short_0035_seed2026101701_forced','required':'Actual final history success and exact old PID/CUDA release before R85 service-only launch.'})
p=R/'audit/root_run_batch.py';s=p.read_text();anchor='def main():\n'
f='''def verify_predecessor():
    expected=read(ROOT/'configs/predecessor.json');prior=Path(expected['root'])
    require(prior!=ROOT and prior.parent==ROOT.parent,'predecessor root differs')
    owner=read(prior/'processes/service.json')
    require(owner['pid']==expected['service_pid'] and str(owner['identity']['start_ticks'])==expected['service_start_ticks'] and owner['gpu_uuid']==expected['gpu_uuid']==service.GPU,'predecessor generation/device differs')
    history=read(prior/'logs'/(expected['last_run']+'_history.json'))
    require(history['status'].get('completed') is True and history['status'].get('status_str')=='success','predecessor final job incomplete')
    require(service.current_identity(owner['pid']) is None,'predecessor service still exists')
    require(not any(r['pid']==owner['pid'] for r in service.compute_processes()),'predecessor CUDA allocation remains')
    cleanup=read(prior/'processes/cleanup.json')
    require(cleanup['pid']==owner['pid'] and cleanup.get('process_absent') is True and cleanup.get('own_compute_absent') is True,'predecessor exact cleanup receipt pending')
    return {'owner':owner,'cleanup':cleanup,'last_history_sha256':sha(prior/'logs'/(expected['last_run']+'_history.json'))}

'''
assert anchor in s;s=s.replace(anchor,f+anchor)
s=s.replace("peers=live_peers(args.peer_root)\n        admission=", "service.write_json(audit/'PREDECESSOR_RELEASE.json',verify_predecessor())\n        peers=live_peers(args.peer_root)\n        admission=",1)
p.write_text(s)
p=R/'scripts/execution_gate.py';s=p.read_text().replace("'runtime.json','scientific_contract.json'","'runtime.json','predecessor.json','scientific_contract.json'");p.write_text(s)
# Passive verifier uses existing environment; gathers a complete numerical-module/core binding.
p=R/'audit/verify_passive_deployment.py';s=(B/'h3-timing-flexiact-official-six-r74-20261018/audit/verify_passive_deployment.py').read_text().replace('hashlib,json,os,subprocess,sys,shutil','hashlib,json,os,subprocess,sys,shutil,re')
s=s.replace("PYTHONPATH=runtime['dependencies'])","PYTHONPATH=runtime['dependencies'],OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')")
s=s.replace("'CPU_tests':46", "'CPU_tests':int(re.search(r'Ran (\\d+) tests',(root/'audit/CPU_REMOTE_TESTS.txt').read_text()).group(1))")
p.write_text(s)
print('R85 GPU3/reviewed administration prepared')
