"""Scheduling revision around unchanged frozen consumer code."""
import argparse
from pathlib import Path
import runpy
import sys
from priority import pending

HERE = Path(__file__).resolve().parent
POSTRUN = HERE.parent.parent
sys.path.insert(0, str(POSTRUN))
import remote_consume

parser = argparse.ArgumentParser()
parser.add_argument('--entry', choices=['incremental', 'identity'], required=True)
args, remainder = parser.parse_known_args()
remote_consume.online_pending = lambda: pending(remote_consume.P['online_priority_roots'])
target = POSTRUN / ('incremental_case.py' if args.entry == 'incremental' else 'audit/run_identity_pair.py')
sys.argv = [str(target)] + remainder
try:
    runpy.run_path(str(target), run_name='__main__')
except BlockingIOError:
    print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY')
    raise SystemExit(75)
