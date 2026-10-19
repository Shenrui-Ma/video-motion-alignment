"""Evaluate registered reference-bin controls on frozen common support, CPU only."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys


RUNS = {
    'offset0': 's05_full_seed1_mass_x0',
    'offset_plus4': 's05_full_seed1_offset4_x0',
    'offset_minus4': 's05_full_seed1_offsetm4_x0',
}
METRICS_SHA = 'eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='/data5/researcher/h3_runs/timing_autoresearch_20261016')
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    root = Path(args.root)
    home = root/'analysis/pose'
    if hashlib.sha256((root/'scripts/timing_metrics.py').read_bytes()).hexdigest() != METRICS_SHA:
        raise ValueError('Frozen metrics changed')
    protocol_path = root/'configs/reference_bin_control_protocol.json'
    protocol = json.loads(protocol_path.read_text())
    inventory, poses, diagnostics = {}, {}, {}
    for label, run_id in RUNS.items():
        admission = json.loads((home/'pilot'/f'{run_id}.history_provenance.json').read_text())
        if not admission['history_status']['completed'] or admission['history_status']['status_str'] != 'success':
            raise ValueError(f'No formal success history: {run_id}')
        if run_id in protocol['jobs'] and admission['config_sha256'] != protocol['jobs'][run_id]:
            raise ValueError(f'Config differs from registered graph: {run_id}')
        stem = Path(admission['history_output']['filename']).stem
        poses[label] = home/'pilot'/f'{stem}.pose.json'
        if not poses[label].is_file():
            raise ValueError(f'Pose absent: {run_id}; retain failed outputs separately')
        inventory[label] = {'admission': admission, 'pose_sha256': hashlib.sha256(poses[label].read_bytes()).hexdigest()}
        diagnostics[label] = {}
        for confidence in (.3, .5):
            raw = json.loads((home/'pilot'/f'{stem}.threshold{confidence}.timing.json').read_text())
            diagnostics[label][str(confidence)] = [
                {k: v for k, v in row.items() if k not in ('curve', 'distinct_lag_runner_up')}
                for row in raw['diagnostics']]
    destination = home/'offset_specificity'/args.tag
    destination.mkdir(parents=True, exist_ok=False)
    (destination/'protocol.json').write_bytes(protocol_path.read_bytes())
    report = {'registered_protocol': str(protocol_path), 'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'inventory': inventory, 'thresholds': {}, 'individual_frozen_diagnostics': diagnostics,
              'visual_quality_gate': 'requires independent fixed-frame review; not inferred from pose',
              'limits': ['exploratory descriptive threshold, not statistical significance',
                         'wrong-reference shape failures must not be sold as clean signed phase control',
                         'narrow fixed query window can censor a full requested event shift',
                         'same-input algebra preserves reference mass; different trajectories need not have equal measured mass']}
    for confidence in (.3, .5):
        output = destination/f'common_support.threshold{confidence}.json'
        command = [sys.executable, str(home/'compare_runs.py'), '--source', str(home/'old_sam/05_real_megumi_v.pose.json'),
                   '--confidence', str(confidence), '--output', str(output)]
        for label, path in poses.items():
            command += ['--run', f'{label}={path}']
        for window in ('50:65', '69:81', '80:92', '99:111', '0:140', '0:46', '47:67', '68:140', '112:140'):
            command += ['--window', window]
        result = subprocess.run(command, capture_output=True, text=True)
        (destination/f'threshold{confidence}.log').write_text(result.stdout+result.stderr)
        if result.returncode:
            raise RuntimeError('Common-support comparison failed; log preserved')
        raw = json.loads(output.read_text())
        primary = next(row for row in raw['results'] if row['window'] == [50, 65] and row['feature'] == 'arm_direction')
        errors = {label: row['same_frame_error_on_common_support'] for label, row in primary['runs'].items()}
        differences = {label: None if value is None or errors['offset0'] is None else value-errors['offset0']
                       for label, value in errors.items() if label != 'offset0'}
        coverage_ok = primary['common_valid_fraction'] >= .8
        report['thresholds'][str(confidence)] = {
            'common_coverage': primary['common_valid_fraction'], 'errors': errors,
            'nonzero_minus_zero': differences, 'coverage_passed': coverage_ok,
            'registered_specificity_error_gate_passed': coverage_ok and all(value is not None and value >= .05 for value in differences.values())}
    report['dual_threshold_specificity_error_gate_passed'] = all(row['registered_specificity_error_gate_passed'] for row in report['thresholds'].values())
    (destination/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'saved': str(destination), 'thresholds': report['thresholds'],
                      'dual_threshold_specificity_error_gate_passed': report['dual_threshold_specificity_error_gate_passed']}))


if __name__ == '__main__':
    main()
