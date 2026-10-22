"""Fixed four-task consumer bindings; no GPU work at import time."""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'runtime'
SELECTION = ROOT / 'configs/SELECTED_5_MANIFEST.json'
PAIRS = ('short_0230', 'short_0263', 'short_0352', 'short_0370')
METHODS = ('native', 'forced')

def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()

def read(path):
    return json.loads(Path(path).read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))

def require(condition, message):
    if not condition:
        raise ValueError(message)

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write('\n')

def bound(path):
    path = Path(path).resolve()
    return {'file': str(path), 'sha256': sha(path)}

def entry(source):
    require(source in PAIRS, 'unregistered source')
    selection = read(SELECTION)
    require(tuple(row['pair_id'] for row in selection['pairs']) == ('short_0210',) + PAIRS, 'fixed four sources differ')
    return next(row for row in selection['pairs'] if row['pair_id'] == source)

def verify_runtime():
    frozen = read(ROOT / 'configs/R63_RUNTIME_INHERITANCE.json')
    for relative, expected in frozen['files'].items():
        path = ROOT / relative
        require(path.is_file() and sha(path) == expected['sha256'] and path.stat().st_size == expected['bytes'], 'frozen R63 runtime differs: ' + relative)
    for relative, digest in read(ROOT / 'configs/producer_input_hashes.json').items():
        require(sha(ROOT / 'inputs' / relative) == digest, 'source input differs: ' + relative)
    if (ROOT / 'CONSUMER_FREEZE.json').exists():
        for relative, digest in read(ROOT / 'CONSUMER_FREEZE.json')['files'].items():
            require(sha(ROOT / relative) == digest, 'consumer source differs: ' + relative)
    return sha(ROOT / 'configs/R63_RUNTIME_INHERITANCE.json')

def checkpoint():
    paths = read(ROOT / 'configs/paths.json')
    suffix = 'remote41' if str(ROOT).startswith('/data3/') else 'remote9' if str(ROOT).startswith('/data5/') else 'local'
    return Path(paths['checkpoint_' + suffix])

@contextlib.contextmanager
def cpu_lock():
    if str(ROOT).startswith('/data3/'):
        path = Path('/data3/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
    elif str(ROOT).startswith('/data5/'):
        path = Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
    else:
        path = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield

def selection_hash():
    return sha(SELECTION)

def source_row(source):
    row = read(ROOT / 'prepared' / source / 'SOURCE_INPUTS.json')
    roles = {'source_original': ROOT / 'inputs' / (source + '_original.mp4'),
             'source_prepared_video': ROOT / 'inputs' / (source + '_video.mp4'),
             'source_preparation_record': ROOT / 'inputs' / (source + '_provenance.json'),
             'source_score_video': ROOT / 'prepared' / source / 'source_score.mp4'}
    for role, path in roles.items():
        require(sha(path) == row[role]['sha256'], 'portable source bytes changed: ' + role)
        row[role]['file'] = str(path.resolve())
    return row

def source_manifest(source):
    host_root = hashlib.sha256(str(ROOT.resolve()).encode()).hexdigest()[:12]
    path = ROOT / 'prepared' / source / ('SOURCE_INPUTS_HOST_' + host_root + '.json')
    row = source_row(source)
    if path.exists():
        require(read(path) == row, 'source host binding differs')
    else:
        save(path, row)
    return path
