"""Incrementally copy this experiment's artifacts; never touch other runs."""
import argparse
import json
import subprocess
import time
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
REMOTE = 'researcher@192.0.2.1:/data3/researcher/h3_runs/short_event_switching_20261013'


def collect(full=False):
    paths = [('output', 'outputs'), ('logs', 'logs'), ('configs', 'remote_configs'),
             ('processes', 'processes/remote')]
    if full:
        paths += [('audit', 'audit'), ('scripts', 'remote_scripts')]
    else:
        paths += [('audit', 'audit')]
    results = []
    for source, destination in paths:
        target = LAB / destination
        target.mkdir(parents=True, exist_ok=True)
        argv = ['rsync', '-az', '--partial', '--exclude=*.tmp', '-e', 'ssh -o BatchMode=yes -o ConnectTimeout=12']
        if source == 'configs':
            argv += ['--exclude=*.tar.gz']
        if source == 'audit' and not full:
            argv += ['--exclude=*.pt', '--exclude=tensor_blobs']
        argv += [REMOTE + '/' + source + '/', str(target) + '/']
        result = subprocess.run(argv, capture_output=True, text=True)
        results.append({'source': source, 'destination': destination, 'returncode': result.returncode,
                        'stderr': result.stderr[-1500:]})
        if result.returncode:
            raise RuntimeError(json.dumps(results))
    (LAB / 'logs/last_collection.json').write_text(json.dumps({'unix': time.time(), 'full': full, 'results': results}, indent=2))
    print(json.dumps({'collected': len(results), 'full': full}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true')
    collect(parser.parse_args().full)
