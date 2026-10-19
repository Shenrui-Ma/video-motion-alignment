"""Source-only observer selection. Inputs are frozen pose feature dictionaries.

This module never opens target files and never returns actuator support S.
The source score is an empirical view-relative margin, not an error bound.
"""
import hashlib
import math
import time

import numpy as np

FEATURES = ('arm_direction', 'left_arm_direction', 'right_arm_direction')
CONF = {'arm_direction': 'arm_conf', 'left_arm_direction': 'left_arm_conf',
        'right_arm_direction': 'right_arm_conf'}
BONES = {'arm_direction': (0, 1, 2, 3), 'left_arm_direction': (0, 1),
         'right_arm_direction': (2, 3)}
VIEWS = ('identity', 'flip', 'pad16')
THRESHOLDS = (.3, .5)


def candidates(n=141, lengths=(16, 24, 32), stride=4):
    out = []
    for length in lengths:
        for start in sorted(set(range(0, n-length+1, stride)) | {n-length}):
            if start < 0:
                continue
            for feature in FEATURES:
                out.append({'id': f'{start:03d}:{length:02d}:{feature}',
                            'start': start, 'end': start+length-1,
                            'length': length, 'feature': feature})
    return out


def tie(row):
    return row['start'], row['length'], FEATURES.index(row['feature'])


def support(values, confidence):
    mask = np.isfinite(values).all(axis=-1)
    weights = np.where(mask, np.clip(confidence, 0, 1), 0)
    return mask, weights


def support_record(mask, weights, include_mask=False):
    result = {'coverage': float(mask.mean()) if mask.size else 0.,
              'valid_frames': int((weights.sum(axis=-1) > 0).sum()),
              'valid_slots': int(mask.sum()), 'expected_slots': int(mask.size),
              'weight_sum': float(weights.sum()),
              'weight_min_valid': float(weights[mask].min()) if mask.any() else None,
              'weight_max_valid': float(weights[mask].max()) if mask.any() else None}
    if include_mask:
        result['mask_shape'] = list(mask.shape)
        result['mask_packbits_hex'] = np.packbits(mask.reshape(-1), bitorder='little').tobytes().hex()
        result['weights_le_float64_sha256'] = hashlib.sha256(
            np.asarray(weights, dtype='<f8').tobytes(order='C')).hexdigest()
    result['supported'] = result['coverage'] >= .8 and result['valid_frames'] >= 8 and result['weight_sum'] > 0
    return result


def pair_score(arrays, confidences, start, rival, length):
    """One threshold, one rival; every one of the 27 distances has same support."""
    a = np.stack([arrays[v][start:start+length] for v in VIEWS])
    b = np.stack([arrays[v][rival:rival+length] for v in VIEWS])
    ac = np.stack([confidences[v][start:start+length] for v in VIEWS])
    bc = np.stack([confidences[v][rival:rival+length] for v in VIEWS])
    mask = np.isfinite(a).all(axis=(0, 3)) & np.isfinite(b).all(axis=(0, 3))
    weights = np.where(mask, np.minimum(ac.min(axis=0), bc.min(axis=0)).clip(0, 1), 0)
    result = support_record(mask, weights, include_mask=True)
    result['distance_slots_evaluated'] = 0
    if not result['supported']:
        return result | {'status': 'unknown_support', 'view_pairs': []}
    pairs = []
    for vi, v in enumerate(VIEWS):
        for wi, w in enumerate(VIEWS):
            costs = {}
            for name, x, y in [('far', a[vi], b[wi]), ('anchor_view_error', a[vi], a[wi]),
                               ('rival_view_error', b[vi], b[wi])]:
                d = np.linalg.norm(x-y, axis=-1)
                costs[name] = float((np.nan_to_num(d)*weights).sum()/weights.sum())
            pairs.append({'source_view': v, 'other_view': w, **costs})
    far = min(x['far'] for x in pairs)
    ea = max(x['anchor_view_error'] for x in pairs)
    eu = max(x['rival_view_error'] for x in pairs)
    eps = ea+eu
    return result | {'status': 'measured', 'view_pairs': pairs, 'far': far,
                     'anchor_view_diameter': ea, 'rival_view_diameter': eu,
                     'eps': eps, 'contrast': (far-eps)/max(far+eps, 1e-8),
                     'distance_slots_evaluated': 27*length*a.shape[2]}


def motion_score(identity, row):
    """Adjacent-frame direction change at .5, preserving the 0.8 / 8 gate."""
    s, e, f = row['start'], row['end'], row['feature']
    values = identity[f][s:e+1]
    conf = identity[CONF[f]][s:e+1]
    mask = np.isfinite(values[:-1]).all(-1) & np.isfinite(values[1:]).all(-1)
    weights = np.where(mask, np.minimum(conf[:-1], conf[1:]).clip(0, 1), 0)
    r = support_record(mask, weights)
    r['distance_slots_evaluated'] = int(mask.size)
    r['value'] = (float((np.nan_to_num(np.linalg.norm(values[1:]-values[:-1], axis=-1))*weights).sum()/weights.sum())
                  if r['supported'] else None)
    return r


