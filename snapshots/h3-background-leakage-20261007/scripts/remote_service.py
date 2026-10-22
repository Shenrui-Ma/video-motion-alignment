"""Launch or stop only this pilot's isolated ComfyUI service on .9."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

RUN = Path('/data5/researcher/h3_runs/background_leakage_pilot_20261007')
COMFY = Path('/data5/researcher/ComfyUI')
PYTHON = '/home/researcher/miniconda3/envs/comfyui/bin/python'
GPU = 'GPU-REDACTED'
PORT = 8387


def identity(pid):
    proc = Path('/proc') / str(pid)
    return {
        'uid': proc.stat().st_uid,
        'start_ticks': proc.joinpath('stat').read_text().split(') ', 1)[1].split()[19],
        'cmdline': proc.joinpath('cmdline').read_bytes().replace(b'\0', b' ').decode(),
    }


def gpu_processes():
    result = subprocess.run(
        ['nvidia-smi', '--query-compute-apps=gpu_uuid,pid,used_memory', '--format=csv,noheader,nounits'],
        capture_output=True, text=True, check=True,
    )
    return [line for line in result.stdout.splitlines() if line.startswith(GPU)]


def start(continuation=False):
    for name in ['input', 'output', 'temp', 'user', 'logs', 'configs', 'processes']:
        RUN.joinpath(name).mkdir(parents=True, exist_ok=True)
    lock = RUN.joinpath('processes/gpu.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    occupied = gpu_processes()
    if occupied:
        raise RuntimeError('Selected GPU has active compute processes: ' + repr(occupied))
    probe = socket.socket()
    try:
        probe.bind(('127.0.0.1', PORT))
    finally:
        probe.close()
    memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    available_kib = int(memory['MemAvailable'].split()[0])
    if available_kib < 20 * 1024 * 1024:
        raise RuntimeError('Host RAM headroom below 20 GiB; do not start')
    command = [PYTHON, '-u', str(COMFY / 'main.py'),
               '--listen', '127.0.0.1', '--port', str(PORT),
               '--disable-all-custom-nodes', '--disable-auto-launch',
               '--highvram', '--disable-pinned-memory',
               '--use-pytorch-cross-attention', '--preview-method', 'none',
               '--cache-none', '--reserve-vram', '4',
               '--input-directory', str(RUN / 'input'),
               '--output-directory', str(RUN / 'output'),
               '--temp-directory', str(RUN / 'temp'),
               '--user-directory', str(RUN / 'user'),
               '--database-url', 'sqlite:///' + str(RUN / 'pilot.db')]
    if continuation:
        command += ['--base-directory', str(RUN),
                    '--models-directory', str(COMFY / 'models'),
                    '--whitelist-custom-nodes', 'H3MotionContextOfficial', 'HermesH3Continuation']
    env = os.environ.copy()
    env.update(CUDA_VISIBLE_DEVICES=GPU, OMP_NUM_THREADS='8', MKL_NUM_THREADS='8',
               OPENBLAS_NUM_THREADS='8', TOKENIZERS_PARALLELISM='false',
               PYTHONUNBUFFERED='1', LC_ALL='C', LANG='C')
    registry = RUN / 'processes/service.json'
    if registry.exists():
        previous = json.loads(registry.read_text())
        RUN.joinpath(f"processes/service_{previous['pid']}.json").write_text(json.dumps(previous, indent=2))
    with RUN.joinpath('logs/comfyui.log').open('ab', buffering=0) as log:
        process = subprocess.Popen(command, cwd=str(COMFY), env=env,
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   start_new_session=True, pass_fds=(lock.fileno(),))
    time.sleep(0.2)
    record = {'pid': process.pid, 'gpu_uuid': GPU, 'port': PORT,
              'started_unix': time.time(), 'command': command,
              'identity': identity(process.pid), 'host_available_kib': available_kib}
    registry.write_text(json.dumps(record, indent=2))
    RUN.joinpath(f'processes/service_{process.pid}.json').write_text(json.dumps(record, indent=2))
    print(json.dumps(record))


def stop():
    path = RUN / 'processes/service.json'
    record = json.loads(path.read_text())
    pid = record['pid']
    if Path('/proc', str(pid)).exists():
        current = identity(pid)
        if current != record['identity'] or current['uid'] != os.getuid():
            raise RuntimeError('Process identity mismatch; refusing to signal')
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            if not Path('/proc', str(pid)).exists():
                break
            time.sleep(1)
        else:
            if identity(pid) == current:
                os.kill(pid, signal.SIGKILL)
    time.sleep(2)
    remaining = gpu_processes()
    record.update(stopped_unix=time.time(), remaining_gpu_processes=remaining)
    RUN.joinpath('processes/cleanup.json').write_text(json.dumps(record, indent=2))
    RUN.joinpath(f'processes/cleanup_{pid}.json').write_text(json.dumps(record, indent=2))
    print(json.dumps({'pid': pid, 'remaining_gpu_processes': remaining}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'stop'])
    parser.add_argument('--continuation', action='store_true')
    args = parser.parse_args()
    start(continuation=args.continuation) if args.action == 'start' else stop()
