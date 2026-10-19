"""Native-only reporting from the preregistered IVE physical-time evaluator."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time

BASE = Path('/data3/researcher/h3_runs/timing_auto_motion_r26_20261017/analysis/ivebench_physical_time_eval_20261017')
FREEZE = '6e14dbf25ed28567848396f01eb70827ad0476570c542c44f3b757485a5ca794'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def qualify(values):
    ok = all(x is not None for x in values) and abs(values[0] - values[1]) <= 3
    return {'status': 'qualified_exploratory' if ok else 'unknown',
            'lag_frames_at_confidence_03_05': values,
            'lag_ms_at_confidence_03_05': [None if x is None else x * 1000 / 24 for x in values]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    assert sha(BASE / 'FREEZE.json') == FREEZE
    frozen = json.loads((BASE / 'FREEZE.json').read_text())
    for name, digest in frozen['files'].items():
        assert sha(BASE / name) == digest, name
    sys.path.insert(0, str(BASE))
    import run_pair as pair_module
    import pose90 as pose
    import evaluate90 as evaluator
    protocol = pose.P
    assert sha(pose.SOURCE / 'PROTOCOL.json') == protocol['source_protocol_sha256']
    assert sha(pose.SOURCE / 'COMPLETE.json') == protocol['source_complete_sha256']
    with pose.LOCK.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pending = [p for p in (pose.AUTO / 'audit/observations').glob('step*/request.json')
                   if (p.parent / 'native.json').exists()
                   and not any((p.parent / n).exists() for n in ('response.json', 'failure.json'))]
        if pending:
            return 75
        a.output.mkdir(parents=True, exist_ok=False)
        started = time.monotonic()
        records = []
        for case in protocol['cases']:
            pair = case['pair_id']
            source_path = Path(case['source_pose_path'])
            assert sha(source_path) == case['source_pose_sha256']
            source_raw = pose.validate_pose(pose.read(source_path), case['video_sha256'], case['effective_frames'])
            native_raw, receipt = pair_module.generated(pair, 'native')
            result = {'pair_id': pair, 'method': 'native', 'effective_frames': case['effective_frames'],
                      'confidence_results': {}, 'lag_summary': [], 'automatic_result': 'pending',
                      'source_pose_sha256': sha(source_path), 'generated_receipt': receipt}
            for confidence in protocol['confidence_thresholds']:
                try:
                    source = evaluator.valid_view(source_raw, case['effective_frames'], confidence)
                    native = evaluator.valid_view(native_raw, case['effective_frames'], confidence)
                except ValueError as exc:
                    if str(exc) != 'Insufficient reliable torso anchors for scale normalization':
                        raise
                    result['confidence_results'][str(confidence)] = {'status': 'unknown_visibility', 'rows': []}
                    continue
                rows = []
                for window in case['windows_inclusive']:
                    for feature in protocol['features']:
                        rows.append({'window': window, 'feature': feature,
                                     'diagnostic': evaluator.metrics.local_diagnostic(source, native, window, 24, feature)})
                result['confidence_results'][str(confidence)] = {'status': 'measured', 'rows': rows}
            for window in case['windows_inclusive']:
                for feature in protocol['features']:
                    lags = []
                    for confidence in protocol['confidence_thresholds']:
                        rows = result['confidence_results'][str(confidence)]['rows']
                        item = next((r for r in rows if r['window'] == window and r['feature'] == feature), None)
                        lags.append(item['diagnostic']['reliable_lag_frames'] if item else None)
                    result['lag_summary'].append(dict(window=window, feature=feature, **qualify(lags)))
            path = a.output / (pair + '.json')
            pose.save(path, evaluator.metrics.clean(result))
            records.append({'pair_id': pair, 'file': str(path), 'sha256': sha(path), 'lag_summary': result['lag_summary']})
        report = {'schema': 'ivebench-native-physical-diagnostic-v1', 'fixed_denominator': 5, 'completed': len(records),
                  'method': 'native', 'paired_automatic_results': 'pending', 'evaluator_freeze_sha256': FREEZE,
                  'protocol_sha256': sha(BASE / 'PROTOCOL.json'), 'reporting_script_sha256': sha(__file__),
                  'selection_sha256': protocol['selection_sha256'], 'records': records,
                  'physical_time_step_ms': 1000 / 24, 'qualification_agreement_frames': 3,
                  'cpu_seconds': time.monotonic() - started,
                  'scope': 'Fixed valid prefixes and predeclared windows/features; original numerical functions; all UNKNOWN retained.'}
        pose.save(a.output / 'REPORT.json', report)
        print(json.dumps({'completed': len(records), 'cpu_seconds': report['cpu_seconds'],
                          'report_sha256': sha(a.output / 'REPORT.json')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
