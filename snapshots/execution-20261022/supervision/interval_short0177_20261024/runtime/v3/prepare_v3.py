"""Materialize a fresh package after the verified queue progress-binding failure."""
from pathlib import Path
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'v2/package'
NEW = HERE / 'package'
OLD_REMOTE = '/data4/research-user/h3_runs/interval_short0177_20261024_v2'
NEW_REMOTE = '/data4/research-user/h3_runs/interval_short0177_20261024_v3'
assert not NEW.exists(), 'Preserve any already prepared package'
shutil.copytree(OLD, NEW, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'PACKAGE_SHA256.json'))
for file in NEW.rglob('*'):
    if file.is_file() and file.suffix in ('.py', '.json'):
        file.write_text(file.read_text().replace(OLD_REMOTE, NEW_REMOTE))

for gpu in (5, 6, 7):
    lane = NEW / f'gpu{gpu}'
    cfg = json.loads((lane / 'CONFIG.json').read_text())
    cfg['schema'] = 'interval-short0177-v3'
    cfg['min_cgroup_headroom_gib'] = 40
    (lane / 'CONFIG.json').write_text(json.dumps(cfg, indent=2))
    for file in [lane / 'jobs.json', *(lane / 'manifests').glob('*.json')]:
        data = json.loads(file.read_text())
        for job in data['jobs']:
            job['progress_file'] = cfg['root'] + '/audit/router/' + job['id'] + '__a1.json'
        file.write_text(json.dumps(data, indent=2))
    worker = lane / 'scripts/single_attempt_worker.py'
    text = worker.read_text()
    assert text.count("'--stall-timeout','900'") == 1
    worker.write_text(text.replace("'--stall-timeout','900'", "'--stall-timeout','1800'"))
    # Code that changes tensors or the diffusion process stays byte-identical.
    for relative in ['queue/durable_comfy_queue.py', 'custom_nodes/H3Study/core.py',
                     'custom_nodes/H3Study/schedule.py', 'custom_nodes/H3Study/layout.py',
                     'scripts/int8_row_chunking.py', 'scripts/compatibility_bootstrap.py']:
        assert (lane / relative).read_bytes() == (OLD / f'gpu{gpu}' / relative).read_bytes(), relative

print(json.dumps({'package': str(NEW), 'remote_root': NEW_REMOTE,
                  'change': 'Fresh directory; bind existing progress_file; 1800s stall and 7200s total; scientific code unchanged'}))
