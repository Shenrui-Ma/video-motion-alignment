"""Root runs five frozen source trackers sequentially on the second .41 GPU."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = Path('/data3/researcher/h3_runs')
R65 = BASE / 'timing_flexiact_forced_r65_20261018'
OUT = R65 / 'audit/root_transition'
GPU = 'GPU-REDACTED'
TASKS = [('flexiact_forced_metrics_r65_20261018', '--source', 'fitness'),
         ('flexiact_forced_metrics_r65_20261018', '--source', 'one_leg'),
         ('flexiact_expanded_evaluation_r66_20261018', '--key', 'human2animal_1'),
         ('flexiact_expanded_evaluation_r66_20261018', '--key', 'human2animal_3'),
         ('flexiact_expanded_evaluation_r66_20261018', '--key', 'human2animal_2')]


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


def main():
    deadline = time.monotonic() + 7200
    while not (OUT / 'R65_STARTED.json').is_file():
        assert not (OUT / 'R65_START_FAILURE.json').exists(), 'R65 launch failed'
        assert time.monotonic() < deadline, 'R65 startup wait exceeded two hours'
        time.sleep(10)
    sys.path.insert(0, str(R65 / 'scripts'))
    import service
    owner = read(OUT / 'R65_STARTED.json')['owner']
    service.assert_owned(owner)
    completed = []
    for folder, option, source in TASKS:
        root = BASE / folder
        plan = subprocess.run(['python3', str(root / 'scripts/tracking_plan.py'), option, source,
                               '--method', 'reference', '--gpu-uuid', GPU],
                              cwd=root, check=True, capture_output=True, text=True, timeout=120)
        argv = json.loads(plan.stdout)['argv']
        control = Path(argv[argv.index('--control') + 1])
        output = Path(argv[argv.index('--output') + 1])
        assert control.is_relative_to(root / 'controls') and output.is_relative_to(root / 'tracks/reference')
        assert not output.exists() and not control.exists()
        with (OUT / ('source_' + source + '.log')).open('xb') as log:
            child = subprocess.Popen(argv, cwd=root, stdin=subprocess.DEVNULL, stdout=log,
                                     stderr=log, start_new_session=True)
        deadline = time.monotonic() + 120
        while not (control / 'ready.json').exists():
            assert child.poll() is None, 'Source tracker exited before ready'
            assert time.monotonic() < deadline, 'Source ready timeout'
            time.sleep(.2)
        ready = read(control / 'ready.json')
        assert ready['pid'] == child.pid and ready['gpu_uuid'] == GPU and ready['CUDA_started'] is False
        assert ready['identity'] == service.external_identity(child.pid)
        service.assert_owned(owner)
        admission = read(R65 / 'configs/admission.json')
        admission['permitted_compute_processes'].append({'pid': child.pid, 'identity': ready['identity']})
        write(R65 / 'configs/admission.json', admission)
        write(control / 'go.json', ready)
        result = child.wait(timeout=900)
        assert result == 0, 'Source tracking failed; preserve its attempt and log'
        report = read(output / 'REPORT.json')
        assert report['passed'] and report['gpu_uuid'] == GPU and report['pid'] == child.pid
        assert report['tracks_shape'] == [3025, 49, 2] and report['nonfinite_track_values'] == 0
        assert hashlib.sha256((output / 'tracks.pt').read_bytes()).hexdigest() == report['tracks_sha256']
        assert not (Path('/proc') / str(child.pid)).exists()
        admission = read(R65 / 'configs/admission.json')
        admission['permitted_compute_processes'] = [p for p in admission['permitted_compute_processes'] if p['pid'] != child.pid]
        write(R65 / 'configs/admission.json', admission)
        completed.append({'source': source, 'output': str(output), 'pid': child.pid,
                          'wall_seconds': report['wall_seconds'], 'peak_reserved_bytes': report['peak_reserved_bytes']})
        write(OUT / 'SOURCE_TRACKING_PROGRESS.json', {'completed': completed})
        print(json.dumps(completed[-1]), flush=True)
    write(OUT / 'SOURCE_TRACKING_DONE.json', {'passed': True, 'completed': completed, 'unix': time.time()})


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        write(OUT / 'SOURCE_TRACKING_FAILURE.json', {'error': repr(exc), 'unix': time.time()})
        raise
