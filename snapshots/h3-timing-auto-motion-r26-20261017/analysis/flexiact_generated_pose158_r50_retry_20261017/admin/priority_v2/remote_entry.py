"""Apply exact terminal-generation priority checks to the frozen pose extractor."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from priority import pending

HERE = Path(__file__).resolve().parent
SIDE = HERE.parent.parent
sys.path.insert(0, str(SIDE))
import remote_one

original_helper = remote_one.source_helper

def helper_with_priority(protocol):
    helper = original_helper(protocol)
    helper.online_pending = lambda current: pending(current['online_priority_roots'])
    return helper


def main():
    protocol = remote_one.read(SIDE / 'PROTOCOL.json')
    remote_one.check_freeze(protocol)
    revision = json.loads((HERE / 'REVISION.json').read_text())
    for filename, digest in revision['files'].items():
        if hashlib.sha256((HERE / filename).read_bytes()).hexdigest() != digest:
            raise ValueError('administrative wrapper changed: ' + filename)
    remote_one.source_helper = helper_with_priority
    p = argparse.ArgumentParser()
    for key in ('source', 'method', 'metric-inputs', 'mapping'):
        p.add_argument('--' + key, required=True)
    a = p.parse_args()
    try:
        result = remote_one.execute(a.source, a.method, a.metric_inputs, a.mapping)
    except BlockingIOError:
        print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY'); raise SystemExit(75)
    print(json.dumps(result, allow_nan=False))

if __name__ == '__main__': main()
