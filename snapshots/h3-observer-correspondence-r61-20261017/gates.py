"""Two CPU correspondence vetoes; neither estimates semantic correctness."""
import numpy as np

CONF = {'arm_direction': 'arm_conf', 'left_arm_direction': 'left_arm_conf',
        'right_arm_direction': 'right_arm_conf'}
CONFIDENCES = ('0.3', '0.5')


def reverse_gate(loaded, row, valid_frames, metric, gain_compare):
    """Search the complete inherited lag range independently in reverse."""
    details, reasons, reverse_lags = {}, [], []
    for confidence in CONFIDENCES:
        lag = row['comparison'][confidence]['proposal_lag']
        window = [int(v + lag) for v in row['window']]
        if not 0 <= window[0] <= window[1] < valid_frames:
            details[confidence] = {'target_window': window, 'status': 'boundary_unknown'}
            reasons.append(confidence + ':boundary_unknown')
            continue
        source, target = loaded['source', confidence], loaded['target', confidence]
        diagnostic = metric.local_diagnostic(target, source, window, 24, row['feature'])
        reverse = diagnostic['reliable_lag_frames']
        detail = {'target_window': window, 'forward_lag': lag,
                  'reverse_diagnostic': diagnostic, 'reverse_lag': reverse}
        details[confidence] = detail
        if reverse is None:
            reasons.append(confidence + ':reverse_unknown')
            continue
        reverse_lags.append(reverse)
        gain = gain_compare(target, source, window, reverse, row['feature'])
        detail['reverse_comparison'] = gain
        detail['cycle_error_frames'] = abs(lag + reverse)
        if gain['status'] != 'measured':
            reasons.append(confidence + ':reverse_gain_unknown')
        elif gain['min_gain'] <= .5:
            reasons.append(confidence + ':reverse_gain_below_threshold')
        if abs(lag + reverse) > 2:
            reasons.append(confidence + ':cycle_mismatch')
        if not ((lag > 2 and reverse < -2) or (lag < -2 and reverse > 2)):
            reasons.append(confidence + ':reverse_sign_or_tolerance')
    if len(reverse_lags) == 2 and abs(reverse_lags[0] - reverse_lags[1]) > 2:
        reasons.append('reverse_confidence_disagreement')
    return {'pass': not reasons, 'reasons': reasons, 'by_confidence': details}


def differences(pose):
    """Backward differences on the original physical grid, with explicit holes."""
    out = dict(pose)
    for feature, confidence in CONF.items():
        values, scores = pose[feature], pose[confidence]
        delta = np.full_like(values, np.nan)
        weights = np.zeros_like(scores)
        adjacent = ((np.diff(pose['frames']) == 1)
                    & np.isclose(np.diff(pose['times']), 1 / pose['raw']['video']['fps'], atol=1e-8, rtol=0))
        valid = np.isfinite(values[1:]).all(-1) & np.isfinite(values[:-1]).all(-1) & adjacent[:, None]
        delta[1:] = np.where(valid[..., None], values[1:] - values[:-1], np.nan)
        weights[1:] = np.where(valid, np.minimum(scores[1:], scores[:-1]), 0)
        out[feature], out[confidence] = delta, weights
    return out


def difference_compare(source, target, window, lag, feature, align):
    # Only pairs wholly inside the source window enter: timestamps a+1..b.
    selected = (source['frames'] >= window[0] + 1) & (source['frames'] <= window[1])
    frames, times = source['frames'][selected], source['times'][selected]
    values, conf = source[feature][selected], source[CONF[feature]][selected]
    fps = source['raw']['video']['fps']
    proposed, proposed_conf = align(target, times + lag / fps, feature)
    rows = []
    for null_lag in range(-2, 3):
        null, null_conf = align(target, times + null_lag / fps, feature)
        valid = np.isfinite(values).all(-1) & np.isfinite(proposed).all(-1) & np.isfinite(null).all(-1)
        weights = np.where(valid, np.minimum(np.minimum(conf, proposed_conf), null_conf).clip(0, 1), 0)
        coverage = float(valid.mean()) if valid.size else 0.
        count = int((weights.sum(-1) > 0).sum())
        row = {'null_lag': null_lag, 'source_pair_end_frames': frames.tolist(),
               'valid_mask': valid.tolist(), 'weights': weights.tolist(), 'coverage': coverage,
               'valid_frames': count, 'valid_vectors': int(valid.sum()), 'expected_vectors': int(valid.size)}
        if coverage < .8 or count < 8 or weights.sum() <= 0:
            row['status'] = 'unknown_support'
        else:
            proposal_cost = float((np.nan_to_num(np.linalg.norm(values - proposed, axis=-1)) * weights).sum() / weights.sum())
            null_cost = float((np.nan_to_num(np.linalg.norm(values - null, axis=-1)) * weights).sum() / weights.sum())
            row.update(status='measured', proposal_cost=proposal_cost, null_cost=null_cost,
                       gain=(null_cost - proposal_cost) / max(null_cost, 1e-8))
        rows.append(row)
    if any(r['status'] != 'measured' for r in rows):
        return {'status': 'unknown_support', 'null_comparisons': rows, 'min_gain': None}
    return {'status': 'measured', 'null_comparisons': rows, 'min_gain': min(r['gain'] for r in rows)}


def difference_gate(deltas, row, align):
    reasons, details = [], {}
    for confidence in CONFIDENCES:
        result = difference_compare(deltas['source', confidence], deltas['target', confidence],
                                    row['window'], row['comparison'][confidence]['proposal_lag'],
                                    row['feature'], align)
        details[confidence] = result
        if result['status'] != 'measured':
            reasons.append(confidence + ':difference_unknown_support')
        elif result['min_gain'] <= .5:
            flat = all(r['null_cost'] <= 1e-8 for r in result['null_comparisons'])
            reasons.append(confidence + (':no_change_evidence' if flat else ':difference_gain_below_threshold'))
    return {'pass': not reasons, 'reasons': reasons, 'by_confidence': details}


def filtered(rows, tests, variant):
    if variant not in ('original', 'A', 'B', 'AB'):
        raise ValueError('unknown fixed variant')
    output = []
    for i, row in enumerate(rows):
        checks = tests.get(str(i))
        rejected = checks is not None and any(not checks[name]['pass'] for name in variant if name in ('A', 'B'))
        output.append(dict(row, status='r61_correspondence_rejected') if rejected else row)
    return output
