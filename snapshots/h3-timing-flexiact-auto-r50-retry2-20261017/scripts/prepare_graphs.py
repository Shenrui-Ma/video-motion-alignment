"""Prepare five graph templates; never certify missing actual parent executions."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/data5/researcher/h3_runs/timing_flexiact_auto_r50_retry2_20261017'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def derive(parent, case):
    g = copy.deepcopy(parent)
    run = case['run_id']
    shared = 'r50_source_' + case['source_id'] + '_shared'
    expected = case['geometry']
    if (parent['5']['inputs']['width'], parent['5']['inputs']['height'], parent['5']['inputs']['length']) != (
            expected['width'], expected['height'], expected['frames']):
        raise ValueError('parent template geometry differs')
    if parent['5']['inputs']['prompt'] != case['prompt'] or parent['6']['inputs']['noise_seed'] != case['seed']:
        raise ValueError('parent template prompt/seed differs')
    if parent['21']['inputs']['image'] != case['portrait'] or parent['22']['inputs']['file'] != case['video']:
        raise ValueError('parent template input differs')
    if parent['50']['class_type'] != 'H3TemporalRouter' or parent['50']['inputs']['mode'] != 'native':
        raise ValueError('requires Native parent template')
    # Exact graph fields only. Never replace text inside evidence bytes or prompts.
    for node in ('5', '6'):
        g[node]['inputs']['audit_dir'] = REMOTE + '/audit'
    g['51']['inputs']['source_audit_dir'] = REMOTE + '/audit'
    g['52']['inputs']['output_dir'] = REMOTE + '/audit/x0'
    g['5']['inputs']['run_id'] = shared
    g['51']['inputs']['source_run_id'] = shared
    for node in ('6', '51', '52'):
        g[node]['inputs']['run_id'] = run
    g['6']['inputs']['pair_id'] = run + '_noise'
    g['14']['inputs']['filename_prefix'] = run
    g['50'] = {'class_type': 'H3AutomaticWindowRouter', 'inputs': {
        'model': ['41', 0], 'positive': ['51', 0], 'run_id': run,
        'audit_dir': REMOTE + '/audit/counterfactual'}}
    return g


def diff(a, b, prefix=()):
    if isinstance(a, dict) and isinstance(b, dict):
        rows = []
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                rows.append({'path': list(prefix + (key,)), 'before': a.get(key), 'after': b.get(key)})
            else:
                rows.extend(diff(a[key], b[key], prefix + (key,)))
        return rows
    return [] if a == b else [{'path': list(prefix), 'before': a, 'after': b}]


def main():
    cases = json.loads((ROOT/'configs/protocol.json').read_text())['cases']
    originals = json.loads((ROOT/'audit/R49_GRAPH_ORIGINALS.json').read_text())
    records = []
    out = ROOT/'configs/graphs'
    out.mkdir(exist_ok=True)
    for case in cases:
        source = ROOT/'configs/parent_graphs'/(case['parent_run']+'.json')
        if digest(source) != originals['files'][source.name]:
            raise ValueError('parent graph bytes differ from original record')
        parent = json.loads(source.read_text())
        graph = derive(parent, case)
        target = out/(case['run_id']+'.json')
        data = (json.dumps(graph, indent=2, ensure_ascii=False)+'\n').encode()
        if target.exists() and target.read_bytes() != data:
            raise FileExistsError('refuse to replace a different graph: '+str(target))
        target.write_bytes(data)
        records.append({'run_id': case['run_id'], 'source_id': case['source_id'],
                        'parent_template': str(source.relative_to(ROOT)), 'parent_template_sha256': digest(source),
                        'graph': str(target.relative_to(ROOT)), 'graph_sha256': digest(target),
                        'diff': diff(parent, graph)})
    result = {'schema': 'r50-prepared-graph-derivations-v1', 'deployable': False,
              'actual_parent_history_verified': False, 'parent_template_record': originals,
              'scope': 'Frozen R49 graph templates only; actual histories and full parent closure remain mandatory.',
              'cases': records}
    (ROOT/'audit/GRAPH_PREPARATION.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'prepared_graphs': len(records), 'deployable': False,
                      'diff_counts': [len(r['diff']) for r in records]}))


if __name__ == '__main__':
    main()
