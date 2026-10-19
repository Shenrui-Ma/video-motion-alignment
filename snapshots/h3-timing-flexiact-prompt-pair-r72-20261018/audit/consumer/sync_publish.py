"""Passive transfer and local rendering; remote producer ownership stays with root."""
import argparse
import fcntl
import os
import subprocess
import sys
import time
from common import *
from collect import verify_collection
from presentation import render, document

def transfer(command, timeout):
    for attempt in range(3):
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return result
        if result.returncode not in (12, 23, 30, 35, 255) or attempt == 2:
            raise RuntimeError('transfer failed: ' + result.stderr[-3000:])
        time.sleep(20)

def once():
    (HERE / 'incoming').mkdir(exist_ok=True)
    transfer(['rsync', '-a', '--exclude=*.pt', '--exclude=*.npz', '--exclude=*.collecting.*', HOST + ':' + REMOTE + '/audit/consumer/incoming/', str(HERE / 'incoming') + '/'], 600)
    transfer(['scp', '-q', '-o', 'ConnectTimeout=10', HOST + ':' + REMOTE + '/audit/consumer/REMOTE_PROGRESS.json', str(HERE / 'REMOTE_PROGRESS.json')], 45)
    remote = read(HERE / 'REMOTE_PROGRESS.json')
    completed = []
    for pair in PAIRS:
        intake = HERE / 'incoming' / pair
        if not (intake / 'COLLECTION.json').exists():
            continue
        verify_collection(intake, pair)
        render(pair)
        completed.append(pair)
    delivered = None
    if completed:
        delivered = document()
    value = {'schema': 'r72-local-consumer-progress-v1', 'unix': time.time(), 'completed_pairs': completed, 'remote': remote, 'html': delivered['html'] if delivered else None, 'gpu_started': False}
    save(HERE / 'LOCAL_PROGRESS.json', value)
    return value

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--watch-hours', type=float, default=0)
    a = p.parse_args()
    require(0 <= a.watch_hours <= 12, 'watch bounded to 12 hours')
    with (HERE / 'local_watcher.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        save(HERE / 'LOCAL_PROCESS.json', {'pid': os.getpid(), 'argv': sys.argv, 'started_unix': time.time()})
        deadline = time.monotonic() + 3600 * a.watch_hours
        previous = None
        while True:
            value = once()
            current = json.dumps({'complete': value['completed_pairs'], 'remote': value['remote']['rows']}, sort_keys=True)
            if current != previous:
                print(current, flush=True)
                previous = current
            if len(value['completed_pairs']) == len(PAIRS) or time.monotonic() >= deadline:
                break
            time.sleep(30)

if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        save(HERE / 'LOCAL_FAILURE.json', {'unix': time.time(), 'error': repr(error), 'type': type(error).__name__})
        raise
