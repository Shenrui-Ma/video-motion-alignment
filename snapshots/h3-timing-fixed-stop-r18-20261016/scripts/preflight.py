"""Read-only local/remote contract gate. No Torch, network, GPU or process start."""
import argparse
import hashlib
import json
from pathlib import Path

RUN_ID = 'r18_s05_full_6to11'
REMOTE = '/data5/researcher/h3_runs/timing_fixed_stop_r18_20261016'
PARENT_REMOTE = '/data5/researcher/h3_runs/timing_spatial_r3_20261016'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_graph(parent):
    graph = json.loads(json.dumps(parent))
    for node in graph.values():
        for key, value in node['inputs'].items():
            if isinstance(value, str):
                node['inputs'][key] = (value.replace(PARENT_REMOTE, REMOTE)
                    .replace('r3_s05_full_6to14', RUN_ID)
                    .replace('05_sam_1312x736_shared_v3', '05_sam_1312x736_shared_r18')
                    .replace('05_sam_1312x736_2026101311_v3', '05_sam_1312x736_2026101311_r18'))
    graph['50']['inputs']['step_end'] = 12
    return graph


def check(root):
    root = Path(root).resolve()
    protocol = json.loads((root / 'configs/protocol.json').read_text())
    for name, sha in protocol['parent_evidence_sha256'].items():
        if digest(root / 'configs' / name) != sha:
            raise ValueError('parent evidence mismatch: ' + name)
    for name, sha in protocol['input_sha256'].items():
        if digest(root / 'inputs' / name) != sha:
            raise ValueError('input mismatch: ' + name)
    parent = json.loads((root / 'configs/parent_full_graph.json').read_text())
    graph = json.loads((root / 'configs' / (RUN_ID + '.json')).read_text())
    if graph != expected_graph(parent):
        raise ValueError('graph has changes beyond the fixed-stop contract')
    if json.loads((root / 'configs/queue.json').read_text()) != {'jobs': [RUN_ID], 'sealed': True}:
        raise ValueError('queue must contain exactly the one frozen arm')
    for rel, record in json.loads((root / 'configs/source_original_hashes.json').read_text()).items():
        if digest(root / rel) != record['current_sha256']:
            raise ValueError('extension changed since review: ' + rel)
        if rel.startswith('extensions/H3TemporalRouter/') and not rel.endswith('__init__.py'):
            if record['source_sha256'] != record['current_sha256']:
                raise ValueError('original R3 operator/probes must stay byte identical')
    expected = [5, 6, 7, 8, 9, 10, 11, 12, 15, 19]
    if protocol['captures']['x0_indices_zero_based'] != expected:
        raise ValueError('capture inventory mismatch')
    return {'passed': True, 'run_id': RUN_ID,
            'graph_sha256': digest(root / 'configs' / (RUN_ID + '.json')),
            'planned_NFE': 20, 'planned_block_calls': 1000, 'planned_routed_calls': 300,
            'scope': 'static source/config/input gate only; actual execution and exact tensor gates pending'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    print(json.dumps(check(parser.parse_args().root), indent=2))
