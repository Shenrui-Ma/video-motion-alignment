"""Run the frozen FlexiAct tracker with measured-memory admission on .41."""
import argparse
import math
import os
import platform
import subprocess
import sys
import time
from common import METRIC, ROOT, Path, bound, load, read, require, save, sha, verify_runtime

REQUIRED_FREE_BYTES = 40 * 1024**3


def process_uid(pid):
    try:
        return (Path('/proc') / str(pid)).stat().st_uid
    except FileNotFoundError:
        return None  # The process exited between nvidia-smi and /proc lookup.


def resource_check(uuid):
    require(isinstance(uuid, str) and uuid.startswith('GPU-') and
            os.environ.get('CUDA_VISIBLE_DEVICES') == uuid, 'exact root-admitted UUID required')
    q = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid',
                        '--format=csv,noheader,nounits'], capture_output=True, text=True,
                       timeout=10, check=True)
    processes, owned = [], set()
    for line in q.stdout.splitlines():
        if not line.strip():
            continue
        pid, gpu = [item.strip() for item in line.split(',')]
        pid = int(pid)
        uid = process_uid(pid)
        if uid == os.getuid():
            owned.add(gpu)
        processes.append({'pid': pid, 'uid': uid, 'gpu_uuid': gpu, 'exited_before_uid_read': uid is None})
    require(len(owned | {uuid}) <= 2, 'tracking would exceed two owned GPUs')
    q = subprocess.run(['nvidia-smi', '--id=' + uuid,
                        '--query-gpu=uuid,index,name,memory.free,temperature.gpu',
                        '--format=csv,noheader,nounits'], capture_output=True, text=True,
                       timeout=10, check=True)
    rows = [[v.strip() for v in row.split(',')] for row in q.stdout.splitlines() if row.strip()]
    require(len(rows) == 1 and len(rows[0]) == 5 and rows[0][0] == uuid and
            not q.stderr.strip(), 'GPU snapshot invalid')
    _, index, name, free, temperature = rows[0]
    free, temperature = float(free), float(temperature)
    require(math.isfinite(free) and free * 1024**2 >= REQUIRED_FREE_BYTES and
            math.isfinite(temperature) and 0 <= temperature < 85,
            'tracker requires 40 GiB current free memory and healthy GPU')
    return {'observed_unix': time.time(), 'hostname': platform.node(), 'gpu_uuid': uuid,
            'gpu_index': int(index), 'gpu_name': name, 'required_free_bytes': REQUIRED_FREE_BYTES,
            'memory_free_mib': free, 'temperature_c': temperature,
            'owned_gpu_uuids_including_selected': sorted(owned | {uuid}), 'processes': processes,
            'policy': 'shared contexts allowed; actual free >= 40 GiB; own <= 2 GPUs'}


def identity():
    proc = Path('/proc') / str(os.getpid())
    raw = (proc / 'cmdline').read_bytes()
    require(bool(raw), 'current launcher cmdline is empty')
    import hashlib
    return {'uid': proc.stat().st_uid,
            'start_ticks': (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19],
            'cmdline_sha256': hashlib.sha256(raw).hexdigest()}


def register(control, arguments):
    verify_runtime()
    control = Path(control)
    control.mkdir(parents=True, exist_ok=False)
    manifest = Path(arguments[arguments.index('--input-manifest') + 1])
    record = {'pid': os.getpid(), 'identity': identity(), 'CUDA_started': False,
              'gpu_uuid': os.environ.get('CUDA_VISIBLE_DEVICES'),
              'target_sha256': sha(METRIC / 'run_tracks.py'),
              'wrapper_sha256': sha(__file__), 'consumer_freeze_sha256': sha(ROOT / 'CONSUMER_FREEZE.json'),
              'input_manifest': bound(manifest), 'arguments': arguments,
              'required_free_bytes': REQUIRED_FREE_BYTES}
    save(control / 'ready.tmp', record)
    (control / 'ready.tmp').replace(control / 'ready.json')
    started = time.monotonic()
    while not (control / 'go.json').exists():
        if time.monotonic() - started > 600:
            raise TimeoutError('Root peer registration was not completed')
        time.sleep(.1)
    require(read(control / 'go.json') == record and identity() == record['identity'],
            'Root gate or process identity differs')
    require(sha(manifest) == record['input_manifest']['sha256'] and
            sha(ROOT / 'CONSUMER_FREEZE.json') == record['consumer_freeze_sha256'],
            'tracking binding changed during root registration')
    verify_runtime()
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--control', required=True)
    parser.add_argument('runner_arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    arguments = args.runner_arguments
    if arguments[:1] == ['--']:
        arguments = arguments[1:]
    record = register(args.control, arguments)
    output = Path(arguments[arguments.index('--output') + 1])
    sys.path.insert(0, str(METRIC))
    original = load('r101_frozen_run_tracks', METRIC / 'run_tracks.py')
    original.check_gpu = resource_check
    sys.argv = [str(METRIC / 'run_tracks.py')] + arguments
    try:
        original.main()
    finally:
        if (output / 'REPORT.json').is_file():
            save(output / 'R101_BINDING.json', {'root_registration': record,
                 'report': bound(output / 'REPORT.json'), 'frozen_numerical_tracker': bound(METRIC / 'run_tracks.py'),
                 'administrative_wrapper': bound(__file__), 'hostname': platform.node()})


if __name__ == '__main__':
    main()
