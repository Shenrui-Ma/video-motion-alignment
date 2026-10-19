"""Exact-generation gate; substitutes only runtime admission in the frozen MF runner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
RUNTIME = Path('/data3/researcher/h3_runs/ivebench_official_metric_20261017/metric_runtime')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity():
    p = Path('/proc') / str(os.getpid())
    return {'uid': p.stat().st_uid, 'start_ticks': p.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19],
            'cmdline_sha256': sha(p / 'cmdline')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--control', required=True)
    ap.add_argument('runner_arguments', nargs=argparse.REMAINDER)
    outer = ap.parse_args()
    arguments = outer.runner_arguments[1:] if outer.runner_arguments[:1] == ['--'] else outer.runner_arguments
    binding = [RUNTIME / 'run_tracks.py', RUNTIME / 'ive_mf_adapter.py', HERE / 'tracking_gate.py',
               HERE / 'shared_resource.py', HERE / 'MEMORY_REQUIREMENT.json']
    for flag in ['--input-manifest', '--selection']:
        binding.append(Path(arguments[arguments.index(flag) + 1]))
    control = Path(outer.control)
    control.mkdir(parents=True, exist_ok=False)
    ready = {'pid': os.getpid(), 'identity': identity(), 'CUDA_started': False,
             'gpu_uuid': os.environ.get('CUDA_VISIBLE_DEVICES'), 'arguments': arguments,
             'bindings': [{'file': str(f), 'sha256': sha(f)} for f in binding],
             'engineering_revision': 'measured_memory_admission_only'}
    temp = control / 'ready.tmp'
    temp.write_text(json.dumps(ready, indent=2) + '\n')
    temp.replace(control / 'ready.json')
    start = time.monotonic()
    while not (control / 'go.json').exists():
        if time.monotonic() - start > 600:
            raise TimeoutError('preCUDA admission timeout')
        time.sleep(.1)
    if json.loads((control / 'go.json').read_text()) != ready or identity() != ready['identity']:
        raise ValueError('admitted process generation differs')
    if any(sha(f['file']) != f['sha256'] for f in ready['bindings']):
        raise ValueError('admitted binding changed')
    parser = argparse.ArgumentParser()
    for flag in ['--input-manifest', '--selection', '--pair', '--method', '--output']:
        parser.add_argument(flag, required=True)
    parser.add_argument('--gpu-uuid')
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--ffmpeg', default='/usr/bin/ffmpeg')
    parser.add_argument('--ffprobe', default='/usr/bin/ffprobe')
    args = parser.parse_args(arguments)
    sys.path.insert(0, str(RUNTIME))
    import run_tracks
    from shared_resource import check_gpu
    run_tracks.check_gpu = check_gpu
    run_tracks.main(args)


if __name__ == '__main__':
    main()
