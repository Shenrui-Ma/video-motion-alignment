"""Root-admitted fresh source/target tracking through unchanged R63 numerics."""
import argparse
import os
import socket
import subprocess
import time
from common import *
from bindings import configure_tracker

class ResourceUnavailable(RuntimeError):
    pass

def identity():
    path = Path('/proc') / str(os.getpid())
    return {'pid': os.getpid(), 'uid': path.stat().st_uid, 'start_ticks': path.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19], 'cmdline_sha256': sha(path / 'cmdline')}

def check_owned_cap(rows, uuid, uid):
    owned = {row['gpu_uuid'] for row in rows if row['uid'] == uid}
    if len(owned | {uuid}) > 2:
        raise ResourceUnavailable('tracker would exceed two owned GPU cards')

def resource_snapshot(uuid):
    require(uuid.startswith('GPU-') and os.environ.get('CUDA_VISIBLE_DEVICES') == uuid, 'exact root-admitted visible GPU required')
    result = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid', '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True, timeout=10)
    rows = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        pid, gpu = [part.strip() for part in line.split(',')]
        try:
            uid = (Path('/proc') / pid).stat().st_uid
        except FileNotFoundError as error:
            raise ResourceUnavailable('compute process exited during ownership snapshot') from error
        rows.append({'pid': int(pid), 'uid': uid, 'gpu_uuid': gpu})
    check_owned_cap(rows, uuid, os.getuid())
    result = subprocess.run(['nvidia-smi', '--id=' + uuid, '--query-gpu=uuid,name,memory.free,temperature.gpu', '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True, timeout=10)
    values = [line.split(',') for line in result.stdout.splitlines() if line.strip()]
    require(len(values) == 1 and len(values[0]) == 4 and values[0][0].strip() == uuid and not result.stderr.strip(), 'selected GPU snapshot invalid')
    free, temp = map(float, values[0][2:]); config = read(ROOT / 'configs/paths.json'); minimum = config['tracker_initial_free_bytes']
    require(free >= 0 and 0 <= temp < 85, 'GPU health snapshot invalid')
    if free * 1024**2 < minimum:
        raise ResourceUnavailable('tracker free memory below bootstrap threshold: ' + str(free))
    return {'hostname': socket.gethostname(), 'gpu_name': values[0][1].strip(), 'gpu_uuid': uuid, 'required_free_bytes': minimum, 'capacity_status': config['tracker_capacity_status'], 'memory_free_mib': free, 'temperature_c': temp, 'processes': rows, 'unix': time.time()}

def resource_check(uuid):
    deadline = time.monotonic() + 600
    while True:
        try:
            return resource_snapshot(uuid)
        except (ResourceUnavailable, subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
            if time.monotonic() >= deadline:
                raise TimeoutError('bounded tracker resource wait expired') from error
            time.sleep(min(1, deadline - time.monotonic()))

def root_gate(control, source, method, uuid, manifest, attempt):
    require(control is not None and os.environ.get('CUDA_VISIBLE_DEVICES') == uuid, 'actual tracker requires root control/UUID')
    control.mkdir(parents=True, exist_ok=False)
    ready = {'schema': 'r69-mf-root-preCUDA-v1', 'identity': identity(), 'source': source, 'method': method, 'gpu_uuid': uuid, 'attempt': attempt, 'input_manifest': bound(manifest), 'consumer_freeze_sha256': sha(ROOT / 'CONSUMER_FREEZE.json'), 'required_free_bytes': read(ROOT / 'configs/paths.json')['tracker_initial_free_bytes'], 'CUDA_started': False}
    save(control / 'ready.json', ready); print(json.dumps({'ready': str(control / 'ready.json'), 'identity': ready['identity']}), flush=True)
    deadline = time.monotonic() + 600
    while not (control / 'go.json').exists():
        require(identity() == ready['identity'], 'tracker process generation changed')
        if time.monotonic() >= deadline:
            raise TimeoutError('root tracking registration timed out')
        time.sleep(.2)
    require(read(control / 'go.json') == ready and identity() == ready['identity'] and bound(manifest) == ready['input_manifest'], 'root tracking authorization/input changed')
    verify_runtime()

def main():
    p = argparse.ArgumentParser(); p.add_argument('--source', choices=PAIRS, required=True); p.add_argument('--method', choices=('source',) + METHODS, required=True); p.add_argument('--gpu-uuid'); p.add_argument('--attempt', type=int, default=1); p.add_argument('--control', type=Path); p.add_argument('--check-only', action='store_true'); p.add_argument('--ffmpeg', default='ffmpeg'); p.add_argument('--ffprobe', default='ffprobe')
    a = p.parse_args(); require(a.attempt >= 1, 'positive attempt required'); verify_runtime()
    manifest = source_manifest(a.source) if a.method == 'source' else ROOT / 'prepared' / a.source / 'METRIC_INPUTS.json'
    require(manifest.is_file(), 'prepared actual input is pending')
    if not a.check_only:
        root_gate(a.control, a.source, a.method, a.gpu_uuid, manifest, a.attempt)
    tracker = configure_tracker(a.source)
    tracker.check_gpu = resource_check
    output = ROOT / ('preflight' if a.check_only else 'tracks') / a.method / a.source / ('attempt' + str(a.attempt))
    args = argparse.Namespace(input_manifest=str(manifest), selection=str(SELECTION), pair=a.source, method=a.method, gpu_uuid=a.gpu_uuid, check_only=a.check_only, output=str(output), ffmpeg=a.ffmpeg, ffprobe=a.ffprobe)
    tracker.main(args)
    save(output / 'R69_BINDING.json', {'source': a.source, 'method': a.method, 'actual_tracking': not a.check_only, 'manifest': bound(manifest), 'report': bound(output / ('PREFLIGHT.json' if a.check_only else 'REPORT.json')), 'numerical_tracker': bound(RUNTIME / 'metric_runtime/run_tracks.py'), 'consumer_freeze_sha256': sha(ROOT / 'CONSUMER_FREEZE.json'), 'selection_sha256': sha(SELECTION), 'fixed_denominator': 5})

if __name__ == '__main__':
    main()
