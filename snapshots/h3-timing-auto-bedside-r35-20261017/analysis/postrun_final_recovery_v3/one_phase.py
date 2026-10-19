"""One root-authorized recovery, shared old unique lock and CPU lock order."""
import argparse, fcntl, json, os, shlex, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'postrun'
sys.path.insert(0, str(OLD))
import consume as base
from contract import read, require, save, sha

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    if not args.execute:
        print('Prepared only.'); return 0
    require(not (HERE / 'LOCAL_FAILURE.json').exists(), 'uncertain previous recovery requires review')
    freeze = read(HERE / 'FREEZE.json'); p = read(HERE / 'PROTOCOL.json')
    for rel, digest in freeze['files'].items():
        require(sha(HERE / rel) == digest, 'changed recovery source: ' + rel)
    require(sha(OLD / 'FREEZE.json') == p['old_freeze_sha256'] and sha(OLD / 'BINDING.json') == p['old_binding_sha256'], 'old binding/seal changed')
    with (OLD / 'unique_consumer.lock').open('a') as unique:
        try: fcntl.flock(unique, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: print('BUSY unique driver'); return 75
        remote = p['root_remote'] + '/analysis/postrun_final_recovery_v3'
        subprocess.run(base.SSH + [base.HOST, 'mkdir -p ' + shlex.quote(remote)], check=True, timeout=30)
        files = [str(HERE / rel) for rel in freeze['files']] + [str(HERE / 'FREEZE.json')]
        subprocess.run(['rsync', '-a', '-e', shlex.join(base.SSH), *files, base.HOST + ':' + remote + '/'], check=True, timeout=60)
        with base.CPU.open('a') as cpu:
            try: fcntl.flock(cpu, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: print('BUSY Mac CPU'); return 75
            cmd = shlex.join(['timeout', '--signal=TERM', '600', 'env', 'CUDA_VISIBLE_DEVICES=', 'PYTHONDONTWRITEBYTECODE=1', 'OMP_NUM_THREADS=1', 'OPENBLAS_NUM_THREADS=1', 'MKL_NUM_THREADS=1', base.PYTHON, remote + '/recover.py', '--execute'])
            proc = subprocess.run(base.SSH + [base.HOST, cmd], capture_output=True, text=True, timeout=660)
            log = HERE / ('remote_' + str(time.time_ns()) + '.log'); log.write_text(proc.stdout + '\nSTDERR\n' + proc.stderr)
            if proc.returncode == 75:
                print('BUSY remote CPU/online pose'); return 75
            require(proc.returncode == 0, 'recovery failed; inspect ' + str(log))
            base.sync_download(p['run'])
            subprocess.run(['rsync', '-a', '-e', shlex.join(base.SSH), base.HOST + ':' + remote + '/RECOVERY_COMPLETE.json', str(HERE) + '/'], check=True, timeout=60)
            save(HERE / 'LOCAL_COMPLETE.json', {'status': 'complete', 'remote_receipt': read(HERE / 'RECOVERY_COMPLETE.json'), 'download_sha256': sha(OLD / (p['run'] + '_DOWNLOAD.json')), 'original_failure_retained': (OLD / 'CONSUMER_FAILURE.json').exists()})
            print(json.dumps(read(HERE / 'LOCAL_COMPLETE.json')))
    return 0

if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception as exc:
        save(HERE / 'LOCAL_FAILURE.json', {'error': repr(exc), 'automatic_retry': False, 'time': time.time()}); raise
