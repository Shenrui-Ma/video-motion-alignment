"""Root-only, one-time 0352 recovery. Frozen science/queue remain unchanged."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import uuid
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import service
import job
from execution_gate import first_native_gate, approval
from r80_contract import read, require, registry, sha

spec = importlib.util.spec_from_file_location('r80_root_helpers', ROOT / 'audit/root_run_pair.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
SOURCE = 'short_0352'
RUN_ID = 'r80_short_0352_seed2026101701_native'


def archive_old_processes(root, audit, *, lookup=None, query=None):
    """Preserve all original generation records after exact absence checks."""
    lookup = lookup or service.current_identity
    query = query or service.compute_processes
    root, audit = Path(root), Path(audit)
    directory = root / 'processes'
    require((directory / 'service.json').is_file(), 'old service registry missing; inspect recovery state')
    files = sorted(directory.rglob('*.json'))
    rows = []
    for path in files:
        value = read(path)
        if isinstance(value, dict) and 'pid' in value and 'identity' in value:
            pid = int(value['pid'])
            # Even a replacement PID is rejected here; this function sends no signals.
            require(lookup(pid) is None, 'recorded process PID is still live: ' + str(pid))
            rows.append({'file': str(path.relative_to(directory)), 'pid': pid, 'identity': value['identity']})
    compute = query()
    pids = {row['pid'] for row in rows}
    require(not any(row['pid'] in pids for row in compute), 'old PID still present in CUDA inventory')
    inventory = {str(p.relative_to(directory)): sha(p) for p in sorted(directory.rglob('*')) if p.is_file()}
    service.write_json(audit / 'OLD_GENERATION_ABSENCE.json', {'passed': True, 'records': rows, 'compute': compute, 'files': inventory, 'unix': time.time()})
    for name in ('controller_state.json', 'controller_error.json', 'controller_errors.json'):
        before = root / 'logs' / name
        if before.exists(): shutil.copyfile(before, audit / ('old_' + name))
    directory.rename(audit / 'old_processes')
    directory.mkdir()
    return rows


def register_recovery_controller(root, owner, token):
    """Give the existing watchdog an exact live controller without starting the old queue."""
    value = {'pid': os.getpid(), 'identity': service.identity(os.getpid()),
             'role': 'one_time_0352_recovery_controller', 'service_pid': owner['pid'],
             'service_identity': owner['identity'], 'root_attempt_token': token,
             'allowed_runs': [RUN_ID], 'created_unix': time.time()}
    service.write_json(Path(root) / 'processes/controller.json', value)
    return value


def successful_status(answer):
    status = answer.get('status')
    if isinstance(status, dict):
        require(status.get('status_str') != 'error', '0352 Comfy execution failed: ' + str(answer))
        return status.get('status_str') == 'success' and status.get('completed') is True
    require(status not in ('error', 'submission_uncertain'), '0352 status requires inspection: ' + str(answer))
    return False


def transport_failure(error):
    """Read-only polling may retry unavailable transport; explicit HTTP errors stay errors."""
    return isinstance(error, (TimeoutError, ConnectionError, urllib.error.URLError)) and not isinstance(error, urllib.error.HTTPError)


def poll_completed(owner, audit):
    service.assert_owned(owner)
    try:
        answer = job.status(RUN_ID)
    except Exception as error:
        if not transport_failure(error): raise
        service.write_json(Path(audit) / 'PROGRESS.json', {
            'run': RUN_ID, 'observation': 'UNKNOWN', 'reason': 'status_transport_unavailable',
            'error': repr(error), 'unix': time.time(), 'deadline_reset': False})
        return False
    service.write_json(Path(audit) / 'PROGRESS.json', {
        'run': RUN_ID, 'answer': answer, 'observation': 'UNKNOWN' if answer.get('status') == 'unknown_missing' else 'OBSERVED',
        'unix': time.time(), 'deadline_reset': False})
    return successful_status(answer)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true', required=True)
    parser.add_argument('--task-fidelity-reviewed', action='store_true', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--peer-root', action='append', default=[])
    args = parser.parse_args()
    require(ROOT == Path(service.RUNTIME['remote_root']), 'execution requires the actual remote root')
    require(args.attempt.replace('_', '').replace('-', '').isalnum(), 'invalid attempt name')
    audit = ROOT / 'audit' / args.attempt
    audit.mkdir(exist_ok=False)
    owner = None
    entry = None
    peers = []
    token = uuid.uuid4().hex
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', LC_ALL='C', LANG='C', H3_ROOT_ATTEMPT_TOKEN=token)
    cpuenv = dict(env, CUDA_VISIBLE_DEVICES='', PYTHONPATH=service.RUNTIME['dependencies'])

    def run(argv, *, timeout=720, cpu=False, name='execution.log'):
        with (audit / name).open('ab', buffering=0) as log:
            return subprocess.run(argv, cwd=ROOT, env=cpuenv if cpu else env,
                                  stdout=log, stderr=log, check=True, timeout=timeout)
    try:
        service.write_json(audit / 'ATTEMPT_BINDING.json', {'token': token, 'root': str(ROOT), 'script_sha256': sha(Path(__file__)), 'unix': time.time()})
        first = first_native_gate(ROOT)
        require(first.name == 'NATIVE_RUNTIME_GATE_HOST9_v2.json' and read(first)['passed'] is True, 'actual 0230 strict host9 v2 receipt required')
        approval(ROOT)
        _, order = registry(ROOT)
        require(order[1:] == [RUN_ID], '0352 recovery scope changed')
        require(not (ROOT / 'logs' / (RUN_ID + '_job.json')).exists(), '0352 job exists; preserve and inspect it')
        target_gate = ROOT / 'analysis/postrun' / SOURCE / 'NATIVE_RUNTIME_GATE_HOST9_v2.json'
        require(not target_gate.exists(), '0352 v2 gate already exists')
        seal = read(ROOT / 'deploy_manifest.json')
        require(all(sha(ROOT / path) == row['sha256'] for path, row in seal['files'].items()), 'frozen producer changed')
        service.write_json(audit / 'INPUT_BINDING.json', {'first_gate': str(first), 'first_gate_sha256': sha(first), 'producer_seal_sha256': sha(ROOT / 'deploy_manifest.json'), 'allowed_run': RUN_ID, 'task_fidelity_reviewed': True})
        archive_old_processes(ROOT, audit)
        peers = helpers.live_peers(args.peer_root)
        admission = {'ready_for_launch': True, 'scope': 'own_user_video_jobs', 'existing_comfy_port': None, 'permitted_compute_processes': helpers.peer_policy(peers)}
        service.write_json(ROOT / 'configs/admission.json', admission)
        service.wait_admission_snapshot(admission, {'queue_running': [], 'queue_pending': []})
        run(['python3', '-u', 'scripts/launch_remote.py', '--service-only'])
        candidate = read(ROOT / 'processes/service.json')
        require(candidate.get('root_attempt_token') == token, 'service belongs to a different attempt')
        service.assert_owned(candidate)
        owner = candidate
        ready = read(ROOT / 'processes/cuda_gate_ready.json')
        require(ready['pid'] == owner['pid'] and ready['identity'] == service.external_identity(owner['pid']), 'preCUDA identity mismatch')
        require(ready['supervisor']['identity'] == service.external_identity(ready['supervisor']['pid']), 'preCUDA supervisor identity mismatch')
        peers = helpers.live_peers(args.peer_root)
        entry = {'pid': owner['pid'], 'identity': ready['identity']}
        admission['permitted_compute_processes'] = helpers.peer_policy(peers)
        service.write_json(ROOT / 'configs/admission.json', admission)
        service.wait_admission_snapshot(admission, {'queue_running': [], 'queue_pending': []})
        for peer in peers: helpers.update_peer(peer, entry)
        controller = register_recovery_controller(ROOT, owner, token)
        service.write_json(audit / 'ADMITTED.json', {'owner': owner, 'ready': ready, 'peers': peers, 'controller': controller, 'unix': time.time()})
        service.write_json(ROOT / 'processes/cuda_gate_go.json', ready)

        def http_ready():
            service.assert_owned(owner)
            try: queue = service.queue_at(service.PORT)
            except OSError: return False
            require(not queue['queue_running'] and not queue['queue_pending'], 'unexpected task queue')
            return True
        helpers.wait_until(http_ready, 600, 'HTTP service unavailable')
        run(['python3', 'scripts/execution_gate.py', 'approve-second-native', '--root-admitted', '--task-fidelity-reviewed'])
        # The submit function binds this exact owner again while holding the job lock.
        job.submit(RUN_ID, expected_owner=owner)
        service.write_json(audit / 'STARTED.json', {'owner': owner, 'controller': controller, 'allowed_run': RUN_ID, 'unix': time.time()})

        helpers.wait_until(lambda: poll_completed(owner, audit), 18000, '0352 completion deadline', 20)
        cleanup = service.stop(expected_record=owner)
        require(cleanup['process_absent'] and cleanup['own_compute_absent'], 'exact release incomplete')
        service.write_json(audit / 'ROOT_EXIT_RECEIPT.json', {'passed': True, 'owner': owner, 'process_absent': True, 'CUDA_allocation_absent': True, 'cleanup': cleanup, 'unix': time.time()})
        for peer in peers: helpers.update_peer(peer, entry, remove=True)
        entry = None
        run([service.RUNTIME['python'], 'analysis/postrun/verify_native_host9_v2.py', '--source', SOURCE], cpu=True, name='0352_v2_verify.log', timeout=900)
        require(read(target_gate)['passed'] is True, 'actual 0352 v2 gate failed')
        run([service.RUNTIME['python'], 'audit/input_decode_recovery_v2/collect_v2.py', '--source', SOURCE], cpu=True, name='0352_collect.log', timeout=180)
        service.write_json(audit / 'COMPLETE_REVIEW_HOLD.json', {'passed': True, 'completed_run': RUN_ID, 'actual_gate_sha256': sha(target_gate), 'GPU_released': True, 'next_registered_submission': None, 'quality_review': 'PENDING_ROOT', 'unix': time.time()})
    except BaseException as error:
        owner = helpers.failure_cleanup(audit, error, owner, token)
        raise
    finally:
        if entry is not None and owner is not None:
            try:
                if service.current_identity(owner['pid']) is None:
                    for peer in peers:
                        try: helpers.update_peer(peer, entry, remove=True)
                        except BaseException as error: helpers.best_effort_receipt(audit / 'PEER_CLEANUP_ERROR.json', {'peer': peer['root'], 'error': repr(error)})
            except BaseException as error:
                helpers.best_effort_receipt(audit / 'PEER_CLEANUP_ERROR.json', {'error': repr(error)})


if __name__ == '__main__':
    def interrupted(signum, frame): raise KeyboardInterrupt('root recovery received signal ' + str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    with (ROOT / 'audit/root_execution.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        main()
