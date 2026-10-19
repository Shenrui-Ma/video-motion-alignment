"""Release the exact R54 service after the five-case archive has passed."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys

ROOT = Path('/data3/researcher/h3_runs/timing_ivebench_native_r54_20261017')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def main(expected_sha):
    archive = ROOT / 'analysis/postrun/captured/batch'
    gate_path = archive / 'RUN_GATE.json'
    assert sha(gate_path) == expected_sha
    gate = read(gate_path)
    owner = read(ROOT / 'processes/service.json')
    assert gate['passed'] is True and gate['owner'] == owner
    assert gate['runtime_gate_sha256'] == sha(archive / 'RUNTIME_GATE.json')
    runtime = read(archive / 'RUNTIME_GATE.json')
    assert runtime['passed'] is True and all(runtime['checks'].values())
    assert sha(archive / 'deploy_manifest.json') == sha(ROOT / 'deploy_manifest.json')
    assert gate['file_inventory_sha256'] == sha(archive / 'FILE_INVENTORY.json')
    expected_runs = ['r54_short_' + case + '_seed2026101701_native'
                     for case in ('0210', '0230', '0263', '0352', '0370')]
    assert gate['runs'] == expected_runs
    assert set(runtime['runs']) == set(expected_runs)
    assert owner['pid'] == 29486
    assert owner['identity']['uid'] == os.getuid() == 1004
    assert str(owner['identity']['start_ticks']) == '333608'
    proc = Path('/proc/29486')
    if proc.exists():
        assert sha(proc / 'cmdline') == '46a3ab4b0884177c02eb3f1a793fb725fb5b48a5ab5134550e9b6fffdc6a3e17'
    sys.path[:0] = [str(ROOT / 'scripts'), '/data3/researcher/h3_runs/closure_tutorials_53592/01-anime/runtime_deps']
    import service
    queue = service.queue_at(service.PORT)
    assert not queue['queue_running'] and not queue['queue_pending']
    service.stop(expected_record=owner)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-gate-sha', required=True)
    main(parser.parse_args().run_gate_sha)
