from pathlib import Path
import shutil
R=Path(__file__).resolve().parents[1];A=Path('/Users/researcher/DevProjects/h3-timing-local-edit-repair-r80-20261018');H=Path('/Users/researcher/DevProjects/h3-timing-local-edit-protocol-r78-20261018')
p=R/'scripts/job.py';s=p.read_text();old="""    other_processes = [row for row in service.compute_processes() if row['pid'] != owner['pid']]
    existing_queue = service.queue_at(admission.get('existing_comfy_port', 8189))
    service.check_admission(admission, other_processes, existing_queue)
""";new="""    existing_queue = service.queue_at(admission.get('existing_comfy_port', 8189))
    service.wait_admission_snapshot(admission, existing_queue, exclude_pid=owner['pid'])
""";assert old in s;s=s.replace(old,new)
func='''def require_native_generation(binding, owner):
    if binding['arm'] != 'forced':return
    run = 'r83_' + binding['source_id'] + '_seed2026101701_native'
    native = json.loads((RUN/'logs'/(run+'_job.json')).read_text())
    history = json.loads((RUN/'logs'/(run+'_history.json')).read_text())
    if (native.get('status') != 'success' or native['service_pid'] != owner['pid'] or
        native['service_identity'] != owner['identity'] or
        history['status'].get('completed') is not True or history['status'].get('status_str') != 'success'):
        raise RuntimeError('paired Native success or service generation differs')


'''
s=s.replace('def submit(name, expected_owner=None):',func+'def submit(name, expected_owner=None):')
s=s.replace('        owner = active_service()\n        if expected_owner',"        owner = active_service()\n        if not admitted_job(name,RUN):raise RuntimeError('first pair review pending inside submission lock')\n        require_native_generation(binding,owner)\n        require_generation(active_service(),owner)\n        if expected_owner")
s=s.replace("            require_generation(active_service(),owner)\n            response = request('/prompt'", "            require_generation(active_service(),owner)\n            if not admitted_job(name,RUN):raise RuntimeError('approval withdrawn before POST')\n            require_native_generation(binding,owner)\n            require_generation(active_service(),owner)\n            response = request('/prompt'")
p.write_text(s)
for src in [A/'tests/test_admission_resample.py',H/'tests/test_cuda_release.py']:
 shutil.copy2(src,R/'tests'/src.name)
# The root launcher uses the already-tested attempt-token and exact-owned cleanup boundary.
s=(A/'audit/root_run_pair.py').read_text().replace('r80_contract','r83_contract').replace('approve-first-native','approve-first-pair').replace("'30720'","'40960'")
s=s.replace("state.get('completed')==order[:1]","state.get('completed')==order[:2]").replace("first Native completion deadline","first pair completion deadline").replace("first_native_verify.log","first_pair_verify.log").replace('verify_native.py','verify_pair.py').replace('NATIVE_RUNTIME_GATE.json','PAIR_RUNTIME_GATE.json').replace('actual first Native gate','actual first pair gate')
s=s.replace("        subprocess.run([service.RUNTIME['python'],'audit/consumer/collect.py','--source',source],cwd=ROOT,env=cpuenv,check=True,timeout=120)\n",'')
s=s.replace("audit/'FIRST_NATIVE_REVIEW_HOLD.json'","audit/'FIRST_PAIR_REVIEW_HOLD.json'").replace("'run':order[0]","'runs':order[:2]").replace("'native_gate_sha256'","'pair_gate_sha256'").replace("'second_submission_requires':'root approve-second-native --task-fidelity-reviewed'","'remaining_submission_requires':'root approve-rest --root-admitted'")
s=s.replace("wait_until(completed,36000,'two-run completion deadline',20)","wait_until(completed,57600,'seven-pair completion deadline',20)")
s=s.replace("actual Native gate failed","actual pair gate failed").replace("        subprocess.run([service.RUNTIME['python'],'audit/consumer/collect.py'],cwd=ROOT,env=cpuenv,check=True,timeout=120)\n",'')
s=s.replace('two runs','seven pairs').replace('CPU gate','CPU pair gate')
(R/'audit/root_run_batch.py').write_text(s)
s=(H/'tests/test_attempt_cleanup.py').read_text().replace('root_run_pair.py','root_run_batch.py').replace('r78','r83');(R/'tests/test_attempt_cleanup.py').write_text(s)
# Seal the administrative entry too, alongside the scientific/runtime files.
p=R/'scripts/execution_gate.py';s=p.read_text().replace("paths.append(root/'PREPARED_INPUTS_MANIFEST.json')","paths.append(root/'PREPARED_INPUTS_MANIFEST.json')\n paths.append(root/'audit/root_run_batch.py')");p.write_text(s)
# If the hold ends with exact release, the root launcher records a successful partial hold.
p=R/'audit/root_run_batch.py';s=p.read_text();old="""            if state.get('completed')==order:return True
            service.assert_owned(owner);return False
""";new="""            if state.get('completed')==order:return True
            if state.get('completed')==order[:2] and service.current_identity(owner['pid']) is None:
                return 'first_pair_released_after_review_hold'
            service.assert_owned(owner);return False
""";assert old in s;s=s.replace(old,new)
s=s.replace("        wait_until(completed,57600,'seven-pair completion deadline',20)","        terminal=wait_until(completed,57600,'seven-pair completion deadline',20)")
s=s.replace("        for source in SOURCES:\n", "        finished_sources=SOURCES if terminal is True else SOURCES[:1]\n        for source in finished_sources:\n")
s=s.replace("'jobs':order,'GPU_released':True,'further_registered_jobs':0", "'jobs':order if terminal is True else order[:2],'GPU_released':True,'remaining_registered_jobs':0 if terminal is True else len(order)-2")
p.write_text(s)
