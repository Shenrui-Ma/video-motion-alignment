"""Apply the same terminal-generation scheduling rule to frozen pose extraction."""
import argparse
import json
import sys
from priority import pending

sys.path.insert(0, '/data5/researcher/h3_runs/timing_auto_motion_r26_20261017/analysis/flexiact_generated_pose158_r50_retry_20261017')
import remote_one

original_helper = remote_one.source_helper


def source_helper(protocol):
    helper = original_helper(protocol)
    helper.online_pending = lambda current: pending(current['online_priority_roots'])
    return helper


remote_one.source_helper = source_helper
parser = argparse.ArgumentParser()
parser.add_argument('--source', required=True)
parser.add_argument('--metric-inputs', required=True)
parser.add_argument('--mapping', required=True)
args = parser.parse_args()
try:
    print(json.dumps(remote_one.execute(args.source, 'automatic', args.metric_inputs, args.mapping), allow_nan=False))
except BlockingIOError:
    print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY')
    raise SystemExit(75)
