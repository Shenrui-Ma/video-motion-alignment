"""Summarize the registered semantic 2x2 using frozen, already extracted poses."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys


METRICS_SHA = 'eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e'
RUNS = {'A': 's05_full_seed1_native_x0', 'B': 's05_semantic_b_p6_t6',
        'C': 's05_semantic_c_p0_t6', 'D': 's05_semantic_d_p6_t0'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='/data5/researcher/h3_runs/timing_autoresearch_20261016')
    parser.add_argument('--semantic-root', default='/data5/researcher/h3_runs/timing_autoresearch_20261016_semantic0')
    parser.add_argument('--tag', required=True)
    parser.add_argument('--protocol', required=True, help='Unchanged preregistered protocol file or verified copy')
    args = parser.parse_args()
    root, semantic = Path(args.root), Path(args.semantic_root)
    home = root/'analysis/pose'
    if hashlib.sha256((root/'scripts/timing_metrics.py').read_bytes()).hexdigest() != METRICS_SHA:
        raise ValueError('Frozen metrics changed')
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text())
    destination = home/'semantic_factorial'/args.tag
    destination.mkdir(parents=True, exist_ok=False)
    (destination/'protocol.json').write_bytes(protocol_path.read_bytes())
    # This checker understands intentional Qwen embedding changes, unlike generic pair equivalence.
    check = subprocess.run([sys.executable, str(semantic/'scripts/check_encoded_acceptance.py'),
                            str(semantic), '--require-all'], capture_output=True, text=True)
    (destination/'actual_encoding_acceptance.log').write_text(check.stdout+check.stderr)
    if check.returncode:
        raise RuntimeError('Actual factorial acceptance failed; log retained')
    inventory, poses, diagnostics = {}, {}, {}
    for label, run_id in RUNS.items():
        run_home = (root if label == 'A' else semantic)/'analysis/pose/pilot'
        admission = json.loads((run_home/f'{run_id}.history_provenance.json').read_text())
        status = admission['history_status']
        if not status['completed'] or status['status_str'] != 'success':
            raise ValueError(f'No exact success history: {run_id}')
        stem = Path(admission['history_output']['filename']).stem
        poses[label] = run_home/f'{stem}.pose.json'
        inventory[label] = {'run': run_id, 'admission': admission,
                            'pose_sha256': hashlib.sha256(poses[label].read_bytes()).hexdigest()}
        diagnostics[label] = {}
        for confidence in (.3, .5):
            raw = json.loads((run_home/f'{stem}.threshold{confidence}.timing.json').read_text())
            diagnostics[label][str(confidence)] = [
                {k: row.get(k) for k in ('window', 'feature', 'status', 'flags', 'reliable_lag_frames')}
                | {'same_frame': row['same_frame'], 'best': row.get('best')}
                for row in raw['diagnostics']]
    report = {'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'protocol': protocol, 'inventory': inventory, 'diagnostics': diagnostics,
              'thresholds': {}, 'factor_gates': {},
              'runtime_replay_gate': 'parent independent all5 tensor and141 RGB audit; inspect before causal attribution',
              'quality_gate': 'independent fixed55/86 review; not inferred from pose',
              'limits': ['one selected source/seed, descriptive not statistical',
                         'timestamps change contextual Qwen embeddings, not direct temporal RoPE',
                         'four-arm same-frame errors use shared valid support; lags remain frozen within-arm estimators',
                         'rejected lags remain null, never zero',
                         'A0 encoding-only gate is not an independent quality sample']}
    pairs = {'timestamp_at_P0': ('C', 'A'), 'timestamp_at_P6': ('B', 'D'),
             'pixels_at_T0': ('D', 'A'), 'pixels_at_T6': ('B', 'C')}
    for confidence in (.3, .5):
        key = str(confidence)
        lag = {label: next(row['reliable_lag_frames'] for row in diagnostics[label][key]
                          if row['feature'] == 'arm_direction' and row['window'] == [50, 65])
               for label in RUNS}
        contrasts = {name: None if lag[x] is None or lag[y] is None else lag[x]-lag[y]
                     for name, (x, y) in pairs.items()}
        contrasts['interaction'] = (None if any(v is None for v in lag.values())
                                    else lag['B']-lag['D']-lag['C']+lag['A'])
        report['thresholds'][key] = {'primary_lags': lag, 'signed_lag_contrasts': contrasts}
        output = destination/f'common_support.threshold{confidence}.json'
        cmd = [sys.executable, str(home/'compare_runs.py'), '--source',
               str(home/'old_sam/05_real_megumi_v.pose.json'), '--confidence', key, '--output', str(output)]
        for label, path in poses.items():
            cmd += ['--run', f'{label}={path}']
        for window in ('50:65', '69:81', '80:92', '99:111', '0:140', '0:46', '47:67', '68:140', '112:140'):
            cmd += ['--window', window]
        result = subprocess.run(cmd, capture_output=True, text=True)
        (destination/f'common_support.threshold{confidence}.log').write_text(result.stdout+result.stderr)
        if result.returncode:
            raise RuntimeError('Common-support computation failed; log retained')
    gate = protocol['exploratory_meaningful_effect']
    min_effect = gate['absolute_contrast_at_both_thresholds_at_least_frames']
    max_disagreement = gate['threshold_contrast_disagreement_at_most_frames']
    for factor, names in {'timestamp': ('timestamp_at_P0', 'timestamp_at_P6'),
                          'pixels': ('pixels_at_T0', 'pixels_at_T6')}.items():
        values = {name: [report['thresholds'][key]['signed_lag_contrasts'][name] for key in ('0.3', '0.5')]
                  for name in names}
        each = {name: all(v is not None for v in val) and min(abs(v) for v in val) >= min_effect
                and abs(val[0]-val[1]) <= max_disagreement and val[0]*val[1] > 0
                for name, val in values.items()}
        same_sign = all(each.values()) and values[names[0]][0]*values[names[1]][0] > 0
        report['factor_gates'][factor] = {'values': values, 'individual_contrast_passed': each,
                                         'same_direction_across_other_factor_passed': same_sign,
                                         'registered_exploratory_phase_gate_passed': same_sign}
    (destination/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'saved': str(destination), 'thresholds': report['thresholds'],
                      'factor_gates': report['factor_gates']}))


if __name__ == '__main__':
    main()
