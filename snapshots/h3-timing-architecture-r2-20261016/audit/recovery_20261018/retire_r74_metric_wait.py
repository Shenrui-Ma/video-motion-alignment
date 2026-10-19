"""Retire the exact R74 CPU waiter after task-scope review; no GPU work admitted."""
import json
import os
from pathlib import Path
import signal
import time

pid = 791426
root = Path('/data3/researcher/h3_runs/flexiact_official_six_metrics_r74_20261018')
expected = ['/data3/researcher/ComfyUI/.venv/bin/python', '-u', str(root / 'audit/root_finish_metrics.py')]

def identity():
    p = Path('/proc') / str(pid)
    if not p.exists():
        return None
    args = p.joinpath('cmdline').read_bytes().rstrip(b'\0').decode().split('\0')
    start = p.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19]
    return {'args': args, 'start_ticks': start, 'uid': p.stat().st_uid}

before = identity()
assert before and before['args'] == expected and before['uid'] == os.getuid(), before
children = Path(f'/proc/{pid}/task/{pid}/children').read_text().strip()
assert not children, children
assert identity() == before
os.kill(pid, signal.SIGTERM)
deadline = time.monotonic() + 30
while identity() is not None and time.monotonic() < deadline:
    time.sleep(.2)
assert identity() is None
receipt = {'pid': pid, 'identity': before, 'process_absent': True,
           'children_before': children, 'reason': 'R74 remaining queue held for task-scope review',
           'unix': time.time()}
out = root / 'audit/ROOT_METRIC_WAITER_RETIRED_TASK_REVIEW.json'
assert not out.exists()
out.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
