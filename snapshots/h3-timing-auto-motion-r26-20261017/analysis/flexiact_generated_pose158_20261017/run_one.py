"""One source/method CPU transaction. No polling loop or implicit retries."""
import argparse
import fcntl
import shlex
import subprocess
import time
from contract import *

SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-o', 'ServerAliveInterval=20', '-o', 'ServerAliveCountMax=3']
HOST = 'H3_SERVER_A'
PYTHON = '/home/researcher/miniconda3/envs/comfyui/bin/python'
CPU = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')


def execute(source, method, metric, mapping):
    protocol = read(HERE / 'PROTOCOL.json')
    require(source in protocol['source_order'] and method in protocol['methods'], 'fixed ten cases')
    freeze = check_freeze(protocol)
    dest = HERE / 'records' / (method + '_' + source)
    require(not dest.exists(), 'existing output requires review')
    with CPU.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'status': 'busy', 'source_id': source, 'method': method, 'scope': 'Mac CPU'}
        remote = protocol['root_remote']
        temp = remote + '/temp'
        subprocess.run(SSH + [HOST, 'mkdir -p ' + shlex.quote(remote) + ' ' + shlex.quote(temp)], check=True, timeout=30)
        files = [str(HERE / name) for name in freeze['files']] + [str(HERE / 'FREEZE.json')]
        subprocess.run(['rsync', '-a', '-e', shlex.join(SSH), *files, HOST + ':' + remote + '/'], check=True, timeout=60)
        command = SSH + [HOST, shlex.join(['env', 'CUDA_VISIBLE_DEVICES=', 'TMPDIR=' + temp, 'TMP=' + temp, 'TEMP=' + temp, 'PYTHONDONTWRITEBYTECODE=1', 'OMP_NUM_THREADS=4', 'OPENBLAS_NUM_THREADS=4', 'MKL_NUM_THREADS=4', 'NUMEXPR_NUM_THREADS=4', PYTHON, remote + '/remote_one.py', '--source', source, '--method', method, '--metric-inputs', metric, '--mapping', mapping])]
        audit = HERE / 'audit'
        audit.mkdir(exist_ok=True)
        stamp = str(time.time_ns())
        save(audit / (stamp + '.command.json'), {'command': command, 'code_freeze_sha256': sha(HERE / 'FREEZE.json'), 'time': time.time()})
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        (audit / (stamp + '.log')).write_text(result.stdout + '\nSTDERR\n' + result.stderr)
        if result.returncode == 75:
            return {'status': 'busy', 'source_id': source, 'method': method, 'scope': 'server CPU/online priority'}
        require(result.returncode == 0, 'remote technical failure; keep phase and audit')
        record = json.loads(result.stdout.splitlines()[-1])
        if record['status'] == 'pending':
            return record
        require(record['status'] == 'complete' and record['source_id'] == source and record['method'] == method and record['pair_id'] == protocol['pairs'][source]['pair_id'], 'actual response identity')
        dest.parent.mkdir(exist_ok=True)
        subprocess.run(['rsync', '-a', '-e', shlex.join(SSH), HOST + ':' + remote + '/records/' + method + '_' + source, str(dest.parent) + '/'], check=True, timeout=120)
        from manifest import verified_record
        verified_record(protocol, source, method)
        return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--method', required=True)
    parser.add_argument('--metric-inputs', required=True)
    parser.add_argument('--mapping', required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.source, args.method, args.metric_inputs, args.mapping), allow_nan=False))
