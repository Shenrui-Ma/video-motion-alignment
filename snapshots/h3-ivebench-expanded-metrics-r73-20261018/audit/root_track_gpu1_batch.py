"""Root-only administrative tracker launcher; scientific tracking code is frozen."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/data5/researcher/h3_runs/ivebench_expanded_metrics_r73_20261018')
PRODUCER = Path('/data5/researcher/h3_runs/timing_ivebench_expanded_r73_20261018')
PEERS = [
    (PRODUCER, 40927, '2632511242'),
]
GPU = 'GPU-REDACTED'
PYTHON = '/home/researcher/miniconda3/envs/comfyui/bin/python'
sys.path.insert(0, str(PRODUCER / 'scripts'))
import service

def read(path):
    return json.loads(path.read_text())

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)

def peers():
    result = []
    for root, pid, start in PEERS:
        owner = read(root / 'processes/service.json')
        assert owner['pid'] == pid and owner['identity']['start_ticks'] == start
        assert service.current_identity(pid) == owner['identity']
        result.append(root)
    return result

def register(roots, pid, identity, adding):
    for root in roots:
        path = root / 'configs/admission.json'
        value = read(path)
        entries = value['permitted_compute_processes']
        if adding:
            assert all(row['pid'] != pid for row in entries)
            entries.append({'pid': pid, 'identity': identity})
        else:
            assert all(row['pid'] != pid or row['identity'] == identity for row in entries)
            value['permitted_compute_processes'] = [row for row in entries if row['pid'] != pid]
        save(path, value)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', required=True)
    parser.add_argument('--items', nargs='+', required=True)
    args = parser.parse_args()
    audit = ROOT / 'audit' / args.batch
    audit.mkdir(exist_ok=False)
    roots = peers()
    completed = []
    for item in args.items:
        source, method = item.split(':')
        assert source in ('short_0252', 'short_0344', 'short_0065', 'short_0135', 'short_0035')
        assert method in ('source', 'native', 'forced')
        control = ROOT / 'controls' / (args.batch + '_' + source + '_' + method)
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=GPU, PYTHONDONTWRITEBYTECODE='1',
                   OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                   PYTHONPATH='/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps')
        argv = [PYTHON, '-u', 'scripts/track_one.py', '--source', source, '--method', method,
                '--gpu-uuid', GPU, '--attempt', '1', '--control', str(control)]
        with (audit / (source + '_' + method + '.log')).open('xb') as log:
            child = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=log, start_new_session=True)
        identity = None
        try:
            deadline = time.monotonic() + 120
            while not (control / 'ready.json').exists():
                assert child.poll() is None and time.monotonic() < deadline
                time.sleep(.2)
            ready = read(control / 'ready.json')
            identity = service.external_identity(child.pid)
            assert ready['identity'] == dict(identity, pid=child.pid)
            assert ready['gpu_uuid'] == GPU and ready['CUDA_started'] is False
            assert peers() == roots
            register(roots, child.pid, identity, True)
            save(control / 'go.json', ready)
            code = child.wait(timeout=1000)
            assert not Path('/proc', str(child.pid)).exists()
            assert child.pid not in [row['pid'] for row in service.compute_processes()]
            register(roots, child.pid, identity, False)
            assert code == 0, (item, code)
            output = ROOT / 'tracks' / method / source / 'attempt1'
            report = read(output / 'REPORT.json')
            assert report['passed'] and report['pid'] == child.pid
            assert report['tracks_shape'] == [1, report['effective_frame_count'], 100, 2]
            assert hashlib.sha256((output / 'tracks.npz').read_bytes()).hexdigest() == report['tracks_sha256']
            row = {'item': item, 'pid': child.pid, 'exit_code': code, 'process_absent': True,
                   'CUDA_allocation_absent': True, 'wall_seconds': report['wall_seconds'],
                   'peak_reserved_bytes': report['peak_reserved_bytes'], 'unix': time.time()}
            completed.append(row)
            save(audit / 'PROGRESS.json', {'completed': completed})
            print(json.dumps(row), flush=True)
        except BaseException as error:
            save(audit / 'FAILURE.json', {'item': item, 'pid': child.pid, 'identity': identity,
                                        'error': repr(error), 'unix': time.time()})
            if child.poll() is None and identity is not None and service.external_identity(child.pid) == identity:
                child.terminate()
                child.wait(timeout=30)
            if child.poll() is not None and identity is not None:
                assert child.pid not in [row['pid'] for row in service.compute_processes()]
                register(roots, child.pid, identity, False)
            raise
    save(audit / 'COMPLETE.json', {'passed': True, 'completed': completed, 'unix': time.time()})

if __name__ == '__main__':
    main()
