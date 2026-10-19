"""Run the frozen physical-time evaluator under existing observer priority."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import runpy
import sys
from priority import pending

HERE = Path(__file__).resolve().parent
SIDE = HERE.parent.parent
BASE = Path('/data5/researcher/h3_runs')
RUN = BASE / 'flexiact_physical_time_run_r50_retry_20261017'
FROZEN = '1da583cfb2c8d391f460fd1a76bd304e751e7ffde08990ef9ed31fc5efc935bb'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(); p.add_argument('--source', required=True)
    a = p.parse_args()
    protocol = json.loads((SIDE / 'PROTOCOL.json').read_text())
    if a.source not in protocol['source_order']:
        raise ValueError('Source outside fixed five')
    seal = json.loads((HERE / 'PHYSICAL_FREEZE.json').read_text())
    for filename, digest in seal['files'].items():
        if sha(HERE / filename) != digest: raise ValueError('Physical administrative entry changed')
    if sha(RUN / 'FREEZE.json') != FROZEN: raise ValueError('Frozen physical runner differs')
    for filename, digest in json.loads((RUN / 'FREEZE.json').read_text())['files'].items():
        if sha(RUN / filename) != digest: raise ValueError('Frozen physical code differs: ' + filename)
    if pending(protocol['online_priority_roots']): raise BlockingIOError('Online observer priority')
    with (BASE / 'timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if pending(protocol['online_priority_roots']): raise BlockingIOError('Online observer priority')
        source = BASE / 'timing_flexiact_native_r49_20261017/analysis/source_pose158_sidecar'
        sys.argv = [str(RUN / 'run_pair.py'),
                    '--generated-manifest', str(SIDE / 'MANIFEST.json'),
                    '--source-manifest', str(source / 'MANIFEST.json'),
                    '--source-protocol', str(source / 'PROTOCOL.json'),
                    '--numeric-root', str(BASE / 'flexiact_physical_time_eval_20261017'),
                    '--metric-root', str(BASE / 'flexiact_official_metric_20261017'),
                    '--pair', 'human/' + a.source + '/000',
                    '--output', str(HERE / 'results' / (a.source + '.json'))]
        runpy.run_path(sys.argv[0], run_name='__main__')

if __name__ == '__main__':
    try: main()
    except BlockingIOError:
        print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY'); raise SystemExit(75)