def score_candidate(loaded, row, n=141):
    start, length, feature = row['start'], row['length'], row['feature']
    out = dict(row, own_support={}, rivals=[], Q=0., V=0., r=0.,
               min_known_contrast=None, source_status='source_unobservable',
               distance_slots_evaluated=0)
    own = []
    for c in THRESHOLDS:
        for view in VIEWS:
            p = loaded[view, c]
            a, w = support(p[feature][start:start+length], p[CONF[feature]][start:start+length])
            r = support_record(a, w)
            out['own_support'][f'{view}:{c:g}'] = r
            own.append(r)
    out['V'] = min(x['coverage'] for x in own)
    out['motion'] = motion_score(loaded['identity', .5], row)
    if not all(x['supported'] for x in own):
        out['rejection_reasons'] = ['self_visibility_below_0.8_or_8_frames']
        return out
    out['source_status'] = 'source_observable'
    for rival in range(n-length+1):
        if abs(rival-start) <= 2:
            continue
        measurements = {}
        for c in THRESHOLDS:
            arrays = {v: loaded[v, c][feature] for v in VIEWS}
            confidences = {v: loaded[v, c][CONF[feature]] for v in VIEWS}
            measurements[f'{c:g}'] = pair_score(arrays, confidences, start, rival, length)
        known = all(x['supported'] for x in measurements.values())
        out['rivals'].append({'start': rival, 'known': known, 'measurements': measurements,
                              'rejection_reasons': [] if known else ['common_view_support_below_0.8_or_8_frames']})
        out['distance_slots_evaluated'] += sum(x['distance_slots_evaluated'] for x in measurements.values())
    known = [x for x in out['rivals'] if x['known']]
    out['known_rivals'] = len(known)
    out['unknown_rivals'] = len(out['rivals'])-len(known)
    out['r'] = len(known)/len(out['rivals']) if out['rivals'] else 0.
    out['conditional_on_observed_rivals'] = bool(out['unknown_rivals'])
    if known:
        out['min_known_contrast'] = min(m['contrast'] for x in known for m in x['measurements'].values())
        out['Q'] = out['V']*out['r']*max(out['min_known_contrast'], 0.)
    out['rejection_reasons'] = ([] if out['Q'] > 0 else
                                ['no_known_rival'] if not known else ['nonpositive_known_rival_margin'])
    return out


def nonoverlap(row, selected):
    return all(row['end'] < other['start'] or row['start'] > other['end'] for other in selected)


def budget(rows):
    frames = set()
    slots = set()
    for row in rows:
        frames.update(range(row['start'], row['end']+1))
        slots.update((t, b) for t in range(row['start'], row['end']+1) for b in BONES[row['feature']])
    return {'K': len(rows), 'length_feature_multiset': sorted((r['length'], r['feature']) for r in rows),
            'physical_frame_union_count': len(frames), 'bone_slot_union_count': len(slots),
            'sum_window_lengths': sum(r['length'] for r in rows),
            'physical_frames': sorted(frames)}


def select(scored, source_sha, n=141, kmax=3):
    selected = []
    ranked = sorted(scored, key=lambda x: (-x['Q'], -x['r'], -x['V'], *tie(x)))
    for row in ranked:
        if row['Q'] > 0 and nonoverlap(row, selected):
            selected.append(row)
        if len(selected) == kmax:
            break
    selected.sort(key=tie)
    slim = lambda r: {k: r[k] for k in ('id', 'start', 'end', 'length', 'feature')}
    out = {'source_margin': {'rows': list(map(slim, selected)), 'feasible': True,
                            'budget': budget(selected)}, 'baselines': {}}
    pool = [r for r in scored if r['source_status'] == 'source_observable']
    for name in ('random_SHA256_20261017', 'even', 'visibility', 'motion'):
        chosen = []
        failed = None
        slot_records = []
        for j, slot in enumerate(selected):
            choices = [r for r in pool if (r['length'], r['feature']) == (slot['length'], slot['feature'])]
            if name == 'random_SHA256_20261017':
                key = lambda r: (hashlib.sha256(f"{source_sha}|20261017|{j}|{r['id']}".encode()).hexdigest(), *tie(r))
            elif name == 'even':
                center = (j+1)*(n-1)/(len(selected)+1)
                key = lambda r: (abs((r['start']+r['end'])/2-center), *tie(r))
            elif name == 'visibility':
                key = lambda r: (-r['V'], *tie(r))
            else:
                choices = [r for r in choices if r['motion']['value'] is not None]
                key = lambda r: (-r['motion']['value'], *tie(r))
            ordered = sorted(choices, key=key)
            match = next((r for r in ordered if nonoverlap(r, chosen)), None)
            slot_records.append({'slot': j, 'length': slot['length'], 'feature': slot['feature'],
                                 'ranked_ids': [r['id'] for r in ordered],
                                 'chosen_id': None if match is None else match['id']})
            if match is None:
                failed = j
                break
            chosen.append(match)
        out['baselines'][name] = {'rows': list(map(slim, chosen)), 'budget': budget(chosen),
                                  'feasible': failed is None, 'failed_slot': failed,
                                  'slot_records': slot_records,
                                  'status': 'matched_budget' if failed is None else 'baseline_budget_infeasible'}
    out['strict_comparison_eligible'] = bool(selected) and all(x['feasible'] for x in out['baselines'].values())
    out['status'] = 'selected' if selected else 'source_selection_not_usable'
    out['observer_A_only'] = True
    out['actuator_S'] = None
    return out


def run_source(loaded, source_sha):
    t = time.monotonic()
    rows = [score_candidate(loaded, r) for r in candidates()]
    scored = time.monotonic()
    selection = select(rows, source_sha)
    return {'schema': 'source-anchor-observer-selection-v1', 'candidates': rows,
            'selection': selection, 'source_scan_seconds': scored-t,
            'selection_seconds': time.monotonic()-scored,
            'source_pair_distance_slots': sum(r['distance_slots_evaluated'] for r in rows),
            'motion_distance_slots': sum(r['motion']['distance_slots_evaluated'] for r in rows),
            'source_scan_includes_pose': False,
            'score_limit': 'eps=0 and far>=1e-8 gives contrast=1 independent of absolute far; empirical relative margin only'}
