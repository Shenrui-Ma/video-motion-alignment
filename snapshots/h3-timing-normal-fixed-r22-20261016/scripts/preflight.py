"""Read-only local/remote contract gate. No Torch, network, GPU or process start."""
import argparse
import hashlib
import json
from pathlib import Path

RUN_ID = 'r22_s05_seed1313_full6to11'
REMOTE = '/data5/researcher/h3_runs/timing_normal_fixed_r22_20261016'
PARENT_REMOTE = '/data5/researcher/h3_runs/timing_fixed_stop_r18_20261016'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_graph(parent):
    graph = json.loads(json.dumps(parent).replace(PARENT_REMOTE,REMOTE).replace('r18_s05_full_6to11',RUN_ID))
    graph['5']['inputs']['run_id']='05_sam_1312x736_shared_r22'
    graph['51']['inputs']['source_run_id']='05_sam_1312x736_shared_r22'
    graph['6']['inputs']['pair_id']='05_sam_1312x736_2026101313_r22'
    graph['6']['inputs']['noise_seed']=2026101313
    return graph


def admission_document(root, approved=False):
    value=json.loads((Path(root)/'configs/admission.json').read_text())
    template=json.loads((Path(root)/'configs/admission_template.json').read_text())
    if set(value)!=set(template['fixed_fields'])|{'permitted_compute_processes','root_live_review_required'}:
        raise ValueError('unreviewed admission field')
    if any(value[k]!=v for k,v in template['fixed_fields'].items()):raise ValueError('frozen admission field changed')
    if type(value['root_live_review_required']) is not bool or (approved and value['root_live_review_required']):raise ValueError('root live admission not approved')
    if not isinstance(value['permitted_compute_processes'],list):raise ValueError('invalid permitted registry')
    for row in value['permitted_compute_processes']:
        if set(row)!={'pid','identity'} or type(row['pid']) is not int or set(row['identity'])!={'uid','start_ticks','cmdline_sha256'}:raise ValueError('invalid permitted identity')
    return value


def check(root, live=False):
    root = Path(root).resolve()
    protocol = json.loads((root / 'configs/protocol.json').read_text())
    admission_document(root,approved=live)
    for name, sha in protocol['parent_evidence_sha256'].items():
        if digest(root / 'configs' / name) != sha:
            raise ValueError('parent evidence mismatch: ' + name)
    for name, sha in protocol['input_sha256'].items():
        if digest(root / 'inputs' / name) != sha:
            raise ValueError('input mismatch: ' + name)
    normal_history=json.loads((root/'configs/parent_normal_history.json').read_text())
    normal_graph=json.loads((root/'configs/parent_normal_graph.json').read_text())
    if not (normal_history['status']['status_str']=='success' and normal_history['status']['completed'] is True and normal_history['prompt'][2]==normal_graph):
        raise ValueError('R14 actual executed normal graph is not the pinned parent')
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
    seal=root/'deploy_manifest_v1.json'
    if seal.exists():
        for rel,row in json.loads(seal.read_text())['files'].items():
            if digest(root/rel)!=row['sha256']:raise ValueError('sealed file changed: '+rel)
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
