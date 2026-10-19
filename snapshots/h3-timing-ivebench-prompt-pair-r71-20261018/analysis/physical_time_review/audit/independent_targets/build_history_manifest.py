"""Resolve prior paired reports to their existing, hash-bound pose caches."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = Path('/Users/researcher/DevProjects')
MAPPING = {
    'flexiact_forced_metrics_r65_20261018': 'h3-flexiact-forced-metrics-r65-20261018',
    'flexiact_expanded_evaluation_r66_20261018': 'h3-flexiact-expanded-evaluation-r66-20261018',
    'timing_auto_motion_r26_20261017': 'h3-timing-auto-motion-r26-20261017',
    'timing_ivebench_native_r54_20261017': 'h3-timing-ivebench-native-r54-20261017',
}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def locate(name):
    path = Path(name)
    if path.exists():
        return path
    for remote, local in MAPPING.items():
        token = '/' + remote + '/'
        if token in name:
            candidate = BASE / local / name.split(token, 1)[1]
            if candidate.exists():
                return candidate
    raise FileNotFoundError(name)


def bound(path, expected=None):
    path = locate(str(path))
    actual = sha(path)
    if expected:
        assert actual == expected, path
    return {'path': str(path), 'sha256': actual}


def main():
    cases = []
    for tag, directory in [('R65', 'h3-flexiact-forced-metrics-r65-20261018'),
                           ('R66', 'h3-flexiact-expanded-evaluation-r66-20261018')]:
        root = BASE / directory
        for path in sorted((root / 'scores/physical').glob('*.json')):
            old = read(path)
            targets, receipts = {}, {}
            for name, item in old['generated_pose_receipts'].items():
                receipt = bound(item['file'], item['sha256'])
                records = read(Path(receipt['path']))
                targets[name] = bound(records['pose']['file'], records['pose']['sha256'])
                receipts[name] = receipt
            source = old['source_pose']
            cases.append({'id': tag + '_' + path.stem, 'family': 'flex',
                          'source': bound(source['file'], source['sha256']), 'targets': targets,
                          'target_receipts': receipts, 'old_report': bound(path),
                          'old_method_labels': {'native': 'native', 'forced': 'forced'}})
    analysis = BASE / 'h3-timing-auto-motion-r26-20261017/analysis'
    ive = analysis / 'ivebench_physical_time_eval_20261017'
    protocol = read(ive / 'PROTOCOL.json')
    for case in protocol['cases']:
        path = ive / 'results' / (case['pair_id'] + '.json')
        old = read(path)
        targets = {name: bound(item['pose_file'], item['pose_sha256'])
                   for name, item in old['generated_receipts'].items()}
        cases.append({'id': 'R55_' + case['pair_id'], 'family': 'ive', 'pair_id': case['pair_id'],
                      'source': bound(case['source_pose_path'], case['source_pose_sha256']),
                      'targets': targets, 'old_report': bound(path),
                      'old_method_labels': {'native': 'native', 'auto': 'auto'}})
    path = analysis / 'flexiact_generated_pose158_r50_retry_20261017/admin/priority_v2/results/chest.json'
    old = read(path)
    targets = {name: bound(item['local_paths']['pose'], item['pose_sha256'])
               for name, item in old['generated'].items()}
    cases.append({'id': 'R50retry_chest', 'family': 'flex',
                  'source': bound(old['source']['pose_path'], old['source']['pose_sha256']),
                  'targets': targets, 'old_report': bound(path),
                  'old_method_labels': {'native': 'native', 'automatic': 'automatic'}})
    evaluator_roots = {
        'ive': ive,
        'flex': BASE / 'h3-flexiact-forced-metrics-r65-20261018/runtime/physical'}
    evaluators = {}
    for family, root in evaluator_roots.items():
        filenames = ['evaluate90.py', 'timing_metrics.py', 'shared_support.py', 'PROTOCOL.json'] if family == 'ive' else ['evaluate.py', 'timing_metrics.py', 'PROTOCOL.json']
        evaluators[family] = {'root': str(root), 'files': [bound(root / name) for name in filenames]}
    result = {'schema': 'paired-physical-fault-isolation-history-v1', 'cases': cases,
              'evaluator_files': evaluators, 'pose_execution_required': False,
              'old_files_are_read_only': True}
    (HERE / 'HISTORY_MANIFEST.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'all_pose_sha_bindings_verified': True}))


if __name__ == '__main__':
    main()
