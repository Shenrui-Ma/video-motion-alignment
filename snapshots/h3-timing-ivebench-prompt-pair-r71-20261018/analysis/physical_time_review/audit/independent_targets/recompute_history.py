"""Re-evaluate already archived poses; isolate target failures, retain old output."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

os.environ['CUDA_VISIBLE_DEVICES'] = ''
HERE = Path(__file__).resolve().parent
from adapter import independent_targets


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound_read(item):
    assert sha(item['path']) == item['sha256'], item['path']
    return read(item['path'])


def numeric_compare(a, b):
    """Preserve both exactness and maximum roundoff discrepancy for audit."""
    if type(a) is not type(b):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return abs(a - b)
        raise AssertionError((type(a), type(b)))
    if isinstance(a, dict):
        assert a.keys() == b.keys()
        return max((numeric_compare(a[k], b[k]) for k in a), default=0)
    if isinstance(a, list):
        assert len(a) == len(b)
        return max((numeric_compare(x, y) for x, y in zip(a, b)), default=0)
    if isinstance(a, float):
        return abs(a - b)
    assert a == b, (a, b)
    return 0


def main(family):
    manifest = read(HERE / 'HISTORY_MANIFEST.json')
    config = manifest['evaluator_files'][family]
    for item in config['files']:
        assert sha(item['path']) == item['sha256']
    sys.path.insert(0, config['root'])
    name = 'evaluate90' if family == 'ive' else 'evaluate'
    spec = importlib.util.spec_from_file_location('frozen_history_evaluator', str(Path(config['root']) / (name + '.py')))
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    all_rows = []
    directory = HERE / 'history_results'
    directory.mkdir(exist_ok=True)
    for case in manifest['cases']:
        if case['family'] != family:
            continue
        source = bound_read(case['source'])
        targets = {key: bound_read(item) for key, item in case['targets'].items()}
        old = bound_read(case['old_report'])['result']
        args = (case['pair_id'],) if family == 'ive' else ()
        split = independent_targets(evaluator.evaluate, source, targets, *args)
        changes = []
        comparisons = []
        for name, result in split.items():
            old_name = case['old_method_labels'][name]
            for confidence, record in result['confidence_results'].items():
                legacy = old['confidence_results'][confidence]
                if legacy['status'] != record['status']:
                    changes.append({'target': name, 'confidence': confidence,
                                    'old_status': legacy['status'], 'new_status': record['status']})
                if legacy['status'] == record['status'] == 'measured':
                    for a, b in zip(legacy['rows'], record['rows']):
                        assert a['window'] == b['window'] and a['feature'] == b['feature']
                        comparisons.append(numeric_compare(a['diagnostics'][old_name], b['diagnostic']))
            for old_row, new_row in zip(old['paired_lag_summary'], result['lag_summary']):
                if old_row['methods'][old_name]['status'] != new_row['status']:
                    changes.append({'target': name, 'window': new_row['window'], 'feature': new_row['feature'],
                                    'old_status': old_row['methods'][old_name]['status'],
                                    'new_status': new_row['status']})
        assert max(comparisons, default=0) < 1e-12, 'Existing measured diagnostics changed beyond roundoff'
        output = {'case': case, 'manifest_sha256': sha(HERE / 'HISTORY_MANIFEST.json'),
                  'adapter_sha256': sha(HERE / 'adapter.py'), 'isolated_results': split,
                  'changes': changes, 'old_measured_max_absolute_numeric_difference': max(comparisons, default=0),
                  'old_measured_rows_compared': len(comparisons), 'old_outputs_unchanged': True}
        path = directory / (case['id'] + '.json.gz')
        with gzip.open(path, 'xt') as stream:
            json.dump(output, stream, allow_nan=False)
        all_rows.append({'case': case['id'], 'changes': changes, 'result_sha256': sha(path),
                         'old_measured_rows_compared': len(comparisons),
                         'max_difference': max(comparisons, default=0)})
    (HERE / (family.upper() + '_RECOMPUTE_SUMMARY.json')).write_text(json.dumps(all_rows, indent=2) + '\n')
    print(json.dumps({'family': family, 'cases': len(all_rows),
                      'cases_with_changes': sum(bool(r['changes']) for r in all_rows)}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--family', choices=['ive', 'flex'], required=True)
    main(p.parse_args().family)
