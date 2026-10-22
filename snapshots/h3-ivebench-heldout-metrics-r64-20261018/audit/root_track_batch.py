"""Root administrative launcher; leaves frozen tracking numerics unchanged."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/data3/researcher/h3_runs/ivebench_heldout_metrics_r64_20261018')
PRODUCER = Path('/data3/researcher/h3_runs/timing_ivebench_heldout_r64_20261018')
GPU = 'GPU-REDACTED'
PYTHON = '/data3/researcher/ComfyUI/.venv/bin/python'
sys.path.insert(0, str(PRODUCER / 'scripts'))
import service

def read(path):
    return json.loads(path.read_text())

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', required=True)
    parser.add_argument('--items', nargs='+', required=True)
    args = parser.parse_args()
    audit = ROOT / 'audit' / args.batch
    audit.mkdir(exist_ok=False)
    owner = read(PRODUCER / 'processes/service.json')
    assert owner['pid'] == 442121 and owner['identity']['start_ticks'] == '6176539'
    service.assert_owned(owner)
    completed = []
    for item in args.items:
        source, method = item.split(':')
        assert source in ('short_0092', 'short_0114', 'short_0126', 'short_0392')
        assert method in ('source', 'native', 'forced')
        control = ROOT / 'controls' / (args.batch + '_' + source + '_' + method)
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=GPU, PYTHONDONTWRITEBYTECODE='1')
        argv = [PYTHON, '-u', 'scripts/track_one.py', '--source', source, '--method', method,
                '--gpu-uuid', GPU, '--attempt', '1', '--control', str(control)]
        with (audit / (source + '_' + method + '.log')).open('xb') as log:
            child = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=log, start_new_session=True)
        deadline = time.monotonic() + 120
        while not (control / 'ready.json').exists():
            assert child.poll() is None and time.monotonic() < deadline
            time.sleep(.2)
        ready = read(control / 'ready.json')
        actual = service.external_identity(child.pid)
        assert ready['identity'] == dict(actual, pid=child.pid)
        assert ready['gpu_uuid'] == GPU and ready['CUDA_started'] is False
        admission = read(PRODUCER / 'configs/admission.json')
        assert child.pid not in [row['pid'] for row in admission['permitted_compute_processes']]
        admission['permitted_compute_processes'].append({'pid': child.pid, 'identity': actual})
        save(PRODUCER / 'configs/admission.json', admission)
        save(control / 'go.json', ready)
        result = child.wait(timeout=1000)
        assert not Path('/proc', str(child.pid)).exists()
        remaining = service.compute_processes()
        assert child.pid not in [row['pid'] for row in remaining]
        admission = read(PRODUCER / 'configs/admission.json')
        admission['permitted_compute_processes'] = [row for row in admission['permitted_compute_processes'] if row['pid'] != child.pid]
        save(PRODUCER / 'configs/admission.json', admission)
        assert result == 0, (item, result)
        output = ROOT / 'tracks' / method / source / 'attempt1'
        report = read(output / 'REPORT.json')
        assert report['passed'] and report['pid'] == child.pid
        assert report['tracks_shape'] == [1, report['effective_frame_count'], 100, 2]
        assert hashlib.sha256((output / 'tracks.npz').read_bytes()).hexdigest() == report['tracks_sha256']
        row = {'item': item, 'pid': child.pid, 'exit_code': result, 'process_absent': True,
               'CUDA_allocation_absent': True, 'wall_seconds': report['wall_seconds'],
               'peak_reserved_bytes': report['peak_reserved_bytes'], 'unix': time.time()}
        completed.append(row)
        save(audit / 'PROGRESS.json', {'completed': completed})
        print(json.dumps(row), flush=True)
    save(audit / 'COMPLETE.json', {'passed': True, 'completed': completed, 'unix': time.time()})

if __name__ == '__main__':
    main()
