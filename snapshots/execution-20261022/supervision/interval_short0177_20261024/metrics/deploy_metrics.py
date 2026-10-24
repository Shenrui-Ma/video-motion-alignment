"""Upload one CPU-verified manifest and its exact seven videos; never launch scoring."""
import argparse
import hashlib
import json
import shlex
import subprocess
from pathlib import Path


def main(prepared):
    prepared = Path(prepared).resolve()
    config = json.loads((prepared / 'config.json').read_text())
    transfers = json.loads((prepared / 'transfers.json').read_text())
    if len(transfers) != 7 or not json.loads((prepared / 'PREPARED.json').read_text())['passed']:
        raise ValueError('Seven verified videos required')
    host, root = config['host'], config['remote_root']
    script = ('from pathlib import Path\n'
              f'r=Path({root!r})\n'
              'r.mkdir(exist_ok=False)\n'
              "(r/'code').mkdir()\n(r/'videos').mkdir()\n")
    subprocess.run(['ssh', '-o', 'BatchMode=yes', host, 'python3 -'], input=script, text=True, check=True)
    names = ['config.json', 'HOST81_READONLY.json', 'manifest.json', 'PREPARED.json',
             'metric_worker.py', 'durable_metrics.py', 'prepare_frames.py', 'run_metrics.py']
    for name in names:
        subprocess.run(['scp', str(prepared / name), host + ':' + root + '/code/' + name], check=True)
    for transfer in transfers:
        local = Path(transfer['local'])
        if hashlib.sha256(local.read_bytes()).hexdigest() != transfer['sha256']:
            raise ValueError('Local video changed after preparation')
        subprocess.run(['scp', str(local), host + ':' + transfer['remote']], check=True)
    python = config['shared_root'] + '/venv/bin/python'
    command = shlex.join([python, root + '/code/run_metrics.py'])
    subprocess.run(['ssh', '-o', 'BatchMode=yes', host, command], check=True)
    print('Uploaded and CPU-prepared seven videos; scoring has not started.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepared', required=True)
    main(parser.parse_args().prepared)
