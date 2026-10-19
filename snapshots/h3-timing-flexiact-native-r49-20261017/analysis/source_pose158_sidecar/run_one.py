"""Single source CPU extraction driver, with both shared resource locks."""
import argparse
import fcntl
import json
from pathlib import Path
import shlex
import subprocess
import time
from remote_one import sha, read, save, require

HERE = Path(__file__).resolve().parent
PYTHON = '/home/researcher/miniconda3/envs/comfyui/bin/python'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-o', 'ServerAliveInterval=20', '-o', 'ServerAliveCountMax=3']
HOST = 'H3_SERVER_A'
CPU = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')


def execute(source):
    p = read(HERE / 'PROTOCOL.json')
    require(source in p['sources'], 'five fixed sources')
    require(not (HERE / source).exists(), 'existing local result requires review')
    freeze = read(HERE / 'FREEZE.json')
    for rel, digest in freeze['files'].items():
        require(sha(HERE / rel) == digest, 'sealed sidecar changed')
    with CPU.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'status': 'busy', 'scope': 'Mac CPU', 'source_id': source}
        remote = p['root_remote'] + '/analysis/source_pose158_sidecar'
        temp = p['root_remote'] + '/temp'
        subprocess.run(SSH + [HOST, 'mkdir -p ' + shlex.quote(remote) + ' ' + shlex.quote(temp)], check=True, timeout=30)
        paths = [str(HERE / f) for f in freeze['files']] + [str(HERE / 'FREEZE.json')]
        subprocess.run(['rsync', '-a', '-e', shlex.join(SSH), *paths, HOST + ':' + remote + '/'], check=True, timeout=60)
        command = SSH + [HOST, shlex.join(['env', 'CUDA_VISIBLE_DEVICES=', 'TMPDIR=' + temp, 'TMP=' + temp, 'TEMP=' + temp, 'PYTHONDONTWRITEBYTECODE=1', 'OMP_NUM_THREADS=4', 'MKL_NUM_THREADS=4', 'OPENBLAS_NUM_THREADS=4', 'NUMEXPR_NUM_THREADS=4', PYTHON, remote + '/remote_one.py', '--source', source])]
        audit = HERE / 'audit'
        audit.mkdir(exist_ok=True)
        stamp = str(time.time_ns())
        save(audit / (stamp + '.command.json'), {'source_id': source, 'command': command, 'code_freeze_sha256': sha(HERE / 'FREEZE.json'), 'time': time.time()})
        proc = subprocess.run(command, capture_output=True, text=True, timeout=300)
        (audit / (stamp + '.log')).write_text(proc.stdout + '\nSTDERR\n' + proc.stderr)
        if proc.returncode == 75:
            return {'status': 'busy', 'scope': 'server CPU/online priority', 'source_id': source}
        require(proc.returncode == 0, 'source extraction failed; retain remote phase and command audit')
        subprocess.run(['rsync', '-a', '-e', shlex.join(SSH), HOST + ':' + remote + '/' + source, str(HERE) + '/'], check=True, timeout=120)
        folder = HERE / source
        complete = read(folder / 'COMPLETE.json')
        require(complete['status'] == 'complete' and complete['source_id'] == source and complete['code_freeze_sha256'] == sha(HERE / 'FREEZE.json'), 'completion identity')
        require({x.name for x in folder.iterdir()} == set(complete['files']) | {'COMPLETE.json'}, 'exact output inventory')
        for rel, digest in complete['files'].items():
            require(sha(folder / rel) == digest, 'download identity')
        return {'status': 'complete', 'source_id': source, 'provenance': read(folder / 'PROVENANCE.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.source), allow_nan=False))
