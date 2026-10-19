"""Frozen R27 measurements with 24-frame parameters and explicit aggregation.

No source selection, threshold fitting, actuator support, or model invocation.
"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent/'vendor'))
import timing_metrics as m
from pairwise_gain import compare
from physical_tolerance import align
from anchor_selection import BONES, CONF, THRESHOLDS

STATES = ('aligned', 'delayed', 'advanced', 'UNKNOWN')


def classify(row):
    if row['baseline'] == 'aligned':
        return 'aligned'
    if row['status'] == 'measured' and row['min_gain'] > .5:
        return {'delayed_candidate': 'delayed', 'advanced_candidate': 'advanced'}[row['baseline']]
    return 'UNKNOWN'


def descriptor_slots(row):
    return {(t, b) for t in range(row['start'], row['end']+1) for b in BONES[row['feature']]}


def same_frame_support(source, target, row):
    """Descriptive .3/.5 support intersection; never changes R27 decisions."""
    mask = None
    frames = None
    for c in THRESHOLDS:
        s, e = source[c], target[c]
        ix = (s['frames'] >= row['start']) & (s['frames'] <= row['end'])
        values, weights = align(e, s['times'][ix], row['feature'])
        good = np.isfinite(s[row['feature']][ix]).all(-1) & np.isfinite(values).all(-1)
        mask = good if mask is None else mask & good
        frames = s['frames'][ix]
    return {(int(t), BONES[row['feature']][j]) for i, t in enumerate(frames)
            for j in range(mask.shape[1]) if mask[i, j]}


def observe_descriptor(source, target, row):
    start = time.monotonic()
    window = [row['start'], row['end']]
    feature = row['feature']
    ds = {str(c): m.local_diagnostic(source[c], target[c], window, 24, feature) for c in THRESHOLDS}
    lags = [d['reliable_lag_frames'] for d in ds.values()]
    baseline = 'unknown'
    # This block and compare calls preserve scan_current_pose.py's decisions.
    if all(x is not None for x in lags) and abs(lags[0]-lags[1]) <= 2:
        if min(lags) > 2:
            baseline = 'delayed_candidate'
        elif max(lags) < -2:
            baseline = 'advanced_candidate'
        elif all(abs(x) <= 2 for x in lags):
            baseline = 'aligned'
    out = dict(row, window=window, baseline=baseline, measurements=ds)
    if baseline in ('delayed_candidate', 'advanced_candidate'):
        gain = {str(c): compare(source[c], target[c], window, ds[str(c)]['reliable_lag_frames'], feature)
                for c in THRESHOLDS}
        out['comparison'] = gain
        if any(d['status'] == 'unknown' for d in gain.values()):
            out['status'] = 'unknown'
        else:
            out.update(status='measured', min_gain=min(d['min_gain'] for d in gain.values()))
    else:
        out['status'] = 'baseline_'+baseline
    out['decision'] = classify(out)
    out['label'] = 'UNKNOWN'
    out['independent_label_available'] = False
    out['same_frame_supported_bone_slots'] = sorted(map(list, same_frame_support(source, target, row)))
    # Counts actual vector norms requested, including unsupported slots; not FLOPs.
    slots = sum(len(m.paired_indices(source[c], target[c], window, lag)[0])*len(BONES[feature])
                for c in THRESHOLDS for lag in range(-24, 25))
    if 'comparison' in out:
        for report in out['comparison'].values():
            slots += sum(2*row['length']*len(BONES[feature])
                         for x in report['null_comparisons'] if 'proposal_cost' in x)
    out['distance_slots_evaluated'] = slots
    out['measurement_seconds'] = time.monotonic()-start
    return m.clean(out)


def observe(source, target, descriptors):
    t = time.monotonic()
    rows = [observe_descriptor(source, target, row) for row in descriptors]
    return {'rows': rows, 'elapsed_seconds': time.monotonic()-t,
            'distance_slots_evaluated': sum(r['distance_slots_evaluated'] for r in rows),
            'summary': summarize(rows)}


def unknown_observation(descriptors, reasons):
    rows = [dict(r, decision='UNKNOWN', label='UNKNOWN', independent_label_available=False,
                 status='unknown_visibility', reasons=reasons, same_frame_supported_bone_slots=[],
                 distance_slots_evaluated=0) for r in descriptors]
    return {'rows': rows, 'elapsed_seconds': 0., 'distance_slots_evaluated': 0,
            'summary': summarize(rows)}


def summarize(rows):
    counts = {state: sum(r['decision'] == state for r in rows) for state in STATES}
    slots = {state: set().union(*(descriptor_slots(r) for r in rows if r['decision'] == state))
             for state in STATES}
    supported = {state: set().union(*(set(map(tuple, r['same_frame_supported_bone_slots']))
                                     for r in rows if r['decision'] == state)) for state in STATES}
    nominal = set().union(*slots.values())
    observable = set().union(*supported.values())
    return {'descriptor_count': len(rows), 'state_descriptor_counts': counts,
            'UNKNOWN_descriptor_fraction': counts['UNKNOWN']/len(rows) if rows else None,
            'state_nominal_bone_slots': {k: sorted(map(list, v)) for k, v in slots.items()},
            'state_nominal_bone_slot_counts': {k: len(v) for k, v in slots.items()},
            'state_same_frame_supported_bone_slots': {k: sorted(map(list, v)) for k, v in supported.items()},
            'state_same_frame_supported_bone_slot_counts': {k: len(v) for k, v in supported.items()},
            'all_nominal_slot_union_count': len(nominal),
            'same_frame_supported_slot_union_count': len(observable),
            'same_frame_support_fraction': len(observable)/len(nominal) if nominal else None,
            'contains_delayed_evidence': counts['delayed'] > 0,
            'evidence_usable': bool(rows), 'independent_accuracy': None}


def compare_coverage(selected, full):
    result = {}
    for state in STATES:
        a = set(map(tuple, selected['state_nominal_bone_slots'][state]))
        b = set(map(tuple, full['state_nominal_bone_slots'][state]))
        result[state] = {'intersection_slots': len(a & b), 'full_scan_slots_denominator': len(b),
                         'relative_evidence_coverage': len(a & b)/len(b) if b else None,
                         'matching': 'identical physical frame and original bone; no tolerance dilation'}
    return result


def trajectory_summary(endpoints, name):
    if [x['index'] for x in endpoints] != list(range(20)):
        raise ValueError('A trajectory summary requires every ordered endpoint 0..19')
    reports = [e['methods'][name] for e in endpoints]
    prior = set()
    persistence = []
    for index, report in enumerate(reports):
        current = {r['id'] for r in report['rows'] if r['decision'] == 'delayed'}
        persistence.append({'index': index, 'persistently_delayed_anchor_ids': sorted(current & prior)})
        prior = current
    numerator = sum(r['summary']['contains_delayed_evidence'] for r in reports)
    return {'endpoints_with_delayed_evidence': numerator, 'endpoint_denominator': 20,
            'endpoint_delayed_evidence_fraction': numerator/20,
            'endpoint_UNKNOWN_fractions': [r['summary']['UNKNOWN_descriptor_fraction'] for r in reports],
            'persistence': persistence, 'all_labels': 'UNKNOWN', 'accuracy': None,
            'interpretation': 'Same frozen measurement evidence on actual controlled trajectory; no new generation or correctness claim'}
