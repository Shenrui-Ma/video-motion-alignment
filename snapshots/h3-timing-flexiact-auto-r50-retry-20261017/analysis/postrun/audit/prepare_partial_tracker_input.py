"""Bind one completed Auto score input for root-controlled later GPU tracking."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
POST = HERE.parent
RUNTIME = Path('/data5/researcher/h3_runs/flexiact_official_metric_20261017')
FREEZE = 'fa573e2065d1c140ef232513d73b909d2aa2902046d4a9becf609a6e549ad580'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())


def main():
    p = argparse.ArgumentParser(); p.add_argument('--source', required=True)
    a = p.parse_args()
    sys.path.insert(0, str(POST)); import remote_consume as consumer
    sys.path.insert(0, str(HERE / 'priority_v2')); from priority import pending
    consumer.online_pending = lambda: pending(consumer.P['online_priority_roots'])
    case = next(c for c in consumer.P['cases'] if c['source_id'] == a.source)
    root = POST / 'completed_cases' / case['run_id']
    with consumer.locked():
        ready = read(root / 'CASE_READY.json')
        mp = root / 'final' / case['run_id'] / 'METRIC_INPUTS.json'
        if not ready['summary']['passed'] or ready['metric_inputs_sha256'] != sha(mp):
            raise ValueError('Actual case release changed')
        metric = read(mp); mapping = Path(metric['edited49']).with_suffix('.mapping.json')
        if sha(RUNTIME / 'RUNTIME_FREEZE.json') != FREEZE: raise ValueError('Official runtime seal differs')
        freeze = read(RUNTIME / 'RUNTIME_FREEZE.json')
        for filename, record in freeze['files'].items():
            if sha(RUNTIME / filename) != record['sha256']: raise ValueError('Runtime file changed: ' + filename)
        item = {'id': metric['official_pair_id'], 'method': 'automatic', 'role': 'generated',
                'file': metric['edited49'], 'sha256': metric['edited49_sha256'],
                'generation_frame_indices': list(range(0, 147, 3)),
                'generation_binding': {'metric_inputs': {'file': str(mp), 'sha256': sha(mp)},
                                       'release_mapping': {'file': str(mapping), 'sha256': sha(mapping)}}}
        if sha(item['file']) != item['sha256']: raise ValueError('Actual edited49 changed')
        sys.path.insert(0, str(RUNTIME)); from run_tracks import validate_generated_binding
        checked = validate_generated_binding(item, Path(item['file']))
        ref = RUNTIME / 'outputs/reference' / a.source / 'REPORT.json'
        ref_value = read(ref)
        if ref_value['case']['sha256'] != metric['original_source_sha256'] or ref_value['passed'] is not True:
            raise ValueError('Reference cache differs')
        value = {'schema': 'h3-flexiact-auto-partial-mf-inputs-v1', 'inputs': [item],
                 'method': 'automatic', 'fixed_pair_denominator': 5,
                 'planned_pair_order': ['human/' + x['source_id'] + '/000' for x in consumer.P['cases']],
                 'metric_runtime_freeze_sha256': FREEZE,
                 'release_evidence': {'file': str(root / 'CASE_READY.json'), 'sha256': sha(root / 'CASE_READY.json')},
                 'preflight': {'passed': True, 'binding': checked,
                               'reference_report_sha256': sha(ref), 'reference_tracks_sha256': ref_value['tracks_sha256']},
                 'builder_sha256': sha(__file__), 'tracking_executed': False,
                 'scope': 'One completed actual Auto task from fixed five; GPU tracking remains root-controlled.'}
        folder = HERE / 'tracking_inputs'; folder.mkdir(exist_ok=True)
        output = folder / (a.source + '.json')
        if output.exists():
            if read(output) != value: raise ValueError('Existing input changed')
        else:
            with output.open('x') as f: json.dump(value, f, indent=2); f.write('\n')
        print(json.dumps({'file': str(output), 'sha256': sha(output), 'tracking_executed': False}))

if __name__ == '__main__':
    try: main()
    except BlockingIOError:
        print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY'); raise SystemExit(75)
