"""Bounded sequential CPU intake; producer scheduling and GPU work stay external."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
import common

PRODUCER = Path('/data5/researcher/h3_runs/timing_ivebench_expanded_r73_20261018')
SOURCES = ('short_0252', 'short_0344', 'short_0065', 'short_0135', 'short_0035')
os.environ['PYTHONPATH'] = '/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps'


def complete(source):
    for arm in ('native', 'forced'):
        run = f'r73_{source}_seed2026101701_{arm}'
        job = PRODUCER / 'logs' / (run + '_job.json')
        if not job.exists():
            return False
        status = common.read(job)['status']
        if status in ('error', 'submission_uncertain', 'unknown_missing'):
            raise RuntimeError(f'{run}: actual producer status {status}')
        if status != 'success':
            return False
        history = common.read(PRODUCER / 'logs' / (run + '_history.json'))
        common.require(history['status']['completed'] is True and history['status']['status_str'] == 'success', 'job/history mismatch')
    return True


def locked(fn):
    deadline = time.monotonic() + 600
    while True:
        try:
            with common.cpu_lock():
                return fn()
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise TimeoutError('existing CPU consumer lock remained busy')
            time.sleep(10)


def execute(source):
    from collect_pair import collect, validate_gate
    from prepare_pair import prepare
    gate = PRODUCER / 'analysis/postrun' / source / 'PAIR_RUNTIME_GATE.json'
    def verify_and_collect():
        if not gate.exists():
            with (HERE / (source + '_verify.log')).open('x') as handle:
                subprocess.run([sys.executable, str(PRODUCER / 'analysis/postrun/verify_pair.py'), '--source', source], cwd=PRODUCER, stdout=handle, stderr=subprocess.STDOUT, check=True, timeout=1200)
        validate_gate(common.read(gate), source)
        collection = ROOT / 'incoming' / source / 'COLLECTION.json'
        if not collection.exists():
            collect(PRODUCER, source)
        else:
            for name, digest in common.read(collection)['files'].items():
                common.require(common.sha(collection.parent / name) == digest, 'existing intake changed')
    locked(verify_and_collect)
    ready = ROOT / 'prepared' / source / 'READY.json'
    if not ready.exists():
        locked(lambda: prepare(source, 'ffmpeg', 'ffprobe'))
    result = common.read(ready)
    common.require(result['passed'] is True and result['source'] == source and result['tracker_started'] is False, 'invalid READY')
    print(json.dumps({'event': 'METRIC_INPUTS_READY', 'source': source, 'gate': common.bound(gate), 'ready': common.bound(ready), 'valid_frames': result['valid_frames'], 'total_frames': result['total_frames'], 'unix': time.time()}), flush=True)


if __name__ == '__main__':
    common.verify_runtime()
    deadline = time.monotonic() + 12 * 3600
    for source in SOURCES:
        print(json.dumps({'event': 'WAITING_FOR_ACTUAL_PAIR', 'source': source, 'pid': os.getpid(), 'CUDA_started': False}), flush=True)
        while not complete(source):
            if time.monotonic() > deadline:
                raise TimeoutError('bounded twelve-hour actual pair wait expired')
            time.sleep(20)
        execute(source)
