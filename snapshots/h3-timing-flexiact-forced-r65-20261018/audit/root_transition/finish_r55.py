"""Finish the existing R55 queue and release its recorded service after CPU verification."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path('/data3/researcher/h3_runs/timing_ivebench_auto_r55_20261017')
OUT = Path('/data3/researcher/h3_runs/timing_flexiact_forced_r65_20261018/audit/root_transition')
EXPECTED_PID = 111012
EXPECTED_TICKS = '1494784'
EXPECTED_CMD_SHA = 'fb230d3870cd649aaba80e75483437ff93a56bf5b0fc2b9eb60b27abc13038bd'


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


def assert_original_service(owner):
    assert owner['pid'] == EXPECTED_PID
    assert str(owner['identity']['start_ticks']) == EXPECTED_TICKS
    proc = Path('/proc') / str(EXPECTED_PID)
    assert proc.stat().st_uid == os.getuid() == 1004
    assert (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19] == EXPECTED_TICKS
    assert hashlib.sha256((proc / 'cmdline').read_bytes()).hexdigest() == EXPECTED_CMD_SHA


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    owner = read(ROOT / 'processes/service.json')
    assert_original_service(owner)
    order = read(ROOT / 'configs/queue.json')['jobs']
    assert len(order) == len(set(order)) == 5
    deadline = time.monotonic() + 7200
    while True:
        assert read(ROOT / 'processes/service.json') == owner
        assert_original_service(owner)
        state = read(ROOT / 'logs/controller_state.json')
        assert state['status'] != 'failed', state
        if state.get('completed') == order:
            break
        assert time.monotonic() < deadline, 'R55 completion wait exceeded two hours'
        time.sleep(15)
    write(OUT / 'R55_FINISHED_QUEUE.json', state)
    result_path = OUT / 'R55_RUNTIME_GATE_RESIDENT.json'
    assert not result_path.exists()
    command = ['/data3/researcher/ComfyUI/.venv/bin/python',
               str(ROOT / 'scripts/verify_completed.py'), '--allow-resident',
               '--output', str(result_path)]
    with (OUT / 'verification.log').open('wb') as log:
        subprocess.run(command, cwd=ROOT / 'scripts', check=True, timeout=900,
                       stdout=log, stderr=subprocess.STDOUT,
                       env=dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1'))
    gate = read(result_path)
    assert gate['status'] == 'pass' and not gate['partial_batch']
    assert gate['planned_denominator'] == 5 and gate['verified_runs'] == order
    # The consumer inventories queue.json; let its atomic intake finish first.
    case_ready = ROOT / 'analysis/postrun/completed_cases/r55_short_0370_seed2026101701_auto/CASE_READY.json'
    deadline = time.monotonic() + 900
    while not case_ready.is_file():
        assert time.monotonic() < deadline, 'Last case intake is pending'
        time.sleep(2)
    assert_original_service(owner)
    queue = read(ROOT / 'configs/queue.json')
    assert queue['jobs'] == order
    queue['finalize'] = True
    write(ROOT / 'configs/queue.json', queue)
    deadline = time.monotonic() + 180
    cleanup = ROOT / 'processes/cleanup.json'
    while not cleanup.exists():
        assert time.monotonic() < deadline, 'Recorded controller cleanup is pending'
        time.sleep(2)
    released = read(cleanup)
    assert released['pid'] == EXPECTED_PID and released['service_record'] == owner
    assert released['process_absent'] and released['own_compute_absent'] and released['child_compute_absent']
    assert not (Path('/proc') / str(EXPECTED_PID)).exists()
    write(OUT / 'R55_RELEASED.json', {'status': 'pass', 'unix': time.time(),
          'runtime_gate_sha256': hashlib.sha256(result_path.read_bytes()).hexdigest(),
          'cleanup': released})
    print('R55 full five-case runtime verification passed; recorded service released.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        OUT.mkdir(parents=True, exist_ok=True)
        write(OUT / 'FAILURE.json', {'unix': time.time(), 'error': repr(exc)})
        raise
