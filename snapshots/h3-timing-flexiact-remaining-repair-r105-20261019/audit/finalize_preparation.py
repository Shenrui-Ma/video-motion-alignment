"""Complete CPU preparation from the verified R104 runtime; no service launch."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent / 'h3-timing-flexiact-remaining-repair-r104-20261019'
OLD = ('fitness__game_man_4', 'human2animal_1__movie_man_11', 'crouch__movie_man_5')
NEW = ('human2animal_2__movie_man_11', 'crouch__movie_man_4', 'human2animal_3__game_man_4')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


assert not (ROOT / 'deploy_manifest.json').exists()
numeric = read(PARENT / 'configs/runtime_kernel_hashes.json')
# The preparation factory's R103 source has since gained recovery-only tests.
# Preserve those snapshots outside discovery; R105 uses R104's strict COMPLETE gate.
for src in (ROOT / 'tests').glob('*.py'):
    if not (PARENT / 'tests' / src.name).exists():
        dest = ROOT / 'audit/bootstrap_test_snapshots' / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src, dest)
for folder in ('scripts', 'extensions', 'tests', 'analysis/postrun'):
    for src in (PARENT / folder).glob('*.py'):
        rel = str(src.relative_to(PARENT))
        dst = ROOT / rel.replace('r104_contract.py', 'r105_contract.py')
        dst.parent.mkdir(parents=True, exist_ok=True)
        if rel in numeric:
            shutil.copy2(src, dst)
        else:
            text = src.read_text().replace('r104', 'r105').replace('R104', 'R105')
            for old, new in zip(OLD, NEW):
                text = text.replace(old, new)
            dst.write_text(text)

for name in ('root_run_batch.py', 'check_cpu_imports.py', 'remote_cpu_validate.py'):
    text = (PARENT / 'audit' / name).read_text().replace('r104', 'r105').replace('R104', 'R105')
    (ROOT / 'audit' / name).write_text(text)

# Runtime storage changes while existing model/core files remain at their original paths.
runtime = read(ROOT / 'configs/runtime.json')
assert runtime['expected_gpu_index'] == 0 and runtime['port'] == 8569
assert runtime['remote_root'].startswith('/home/researcher/h3_runs/')

storage = read(PARENT / 'configs/storage_policy.json')
storage['schema'] = 'r105-storage-budget-v1'
put(ROOT / 'configs/storage_policy.json', storage)

predecessors = []
for key, directory in (
    ('r102', 'h3-timing-ive-task-repair-r102-20261019'),
    ('r108', 'h3-timing-ive-fireplace-recovery-r108-20261019'),
):
    previous = ROOT.parent / directory
    profile = read(previous / 'configs/runtime.json')
    spec = read(previous / 'configs/scientific_contract.json')
    predecessors.append({
        'key': key, 'remote_root': profile['remote_root'],
        'producer_seal_sha256': sha(previous / 'deploy_manifest.json'),
        'runtime_sha256': sha(previous / 'configs/runtime.json'),
        'kind': 'screen', 'required_sources': spec['source_ids'],
    })
put(ROOT / 'configs/predecessor.json', {
    'schema': 'r105-actual-attempt-predecessors-v1', 'required': predecessors,
    'attempt_names': 'Root supplies actual completed attempts; exact release required.',
})

sys.path.insert(0, str(ROOT / 'scripts'))
import r105_contract

spec = read(ROOT / 'configs/scientific_contract.json')
for case in spec['cases']:
    put(ROOT / 'configs/graphs' / (case['run_id'] + '.json'), r105_contract.expected_graph(ROOT, case))
for rel, entry in numeric.items():
    assert sha(ROOT / rel) == entry['current_sha256'] == sha(PARENT / rel)

put(ROOT / 'audit/R104_RUNTIME_REUSE.json', {
    'parent': str(PARENT), 'producer_seal_sha256': sha(PARENT / 'deploy_manifest.json'),
    'six_numerical_modules': {p: sha(ROOT / p) for p in numeric},
    'new_sources': list(NEW), 'GPU_started': False,
})
print(json.dumps({'prepared': str(ROOT), 'sources': list(NEW)}))
