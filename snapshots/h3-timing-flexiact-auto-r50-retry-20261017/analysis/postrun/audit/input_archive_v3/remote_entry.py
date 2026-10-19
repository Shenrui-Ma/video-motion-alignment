"""Preserve numerical consumers while adding parent-bound input inventory."""
import argparse
from pathlib import Path
import runpy
import sys
from source_inputs import install

HERE = Path(__file__).resolve().parent
POSTRUN = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / 'priority_v2'))
from priority import pending
sys.path.insert(0, str(POSTRUN))
import remote_consume

parser = argparse.ArgumentParser()
parser.add_argument('--entry', choices=['incremental', 'identity', 'recover'], required=True)
args, remainder = parser.parse_known_args()
remote_consume.online_pending = lambda: pending(remote_consume.P['online_priority_roots'])
install(remote_consume)
target = {'incremental': POSTRUN / 'incremental_case.py',
          'identity': POSTRUN / 'audit/run_identity_pair.py',
          'recover': HERE / 'recover_chest.py'}[args.entry]
sys.argv = [str(target)] + remainder
try:
    runpy.run_path(str(target), run_name='__main__')
except BlockingIOError:
    print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY')
    raise SystemExit(75)
