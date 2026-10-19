"""Register an exact temporary GPU2 process before running a root-owned gate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import time

ROOT = Path('/data5/researcher/h3_runs/timing_auto_fresh_r28_20261017')
p = argparse.ArgumentParser()
p.add_argument('--kind', choices=['kernel', 'allocator'], required=True)
a = p.parse_args()
target = ROOT/('scripts/gpu_dynamic_union_smoke.py' if a.kind=='kernel' else 'audit/root_allocator_profile.py')
audit = ROOT/'audit'
ready = audit/('root_'+a.kind+'_ready.json')
go = audit/('root_'+a.kind+'_go.json')
assert not ready.exists() and not go.exists()
proc = Path('/proc')/str(os.getpid())
identity = {'uid':proc.stat().st_uid, 'start_ticks':proc.joinpath('stat').read_text().split(') ',1)[1].split()[19],
            'cmdline_sha256':hashlib.sha256(proc.joinpath('cmdline').read_bytes()).hexdigest()}
record = {'pid':os.getpid(), 'identity':identity, 'script_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
          'target':str(target), 'kind':a.kind, 'unix':time.time()}
ready.write_text(json.dumps(record,indent=2)+'\n')
deadline = time.monotonic()+120
while not go.exists():
    if time.monotonic()>=deadline:raise TimeoutError('root peer admission was not provided')
    time.sleep(.1)
assert json.loads(go.read_text())==record
assert hashlib.sha256(target.read_bytes()).hexdigest()==record['script_sha256']
sys.argv = [str(target)]
if a.kind=='kernel':sys.argv += ['--root-admitted','--output',str(audit/'gpu_dynamic_union_gate.json')]
runpy.run_path(str(target),run_name='__main__')
