"""Root-owned handoff after the exact R64 generation and metric jobs finish."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/data3/researcher/h3_runs/timing_flexiact_prompt_pair_r72_20261018')
PREVIOUS = Path('/data3/researcher/h3_runs/ivebench_heldout_metrics_r64_20261018')
PEER = Path('/data3/researcher/h3_runs/timing_ivebench_remaining_r69_20261018')
sys.path.insert(0, str(ROOT / 'scripts'))
import service


def read(path):
    return json.loads(path.read_text())


def main():
    audit = ROOT / 'audit/root_launch_after_r64_attempt1'
    audit.mkdir(exist_ok=False)
    deadline = time.monotonic() + 3600
    previous_audit = PREVIOUS / 'audit/root_finish_remaining_attempt1'
    while not (previous_audit / 'COMPLETE.json').exists():
        if (previous_audit / 'FAILURE.json').exists():
            raise RuntimeError(read(previous_audit / 'FAILURE.json'))
        assert time.monotonic() < deadline, 'R64 completion wait expired'
        time.sleep(5)
    completed = read(previous_audit / 'COMPLETE.json')
    assert completed['passed'] and completed['CUDA_allocation_absent']
    assert completed['exact_pids_absent'] == [442121, 443527, 442106]
    assert all(not Path('/proc', str(pid)).exists() for pid in completed['exact_pids_absent'])
    peer = read(PEER / 'processes/service.json')
    assert peer['pid'] == 470280 and peer['identity']['start_ticks'] == '6354308'
    assert service.current_identity(peer['pid']) == peer['identity']
    peer_identity = service.external_identity(peer['pid'])
    rows = service.compute_processes()
    owned = [row for row in rows if service.proc_uid(row['pid']) == os.getuid()]
    assert all(row['pid'] == peer['pid'] for row in owned), owned
    admission = read(ROOT / 'configs/admission.json')
    assert admission['ready_for_launch'] is False
    admission.update(ready_for_launch=True, existing_comfy_port=None,
                     permitted_compute_processes=[{'pid': peer['pid'], 'identity': peer_identity}])
    service.write_json(ROOT / 'configs/admission.json', admission)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    subprocess.run(['python3', 'scripts/execution_gate.py', 'approve-first-pair',
                    '--root-admitted', '--free-mib', '40960'], cwd=ROOT, env=env, check=True)
    with (audit / 'launch.log').open('xb') as log:
        subprocess.run(['python3', '-u', 'scripts/launch_remote.py', '--service-only'],
                       cwd=ROOT, env=env, stdout=log, stderr=log, check=True, timeout=720)
    owner = read(ROOT / 'processes/service.json')
    ready = read(ROOT / 'processes/cuda_gate_ready.json')
    service.assert_owned(owner)
    assert ready['pid'] == owner['pid'] and ready['identity'] == service.external_identity(owner['pid'])
    assert ready['supervisor']['identity'] == service.external_identity(ready['supervisor']['pid'])
    assert service.current_identity(peer['pid']) == peer['identity']
    peer_admission = read(PEER / 'configs/admission.json')
    assert all(row['pid'] != owner['pid'] for row in peer_admission['permitted_compute_processes'])
    peer_admission['permitted_compute_processes'].append({'pid': owner['pid'], 'identity': ready['identity']})
    service.write_json(PEER / 'configs/admission.json', peer_admission)
    service.write_json(ROOT / 'processes/cuda_gate_go.json', ready)
    deadline = time.monotonic() + 180
    while True:
        service.assert_owned(owner)
        try:
            queue = service.queue_at(service.PORT)
            break
        except OSError:
            assert time.monotonic() < deadline, 'R72 HTTP readiness expired'
            time.sleep(1)
    assert not queue['queue_running'] and not queue['queue_pending']
    subprocess.run(['python3', 'scripts/start_controller.py', '--pid', str(owner['pid']),
                    '--start-ticks', owner['identity']['start_ticks']], cwd=ROOT, env=env, check=True)
    service.write_json(audit / 'STARTED.json', {'owner': owner, 'controller': read(ROOT / 'processes/controller.json'),
                       'peer_registered': peer['pid'], 'previous_completion': completed, 'unix': time.time()})
    print('R72 admitted and started after exact R64 release.', flush=True)


if __name__ == '__main__':
    main()
