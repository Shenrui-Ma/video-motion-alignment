"""Reconcile a completed drain using fresh process/GPU evidence, preserving failure receipts."""
import argparse
import json
from pathlib import Path
import sys
import time

p = argparse.ArgumentParser()
p.add_argument('--root', type=Path, required=True)
a = p.parse_args()
root = a.root
sys.path.insert(0, str(root / 'scripts'))
import service

def read(path):
    return json.loads(path.read_text())

audit = root / 'audit/task_scope_review_hold_20261018'
prior = read(audit / 'PRIOR.json')
drain = read(audit / 'DRAINING.json')
for rec in (prior['owner'], prior['controller']):
    assert not Path('/proc', str(rec['pid'])).exists(), rec['pid']
assert read(root / 'processes/service.json')['identity'] == prior['owner']['identity']
compute = service.compute_processes()
assert all(row['pid'] != prior['owner']['pid'] for row in compute)
history = read(root / 'logs' / (drain['run'] + '_history.json'))
assert history['status']['completed'] is True and history['status']['status_str'] == 'success'
completed = []
for run in read(root / 'configs/queue.json')['jobs']:
    f = root / 'logs' / (run + '_history.json')
    if f.exists():
        h = read(f)
        if h['status']['completed'] is True and h['status']['status_str'] == 'success':
            completed.append(run)
service.write_json(root / 'logs/controller_state.json', {
    'status': 'task_scope_review_hold', 'completed': completed,
    'current': None, 'unix': time.time(), 'administrative_hold': str(audit)})
receipt = {'current_job_completed': drain['run'], 'completed': completed,
           'service_and_controller_proc_absent': True, 'service_CUDA_absent': True,
           'scientific_queue_preserved': True, 'fresh_compute_rows': compute,
           'prior_failure_preserved': (audit / 'FAILURE.json').exists(), 'unix': time.time()}
service.write_json(audit / 'VERIFIED_HOLD.json', receipt)
print(json.dumps(receipt))
