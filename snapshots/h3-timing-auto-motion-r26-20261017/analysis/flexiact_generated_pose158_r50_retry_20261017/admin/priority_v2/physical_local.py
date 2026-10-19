"""One CPU-only actual pair evaluation, preserving frozen numeric implementation."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
SIDE = HERE.parent.parent
SSH = ['ssh', '-J', 'H3_SERVER_B', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15']
REMOTE = '/data5/researcher/h3_runs/timing_auto_motion_r26_20261017/analysis/flexiact_generated_pose158_r50_retry_20261017'
PYTHON = '/home/researcher/miniconda3/envs/comfyui/bin/python'


def main():
    p = argparse.ArgumentParser(); p.add_argument('--source', required=True)
    a = p.parse_args()
    protocol = json.loads((SIDE / 'PROTOCOL.json').read_text())
    if a.source not in protocol['source_order']: raise ValueError('Source outside fixed five')
    with Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('BUSY_MAC'); return
        subprocess.run([sys.executable, str(SIDE / 'manifest.py')], check=True, timeout=30)
        subprocess.run(['rsync', '-a', '-e', shlex.join(SSH), str(SIDE / 'MANIFEST.json'),
                        'H3_SERVER_A:' + REMOTE + '/MANIFEST.json'], check=True, timeout=40)
        command = SSH + ['H3_SERVER_A', shlex.join(['env', 'CUDA_VISIBLE_DEVICES=', 'OMP_NUM_THREADS=2',
                   'MKL_NUM_THREADS=2', 'OPENBLAS_NUM_THREADS=2', 'PYTHONDONTWRITEBYTECODE=1',
                   PYTHON, REMOTE + '/admin/priority_v2/physical_remote.py', '--source', a.source])]
        stamp = str(time.time_ns())
        (HERE / (stamp + '.command.json')).write_text(json.dumps({'command': command}, indent=2) + '\n')
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        (HERE / (stamp + '.log')).write_text(result.stdout + '\nSTDERR\n' + result.stderr)
        if result.returncode == 75:
            print('BUSY_SERVER_OR_ONLINE'); return
        if result.returncode:
            print(result.stdout, result.stderr); raise SystemExit(result.returncode)
        destination = HERE / 'results'; destination.mkdir(exist_ok=True)
        subprocess.run(['rsync', '-a', '-e', shlex.join(SSH), 'H3_SERVER_A:' + REMOTE + '/admin/priority_v2/results/' + a.source + '.json',
                        str(destination) + '/'], check=True, timeout=40)
        print(result.stdout)

if __name__ == '__main__': main()
