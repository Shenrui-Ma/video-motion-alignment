"""Five fixed FlexiAct cases with an exact Native-to-Auto graph transformation."""
import json
import hashlib
import shutil
from pathlib import Path
from prepare_graphs import derive

ROOT = Path(__file__).resolve().parents[1]
REMOTE = Path('/data5/researcher/h3_runs/timing_flexiact_auto_r50_20261017')
SOURCES = ('chest', 'crouch', 'fitness', 'one_leg', 'rotate')

def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def audit_dir(value):
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or path.resolve() != REMOTE / 'audit':
        raise ValueError('audit root outside frozen R50 root')
    return path.resolve()

audit_root = audit_dir

def cases(root=ROOT):
    rows = read(Path(root) / 'configs/protocol.json')['cases']
    if [x['source_id'] for x in rows] != list(SOURCES):
        raise ValueError('fixed five-case order changed')
    return rows

def validate_job(run, root=ROOT, inputs=True):
    root = Path(root)
    found = [x for x in cases(root) if x['run_id'] == run]
    if len(found) != 1:
        raise ValueError('run outside frozen registry')
    case = found[0]
    path = root / 'configs/graphs' / (run + '.json')
    if read(path) != derive(read(root / case['parent_graph']), case):
        raise ValueError('graph differs from exact frozen parent transformation')
    if inputs:
        hashes = read(root / 'configs/input_hashes.json')
        for key in ('video', 'portrait'):
            name = case[key]
            if Path(name).name != name:
                raise ValueError('input must be a basename')
            src, dst = root/'inputs'/name, root/'input'/name
            if src.is_symlink() or sha(src) != hashes[name]:
                raise ValueError('immutable source differs: ' + name)
            if dst.is_symlink():
                raise ValueError('loader input symlink')
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            if sha(dst) != hashes[name]:
                raise ValueError('actual loader input differs: ' + name)
    return {'case': case, 'graph_sha256': sha(path)}
