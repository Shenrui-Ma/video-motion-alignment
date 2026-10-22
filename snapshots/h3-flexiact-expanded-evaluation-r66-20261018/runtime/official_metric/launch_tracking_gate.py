"""Keep a stable PID while root records peer admission before CUDA use."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parent


def identity():
    proc = Path('/proc') / str(os.getpid())
    return {'uid': proc.stat().st_uid,
            'start_ticks': proc.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19],
            'cmdline_sha256': hashlib.sha256(proc.joinpath('cmdline').read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--control', required=True)
    parser.add_argument('runner_arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    directory = Path(args.control)
    directory.mkdir(parents=True, exist_ok=False)
    target = ROOT / 'run_tracks.py'
    record = {'pid': os.getpid(), 'identity': identity(), 'CUDA_started': False,
              'gpu_uuid': os.environ.get('CUDA_VISIBLE_DEVICES'),
              'target_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
              'arguments': args.runner_arguments}
    ready = directory / 'ready.json'
    temporary = directory / 'ready.tmp'
    temporary.write_text(json.dumps(record, indent=2) + '\n')
    temporary.replace(ready)
    start = time.monotonic()
    go = directory / 'go.json'
    while not go.exists():
        if time.monotonic() - start > 600:
            raise TimeoutError('Root peer registration was not completed')
        time.sleep(.1)
    if json.loads(go.read_text()) != record or identity() != record['identity']:
        raise ValueError('Root gate or process identity differs')
    if hashlib.sha256(target.read_bytes()).hexdigest() != record['target_sha256']:
        raise ValueError('Runner changed after admission')
    arguments = args.runner_arguments
    if arguments[:1] == ['--']:
        arguments = arguments[1:]
    sys.argv = [str(target)] + arguments
    runpy.run_path(str(target), run_name='__main__')


if __name__ == '__main__':
    main()
