"""Read-only per-case R49 intake checklist. Never writes a production binding.

Metadata checks do not replace tensor verification by the sealed R49 runtime gate
or R50's actual same-input prefix gate. Absent files stay pending, never guessed.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def safe(root, name):
    relative = Path(name)
    path = root / relative
    if relative.is_absolute() or '..' in relative.parts or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('unsafe parent relative path: ' + name)
    return path


def inspect_case(archive, case, template, inventory):
    archive = Path(archive)
    run = case['parent_run']
    names = {'graph': f'configs/graphs/{run}.json', 'history': f'logs/{run}_history.json',
             'job': f'logs/{run}_job.json', 'conditioning': f'audit/{run}_conditioning.json',
             'noise': f'audit/{run}_noise.json', 'router': f'audit/router/{run}.json',
             'captures': f'audit/x0/{run}/manifest.json',
             'shared': 'audit/' + template['5']['inputs']['run_id'] + '_conditioning.json'}
    records, data, missing = {}, {}, []
    for key, name in names.items():
        path = safe(archive, name)
        if not path.exists():
            missing.append(name)
            continue
        if name not in inventory or sha(path) != inventory[name]['sha256'] or path.stat().st_size != inventory[name]['bytes']:
            raise ValueError('unanchored or changed parent file: ' + name)
        data[key] = read(path)
        records[key] = {'path': str(path), **inventory[name]}
    if 'graph' in data and data['graph'] != template:
        raise ValueError('actual graph differs from frozen per-source template')
    if 'history' in data:
        h = data['history']
        if h['status']['completed'] is not True or h['status']['status_str'] != 'success' or h['prompt'][2] != template:
            raise ValueError('actual history/graph did not complete successfully')
    if 'job' in data:
        j = data['job']
        if j['status'] != 'success' or j['name'] != run:
            raise ValueError('actual job belongs to another or incomplete run')
        if 'graph' in records and j['graph_sha256'] != records['graph']['sha256']:
            raise ValueError('submitted graph SHA differs')
        if 'history' in data and j['prompt_id'] != data['history']['prompt'][1]:
            raise ValueError('history/submission mismatch')
    entities = set()
    def visit(value):
        if isinstance(value, dict):
            if 'tensor_file' in value:
                if not {'shape', 'dtype', 'sha256'} <= set(value):
                    raise ValueError('incomplete condition tensor signature')
                name = 'audit/' + value['tensor_file']
                safe(archive, name)
                entities.add(name)
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
    if 'shared' in data:
        visit(data['shared'])
        if len(entities) != 8 or 'tensor_file' not in data['shared']['conditioning_embedding']:
            raise ValueError('expected eight actual clean-condition entities including embedding')
    if 'conditioning' in data:
        c = data['conditioning']
        if c['run_id'] != run or c['prompt'] != case['prompt'] or len(c['native_vae_calls']) != 2:
            raise ValueError('actual source/prompt/reference count differs')
        if 'shared' in records and (c['pair_snapshot']['verified'] is not True or c['pair_snapshot']['source_manifest_sha256'] != records['shared']['sha256']):
            raise ValueError('actual shared conditioning link differs')
    if 'noise' in data:
        n = data['noise']
        if n['run_id'] != run or n['signature']['seed'] != case['seed'] or len(n['actual_noise_streams']) != 2:
            raise ValueError('actual AV noise identity differs')
        entities.add('audit/' + n['pair_id'] + '_noise.pt')
    if 'captures' in data:
        m = data['captures']
        expected = [f'x0_step{i:03d}.pt' for i in range(20)] + ['sampler_final.pt']
        rows = m['captures'] + [m['final_sampler_result']]
        if (m['run_id'] != run or m['status'] != 'complete' or m['callback_count'] != 20 or
                m['seed'] != case['seed'] or m['geometry'] != case['geometry'] or
                m['capture_steps_zero_based'] != list(range(20)) or [x['file'] for x in rows] != expected):
            raise ValueError('actual 21 captures/run/geometry differs')
        entities.update(f'audit/x0/{run}/' + name for name in expected)
    for name in entities:
        safe(archive, name)
        if name not in inventory:
            raise ValueError('actual tensor absent from archive inventory: ' + name)
    return {'run_id': case['run_id'], 'parent_run': run, 'source_id': case['source_id'],
            'status': 'METADATA_PRESENT_AWAITING_FULL_BINDER' if not missing else 'WAITING_ACTUAL_PARENT',
            'files': records, 'missing_metadata': missing,
            'tensor_inventory': {name: inventory[name] for name in sorted(entities)},
            'tensor_payloads_loaded_or_reverified': False, 'production_ready': False}


def inspect(archive, root=ROOT):
    archive, root = Path(archive), Path(root)
    cases = read(root/'configs/protocol.json')['cases']
    anchor_names = ('RUN_GATE.json', 'FILE_INVENTORY.json', 'RUNTIME_GATE.json', 'deploy_manifest.json')
    pending = [name for name in anchor_names if not (archive/name).exists()]
    if pending:
        return {'status': 'WAITING_R49_ARCHIVE', 'missing_anchors': pending,
                'runs': [c['parent_run'] for c in cases], 'production_ready': False}
    gate, inventory, runtime = [read(archive/name) for name in anchor_names[:3]]
    if (gate['passed'] is not True or runtime['passed'] is not True or
            not runtime['checks'] or not all(value is True for value in runtime['checks'].values()) or
            gate['runs'] != [c['parent_run'] for c in cases] or
            gate['file_inventory_sha256'] != sha(archive/'FILE_INVENTORY.json') or
            gate['runtime_gate_sha256'] != sha(archive/'RUNTIME_GATE.json') or
            sha(archive/'deploy_manifest.json') != read(root/'design/SOURCE_BINDING.json')['native_manifest_sha256']):
        raise ValueError('R49 archived runtime/manifest anchor differs')
    rows = [inspect_case(archive, c, read(root/'configs/parent_graphs'/(c['parent_run']+'.json')), inventory) for c in cases]
    return {'status': 'INTAKE_RECORDED_NOT_BOUND', 'production_ready': False,
            'archive_anchors': {n: sha(archive/n) for n in anchor_names}, 'cases': rows,
            'remaining': ['full condition/noise/21PT inventory and raw signatures via frozen verifier',
                          'per-source packed-layout geometry and full sigma semantics',
                          'source158 sidecar finite intake/provenance/hash binding',
                          'immutable copied evidence, final producer protocol/review/resource gates']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    result = inspect(args.archive)
    text = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        with args.output.open('x') as f: f.write(text)
    print(json.dumps({'status': result['status'], 'production_ready': False}))
