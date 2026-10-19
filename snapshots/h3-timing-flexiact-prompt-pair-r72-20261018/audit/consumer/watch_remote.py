"""Passive CPU postrun verifier; never starts a producer or changes admission."""
import argparse
import fcntl
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import subprocess
import sys
import time
from common import *
from collect import collect

def once():
    rows = []
    for pair in PAIRS:
        status = readiness(ROOT, pair)
        if status in ('READY', 'PASSED'):
            try:
                with open(CPU_LOCK, 'a') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    status = readiness(ROOT, pair)
                    if status == 'READY':
                        started = time.monotonic()
                        log = HERE / (pair + '_VERIFY.log')
                        with log.open('a') as stream:
                            result = subprocess.run([sys.executable, str(ROOT / 'analysis/postrun/verify_pair.py'), '--source', pair], cwd=ROOT, env=os.environ.copy(), stdout=stream, stderr=subprocess.STDOUT, timeout=1800)
                        save(HERE / (pair + '_VERIFY_EFFICIENCY.json'), {'source_id': pair, 'wall_seconds': time.monotonic() - started, 'returncode': result.returncode, 'log': str(log), 'unix': time.time(), 'gpu_started': False})
                        require(result.returncode == 0, 'actual verifier failed; see ' + str(log))
                        status = readiness(ROOT, pair)
                        require(status == 'PASSED', 'verifier returned without passed gate')
                    if status == 'PASSED':
                        collect(pair)
            except BlockingIOError:
                status = 'CPU_BUSY'
        rows.append({'source_id': pair, 'status': status, 'collected': (HERE / 'incoming' / pair / 'COLLECTION.json').exists()})
    value = {'schema': 'r72-consumer-watch-v1', 'unix': time.time(), 'rows': rows, 'all_collected': all(r['collected'] and r['status'] == 'PASSED' for r in rows), 'gpu_started': False}
    save(HERE / 'REMOTE_PROGRESS.json', value)
    return value

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--watch-hours', type=float, default=0)
    a = p.parse_args()
    require(0 <= a.watch_hours <= 12, 'watch bounded to 12 hours')
    with (HERE / 'remote_watcher.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        save(HERE / 'REMOTE_PROCESS.json', {'pid': os.getpid(), 'proc_stat': Path('/proc/self/stat').read_text(), 'argv': sys.argv, 'started_unix': time.time(), 'CUDA_VISIBLE_DEVICES': os.environ['CUDA_VISIBLE_DEVICES']})
        deadline = time.monotonic() + 3600 * a.watch_hours
        previous = None
        while True:
            value = once()
            compact = json.dumps(value['rows'], sort_keys=True)
            if compact != previous:
                print(json.dumps(value), flush=True)
                previous = compact
            if value['all_collected'] or time.monotonic() >= deadline:
                break
            time.sleep(30)

if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        save(HERE / 'REMOTE_FAILURE.json', {'unix': time.time(), 'error': repr(error), 'type': type(error).__name__})
        raise
