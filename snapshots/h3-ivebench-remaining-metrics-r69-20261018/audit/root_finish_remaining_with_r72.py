"""Root-owned completion sequence for the already admitted R69 generation batch."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path('/data3/researcher/h3_runs/ivebench_remaining_metrics_r69_20261018')
PRODUCER = Path('/data3/researcher/h3_runs/timing_ivebench_remaining_r69_20261018')
PEER = Path('/data3/researcher/h3_runs/timing_flexiact_prompt_pair_r72_20261018')
PYTHON = '/data3/researcher/ComfyUI/.venv/bin/python'
sys.path.insert(0, str(PRODUCER / 'scripts'))
import service


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


def main():
    audit = ROOT / 'audit/root_finish_remaining_attempt1'
    audit.mkdir(exist_ok=False)
    owner = read(PRODUCER / 'processes/service.json')
    assert owner['pid'] == 470280 and owner['identity']['start_ticks'] == '6354308'
    service.assert_owned(owner)
    external = service.external_identity(owner['pid'])
    controller = read(PRODUCER / 'processes/controller.json')
    assert controller['pid'] == 471455 and controller['identity']['start_ticks'] == '6363391'
    original_plan = read(PRODUCER / 'configs/queue.json')
    assert original_plan['finalize'] is False and len(original_plan['jobs']) == 8
    items = [s + ':' + m for s in ('short_0263', 'short_0352', 'short_0370') for m in ('native', 'forced')]
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1',
               OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
               PYTHONPATH='/data3/researcher/h3_runs/closure_tutorials_53592/01-anime/runtime_deps')
    deadline = time.monotonic() + 5400
    try:
        while True:
            service.assert_owned(owner)
            assert service.current_identity(controller['pid']) == controller['identity']
            assert read(PRODUCER / 'configs/queue.json') == original_plan
            state = read(PRODUCER / 'logs/controller_state.json')
            assert state['status'] != 'failed', state
            ready = all((ROOT / 'prepared' / s / 'READY.json').is_file()
                        for s in ('short_0263', 'short_0352', 'short_0370'))
            if state['status'] == 'resident_hold' and state['completed'] == original_plan['jobs'] and ready:
                break
            assert time.monotonic() < deadline, 'generation/CPU preparation wait expired'
            time.sleep(10)
        for s in ('short_0263', 'short_0352', 'short_0370'):
            assert read(PRODUCER / 'analysis/postrun' / s / 'PAIR_RUNTIME_GATE.json')['passed']
            assert read(ROOT / 'prepared' / s / 'READY.json')['passed']
        queue = service.queue_at(8538)
        assert not queue['queue_running'] and not queue['queue_pending']
        request = urllib.request.Request('http://127.0.0.1:8538/free',
                  data=json.dumps({'unload_models': True, 'free_memory': True}).encode(),
                  headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=30) as response:
            assert response.status == 200
        write(audit / 'GENERATION_COMPLETE.json', {'passed': True, 'state': state, 'queue': queue, 'unix': time.time()})
        print('R69 generation and CPU gates complete; unloaded models, starting six target tracks.', flush=True)
        subprocess.run([PYTHON, '-u', str(ROOT / 'audit/root_track_gpu7_with_r72.py'),
                        '--batch', 'root_remaining_targets_attempt1', '--items', *items],
                       cwd=ROOT, env=env, check=True, timeout=6000)
        assert read(ROOT / 'audit/root_remaining_targets_attempt1/COMPLETE.json')['passed']
        for item in items:
            source, method = item.split(':')
            subprocess.run([PYTHON, 'scripts/score_one.py', '--source', source, '--method', method],
                           cwd=ROOT, env=env, check=True, timeout=300)
        assert read(PRODUCER / 'configs/queue.json') == original_plan
        write(PRODUCER / 'configs/queue.json', dict(original_plan, finalize=True))
        deadline = time.monotonic() + 120
        pids = [470280, 471455, 470267]
        while any(Path('/proc', str(pid)).exists() for pid in pids):
            assert time.monotonic() < deadline, 'awaiting exact service/controller/supervisor exit'
            time.sleep(1)
        assert not any(row['pid'] in pids for row in service.compute_processes())
        admission = PEER / 'configs/admission.json'
        value = read(admission)
        matches = [row for row in value['permitted_compute_processes'] if row['pid'] == owner['pid']]
        assert len(matches) == 1 and matches[0]['identity'] == external, matches
        value['permitted_compute_processes'] = [row for row in value['permitted_compute_processes'] if row['pid'] != owner['pid']]
        write(admission, value)
        write(audit / 'COMPLETE.json', {'passed': True, 'exact_pids_absent': pids,
              'CUDA_allocation_absent': True, 'peer_removed': str(admission),
              'tracked_and_scored': items, 'unix': time.time()})
        print('R69 six target scores complete; exact GPU service released.', flush=True)
    except BaseException as error:
        write(audit / 'FAILURE.json', {'error': repr(error), 'unix': time.time()})
        raise


if __name__ == '__main__':
    main()
