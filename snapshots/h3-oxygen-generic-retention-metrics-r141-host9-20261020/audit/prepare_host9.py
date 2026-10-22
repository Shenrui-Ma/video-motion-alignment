"""Create the host9 consumer from frozen R141 inputs and shared helpers."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.with_name('h3-oxygen-generic-retention-metrics-r141-20261020')
PRODUCER = ROOT.with_name('h3-timing-oxygen-generic-retention-r141-host9-20261020')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


assert not (ROOT / 'configs').exists(), 'Consumer already prepared'
baseline = read(BASE / 'CONSUMER_FREEZE.json')
assert all(sha(BASE / name) == digest for name, digest in baseline['files'].items())
seal = read(PRODUCER / 'deploy_manifest.json')
assert all(sha(PRODUCER / name) == value['sha256'] for name, value in seal['files'].items())
science = read(PRODUCER / 'configs/scientific_contract.json')
runtime = read(PRODUCER / 'configs/runtime.json')
assert sha(PRODUCER / 'configs/scientific_contract.json') == sha(BASE / 'configs/producer_scientific_contract.json')
assert sha(PRODUCER / 'design/PREREGISTERED_EVENTS.json') == sha(BASE / 'configs/PREREGISTERED_EVENTS.json')
assert runtime['host'] == 'H3_SERVER_A' and runtime['uid'] == 1016

for name in baseline['files']:
    source, destination = BASE / name, ROOT / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if name.startswith('inputs/'):
        os.link(source, destination)
    else:
        data = source.read_bytes()
        if name in ('scripts/consume_native.py', 'scripts/consume_pair.py'):
            data = data.replace(str(BASE).encode(), str(ROOT).encode())
        with destination.open('xb') as handle:
            handle.write(data)

contract = read(ROOT / 'configs/contract.json')
contract.update(
    producer_local=str(PRODUCER),
    producer_remote=runtime['remote_root'],
    producer_seal_sha256=sha(PRODUCER / 'deploy_manifest.json'),
    producer_contract_sha256=sha(PRODUCER / 'configs/scientific_contract.json'),
    producer_runtime_sha256=sha(PRODUCER / 'configs/runtime.json'),
    host=runtime['host'],
)
for source in contract['sources']:
    source['original_media']['file'] = str(ROOT / 'inputs' / Path(source['original_media']['file']).name)
    for run_key, hash_key in [('run_id', 'graph_sha256'), ('forced_run_id', 'forced_graph_sha256')]:
        rel = Path('configs/graphs') / (source[run_key] + '.json')
        (ROOT / rel).write_bytes((PRODUCER / rel).read_bytes())
        source[hash_key] = sha(ROOT / rel)
(ROOT / 'configs/contract.json').write_text(json.dumps(contract, ensure_ascii=False, indent=2) + '\n')
(ROOT / 'configs/producer_runtime.json').write_bytes((PRODUCER / 'configs/runtime.json').read_bytes())
cues = read(ROOT / 'configs/SOURCE_EVENT_REVIEW_CUES.json')
for item in cues['items']:
    item['evidence']['file'] = str(PRODUCER / 'design/PREREGISTERED_EVENTS.json')
(ROOT / 'configs/SOURCE_EVENT_REVIEW_CUES.json').write_text(json.dumps(cues, ensure_ascii=False, indent=2) + '\n')

old_contract = read(BASE / 'configs/contract.json')
normalized = copy.deepcopy(contract)
for key in ('producer_local', 'producer_remote', 'producer_seal_sha256', 'producer_runtime_sha256', 'host'):
    normalized[key] = old_contract[key]
for actual, old in zip(normalized['sources'], old_contract['sources']):
    for key in ('graph_sha256', 'forced_graph_sha256'):
        actual[key] = old[key]
    actual['original_media']['file'] = old['original_media']['file']
assert normalized == old_contract, 'Scientific consumer contract changed'
for path in (ROOT / 'scripts').glob('*.py'):
    ast.parse(path.read_text(), filename=str(path))
save(ROOT / 'audit/HOST9_ADAPTATION.json', {
    'passed': True,
    'source_consumer': str(BASE),
    'source_freeze_sha256': sha(BASE / 'CONSUMER_FREEZE.json'),
    'producer_local': str(PRODUCER),
    'producer_seal_sha256': contract['producer_seal_sha256'],
    'scientific_contract_unchanged': True,
    'preregistered_events_unchanged': True,
    'scientific_consumer_criteria_unchanged': True,
    'source_event_brackets_unchanged': True,
    'immutable_inputs_hardlinked': [
        name for name in baseline['files'] if name.startswith('inputs/')
    ],
    'administrative_changes': [
        'producer local and remote roots, host alias, producer seal/runtime digests',
        'copied graph paths and corresponding graph digests',
        'local output and original-media paths',
        'source event evidence path',
    ],
    'actual_execution_binding_pending': True,
    'network_access_performed': False,
    'GPU_started': False,
})
print(json.dumps({'prepared': str(ROOT), 'producer_seal_sha256': contract['producer_seal_sha256']}))
