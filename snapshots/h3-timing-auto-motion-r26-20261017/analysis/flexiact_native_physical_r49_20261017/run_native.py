"""Report Native timing using the frozen paired runner's artifact and numeric checks."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

BINDING_FREEZE = '214ce19784408b0a8f567c4dae72df5e390761e36291cf69a01736d7449a6dfd'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_binding(root):
    root = Path(root)
    if digest(root / 'FREEZE.json') != BINDING_FREEZE:
        raise ValueError('Frozen artifact runner differs')
    freeze = json.loads((root / 'FREEZE.json').read_text())
    for name, expected in freeze['files'].items():
        if digest(root / name) != expected:
            raise ValueError('Frozen artifact runner file differs: ' + name)
    spec = importlib.util.spec_from_file_location('frozen_flexiact_pair_binding', root / 'run_pair.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def diagnose_native(evaluator, source, native):
    result = {'confidence_results': {}, 'native_lag_summary': [], 'physical_time_step_ms': 125}
    for confidence in (.3, .5):
        try:
            reference = evaluator.original_time_view(source, confidence)
            edited = evaluator.original_time_view(native, confidence)
        except ValueError as exc:
            if str(exc) != 'Insufficient reliable torso anchors for scale normalization':
                raise
            result['confidence_results'][str(confidence)] = {'status': 'unknown_visibility', 'rows': []}
            continue
        rows = [evaluator.diagnostic(reference, edited, window, feature)
                for window in evaluator.PROTOCOL['windows_inclusive'] for feature in evaluator.FEATURES]
        result['confidence_results'][str(confidence)] = {'status': 'measured', 'rows': rows}
    for window in evaluator.PROTOCOL['windows_inclusive']:
        for feature in evaluator.FEATURES:
            values = []
            for confidence in (.3, .5):
                rows = result['confidence_results'][str(confidence)]['rows']
                row = next((r for r in rows if r['window'] == window and r['feature'] == feature), None)
                values.append(row['lag_ms'] if row else None)
            qualified = all(v is not None for v in values) and abs(values[0] - values[1]) <= 125
            result['native_lag_summary'].append({'window': window, 'feature': feature,
                'status': 'qualified_exploratory' if qualified else 'unknown',
                'lag_ms_at_confidence_03_05': values})
    return evaluator.metrics.clean(result)


def main():
    parser = argparse.ArgumentParser()
    for name in ('binding-root', 'generated-manifest', 'source-manifest', 'source-protocol',
                 'numeric-root', 'metric-root', 'pair', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    run = load_binding(args.binding_root)
    run.require(args.pair in run.CONTRACT['pair_order'], 'Pair outside fixed pilot')
    run.frozen(args.numeric_root, 'FREEZE.json', run.CONTRACT['numeric_freeze_sha256'])
    run.frozen(args.metric_root, 'RUNTIME_FREEZE.json', run.CONTRACT['metric_runtime_freeze_sha256'])
    run.artifact(Path(args.source_protocol).resolve(), run.CONTRACT['source_pose_protocol_sha256'])
    os.environ['OMP_NUM_THREADS'] = os.environ['MKL_NUM_THREADS'] = '2'
    sys.path.insert(0, args.numeric_root)
    evaluator = run.import_file('frozen_native_numeric', Path(args.numeric_root) / 'evaluate.py')
    tracker = run.import_file('frozen_native_video_binding', Path(args.metric_root) / 'run_tracks.py')
    snapshots = {'generated': run.snapshot(args.generated_manifest), 'source': run.snapshot(args.source_manifest)}
    generated = snapshots['generated']['content']
    run.validate_manifest(generated['records'])
    folder = Path(args.generated_manifest).resolve().parent
    run.frozen(folder, 'FREEZE.json', run.CONTRACT['generated_pose_freeze_sha256'])
    run.require(generated['code_freeze_sha256'] == run.CONTRACT['generated_pose_freeze_sha256'] and
                generated['protocol_sha256'] == run.CONTRACT['generated_pose_protocol_sha256'], 'Generated sidecar differs')
    receipt = run.import_file('frozen_native_receipt', folder / 'manifest.py')
    source_folder = Path(args.source_manifest).resolve().parent
    run.frozen(source_folder, 'FREEZE.json', run.CONTRACT['source_pose_freeze_sha256'])
    source, source_item = run.source_pose(args.pair, snapshots['source']['content'], run.read(args.source_protocol),
                                        args.metric_root, source_folder)
    record = next(r for r in generated['records'] if r['pair_id'] == args.pair and r['method'] == 'native')
    receipt.verify_supplied_record(record)
    native = run.generated_pose(record, args.pair, 'native', tracker)
    started = time.monotonic()
    result = diagnose_native(evaluator, source, native)
    output = {'pair_id': args.pair, 'status': 'native_complete_auto_pending', 'fixed_pair_denominator': 5,
              'method': 'native', 'automatic': None, 'result': result, 'cpu_seconds': time.monotonic() - started,
              'source': source_item, 'generated': record, 'input_manifests': snapshots,
              'binding_freeze_sha256': BINDING_FREEZE, 'numeric_freeze_sha256': run.CONTRACT['numeric_freeze_sha256'],
              'runner_sha256': digest(__file__), 'scope': 'Native timing diagnosis; paired method effect awaits Auto.'}
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x') as stream:
        json.dump(output, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'pair': args.pair, 'output': str(destination), 'sha256': digest(destination),
                      'cpu_seconds': output['cpu_seconds'], 'native_lags': result['native_lag_summary']}))


if __name__ == '__main__':
    main()
