"""Static R20 contract and inputs. No Torch/CUDA/network/process start."""
import argparse
import hashlib
import json
from pathlib import Path

REMOTE = '/data3/researcher/h3_runs/timing_cross_source_r20_20261016'
ARMS = ('r20_s07_native', 'r20_s07_full_6to14')
CAPTURES = (5, 10, 15, 19)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def expected_graph(parent, run_id):
    if run_id not in ARMS:
        raise ValueError('unknown R20 arm')
    graph = json.loads(json.dumps(parent))
    old = parent['50']['inputs']['run_id']
    oldroot = parent['5']['inputs']['audit_dir'].removesuffix('/audit')
    for node in graph.values():
        for key, value in node['inputs'].items():
            if isinstance(value, str):
                node['inputs'][key] = (value.replace(oldroot, REMOTE).replace(old, run_id)
                    .replace('07_sam_1312x736_shared_v3', '07_sam_1312x736_shared_r20')
                    .replace('07_sam_1312x736_2026101311_v3', '07_sam_1312x736_2026101311_r20'))
    graph['50']['inputs'].update(mode='native' if run_id == ARMS[0] else 'mass_preserve',
                                 step_start=6, step_end=15)
    return graph

def diff(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for key in sorted(set(a)|set(b)):
            out += diff(a.get(key), b.get(key), path+'/'+str(key))
        return out
    if a != b:
        return [{'path':path, 'before':a, 'after':b}]
    return []

def check(root):
    root = Path(root).resolve()
    protocol = read(root/'configs/protocol.json')
    for name, sha in protocol['parent_evidence_sha256'].items():
        if digest(root/'configs'/name) != sha:
            raise ValueError('parent evidence changed: '+name)
    for name, sha in protocol['input_sha256'].items():
        path = root/'inputs'/name
        if path.is_symlink() or digest(path) != sha:
            raise ValueError('input changed: '+name)
    parent = read(root/'configs/source07_actual_graph.json')
    if hashlib.sha256(parent['5']['inputs']['prompt'].encode()).hexdigest() != protocol['prompt_sha256']:
        raise ValueError('source07 prompt pin mismatch')
    if read(root/'configs/queue.json') != {'jobs':list(ARMS), 'sealed':True}:
        raise ValueError('R20 requires Native then Full sealed queue')
    graphs = {}
    for run_id in ARMS:
        graph = read(root/'configs'/f'{run_id}.json')
        if graph != expected_graph(parent, run_id):
            raise ValueError('unexpected scientific or administrative graph change: '+run_id)
        graphs[run_id] = graph
    pairdiff = diff(graphs[ARMS[0]], graphs[ARMS[1]])
    expected_paths = ['/14/inputs/filename_prefix','/50/inputs/mode','/50/inputs/run_id',
                      '/51/inputs/run_id','/52/inputs/run_id','/6/inputs/run_id']
    if [x['path'] for x in pairdiff] != expected_paths:
        raise ValueError('pair differs beyond mode and run/output identities')
    for rel, item in read(root/'configs/source_original_hashes.json').items():
        if digest(root/rel) != item['current_sha256']:
            raise ValueError('reviewed source changed: '+rel)
        if rel in ('extensions/H3TemporalRouter/core.py','extensions/H3TemporalRouter/layout.py',
                   'extensions/H3X0Readout/core.py'):
            if item['source_sha256'] != item['current_sha256']:
                raise ValueError('R2 scientific kernel/recorder must be byte identical: '+rel)
    if protocol['router']['event_frames_inclusive'] != [54,69] or protocol['router']['latent_bins_half_open'] != [16,22]:
        raise ValueError('source07 event mapping contract changed')
    if protocol['captures']['indices_zero_based'] != list(CAPTURES):
        raise ValueError('passive snapshot inventory changed')
    return {'passed':True, 'arms':list(ARMS), 'graph_sha256':{k:digest(root/'configs'/f'{k}.json') for k in ARMS},
            'pair_diff':pairdiff, 'scope':'static contract only; real encoding/Comfy/GPU and numerical pairing remain unmeasured'}

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    print(json.dumps(check(p.parse_args().root),indent=2))
