"""Apply the frozen intermediate-checkpoint protocol without changing pose metrics."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


WINDOWS = [(50, 65), (69, 81), (80, 92), (99, 111)]
FEATURES = ('arm_direction', 'left_arm_direction', 'right_arm_direction', 'wrist_relative', 'body_xy')
FROZEN_HASH = 'eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e'


def gate(rows):
    direction = [rows[t]['arm_direction'].get('reliable_lag_frames') for t in ('0.3', '0.5')]
    position = [rows[t]['wrist_relative'].get('reliable_lag_frames') for t in ('0.3', '0.5')]
    reasons = []
    if any(x is None for x in direction):
        reasons.append('direction_phase_unavailable_at_one_or_both_thresholds')
    else:
        if abs(direction[0]-direction[1]) > 2:
            reasons.append('direction_threshold_estimates_differ_over_two_frames')
        if all(abs(x) > 2 for x in direction) and direction[0]*direction[1] < 0:
            reasons.append('direction_threshold_sign_disagreement')
    # A missing position estimate cannot establish that a directional phase is
    # free from the amplitude confound; report it as unknown, never as agreement.
    if any(x is None for x in position):
        reasons.append('position_phase_unavailable_confound_check_unknown')
    for d, p in zip(direction, position):
        if d is not None and p is not None and abs(d-p) > 3:
            reasons.append('direction_position_disagreement_over_three_frames')
    if reasons:
        status = 'unknown_or_confounded'
    elif any(abs(x) <= 2 for x in direction):
        status = 'near_zero_no_intervention'
    else:
        status = 'phase_available_for_manual_review'
    return {'status': status, 'direction_lags_by_threshold': direction,
            'position_lags_by_threshold': position, 'reasons': reasons,
            'automatic_intervention_authorized': False,
            'note': 'An observable phase is a necessary observation only, not evidence of remaining-step controllability.'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True)
    p.add_argument('--pose', required=True)
    p.add_argument('--checkpoint', required=True)
    p.add_argument('--protocol', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    module = root/'scripts/timing_metrics.py'
    code_hash = hashlib.sha256(module.read_bytes()).hexdigest()
    if code_hash != FROZEN_HASH:
        raise ValueError('Frozen timing observer changed')
    spec = importlib.util.spec_from_file_location('timing_metrics', module)
    metrics = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metrics)
    edited_raw = json.loads(Path(args.pose).read_text())
    all_rows = {f'{a}:{b}': {} for a, b in WINDOWS}
    for threshold in (.3, .5):
        try:
            source = metrics.load_pose(args.source, threshold)
            edited = metrics.load_pose(args.pose, threshold)
            failure = None
        except ValueError as error:
            failure = str(error)
        for window in WINDOWS:
            rows = {}
            for feature in FEATURES:
                if failure:
                    result = {'status': 'unknown_input_normalization_guard', 'error': failure,
                              'window': window, 'feature': feature, 'reliable_lag_frames': None}
                else:
                    result = metrics.local_diagnostic(source, edited, window, 24, feature)
                rows[feature] = result
            all_rows[f'{window[0]}:{window[1]}'][str(threshold)] = rows
    data = {'checkpoint': args.checkpoint, 'source_pose': str(Path(args.source).resolve()),
            'edited_pose': str(Path(args.pose).resolve()), 'observer_sha256': code_hash,
            'edited_video': edited_raw['video'], 'detector_statistics': edited_raw['statistics'],
            'wrapper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'source_pose_sha256': hashlib.sha256(Path(args.source).read_bytes()).hexdigest(),
            'edited_pose_sha256': hashlib.sha256(Path(args.pose).read_bytes()).hexdigest(),
            'protocol_sha256': hashlib.sha256(Path(args.protocol).read_bytes()).hexdigest(),
            'protocol_text': Path(args.protocol).read_text(), 'diagnostics': all_rows,
            'observability': {window: gate(rows) for window, rows in all_rows.items()},
            'scope': 'frozen pose-based checkpoint observability; no amplitude/action-omission classification and no closed-loop efficacy claim',
            'conservative_missing_position_rule': 'Missing reliable wrist phase makes the direction/position confound check unknown; never count missing as agreement.'}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metrics.clean(data), indent=2, allow_nan=False)+'\n')
    print(json.dumps({'checkpoint': args.checkpoint, 'output': str(output), 'observability': data['observability']}))


if __name__ == '__main__':
    main()
