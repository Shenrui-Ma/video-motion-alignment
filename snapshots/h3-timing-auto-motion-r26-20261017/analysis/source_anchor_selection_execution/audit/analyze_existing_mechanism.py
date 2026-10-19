"""Post-hoc explanation using stored JSON only; no new pose/threshold/score run."""
from pathlib import Path
import fcntl
import hashlib
import json
import signal
import statistics
import sys
import time

P = Path(__file__).resolve().parents[1]
LOCK = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
FEATURES = ('arm_direction', 'left_arm_direction', 'right_arm_direction')


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def compact_source(row, rank, selected):
    worst = []
    for rival in row.get('rivals', []):
        if rival['known']:
            for c, measurement in rival['measurements'].items():
                worst.append({'rival_start': rival['start'], 'threshold': c,
                              **{k: measurement[k] for k in ('contrast', 'far', 'eps', 'anchor_view_diameter',
                                                            'rival_view_diameter', 'coverage', 'valid_frames', 'weight_sum')}})
    worst.sort(key=lambda x: (x['contrast'], x['rival_start'], x['threshold']))
    overlap = [r['id'] for r in selected
               if not (row['end'] < r['start'] or row['start'] > r['end'])]
    return {k: row.get(k) for k in ('id', 'start', 'end', 'length', 'feature', 'Q', 'V', 'r',
                                    'min_known_contrast', 'source_status', 'known_rivals', 'unknown_rivals',
                                    'conditional_on_observed_rivals', 'own_support', 'rejection_reasons')} | {
        'global_rank_1based': rank, 'overlaps_selected_ids': overlap, 'worst_known_rivals': worst[:3]}


def compact_target(row):
    result = {k: row.get(k) for k in ('id', 'window', 'feature', 'decision', 'baseline', 'status', 'min_gain')}
    result['measurements'] = {}
    for c, d in row['measurements'].items():
        result['measurements'][c] = {k: d.get(k) for k in ('status', 'flags', 'reliable_lag_frames', 'same_frame',
                                                         'best', 'unqualified_best', 'distinct_lag_runner_up',
                                                         'relative_error_reduction_after_local_shift', 'distinct_lag_relative_gap', 'curve')}
    result['comparison'] = row.get('comparison')
    result['same_frame_supported_bone_slots'] = row['same_frame_supported_bone_slots']
    return result


def timeout(_sig, _frame):
    raise TimeoutError('Read-only mechanism analysis limit')


signal.signal(signal.SIGALRM, timeout)
signal.alarm(180)
with LOCK.open('a') as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('CPU lock busy')
        sys.exit(75)
    begun = time.monotonic()
    source_file = P/'results/source05/SOURCE_SELECTION.json'
    source = json.loads(source_file.read_text())
    selected = source['selection']['source_margin']['rows']
    rows = source['candidates']
    ranked = sorted(rows, key=lambda x: (-x['Q'], -x['r'], -x['V'], x['start'], x['length'], FEATURES.index(x['feature'])))
    ranks = {r['id']: i+1 for i, r in enumerate(ranked)}
    by_id = {r['id']: r for r in rows}
    qualified = json.loads((P/'audit/ALL_QUALIFIED_DELAY_ROWS.json').read_text())['rows']
    wanted = {r['id'] for r in selected} | {r['id'] for r in qualified}
    source_feature_summary = {}
    for feature in FEATURES:
        subset = [r for r in ranked if r['feature'] == feature]
        observable = [r for r in subset if r['source_status'] == 'source_observable']
        source_feature_summary[feature] = {
            'candidate_count': len(subset), 'observable_count': len(observable),
            'positive_Q_count': sum(r['Q'] > 0 for r in subset),
            'Q_median_all_candidates': statistics.median(r['Q'] for r in subset),
            'max_Q': max(r['Q'] for r in subset),
            'top5': [compact_source(r, ranks[r['id']], selected) for r in subset[:5]]}
    # Replay only the stored ordering and interval constraint, never recompute Q.
    accepted, trace = [], []
    for r in ranked:
        overlap = [s['id'] for s in accepted if not (r['end'] < s['start'] or r['start'] > s['end'])]
        decision = 'nonpositive_Q' if r['Q'] <= 0 else ('overlap' if overlap else 'accepted')
        trace.append({'rank': ranks[r['id']], 'id': r['id'], 'Q': r['Q'], 'decision': decision, 'blocking_accepted_ids': overlap})
        if decision == 'accepted':
            accepted.append(r)
        if len(accepted) == 3:
            break
    assert {r['id'] for r in accepted} == {r['id'] for r in selected}
    endpoints = {}
    endpoint_files = []
    for index in (3, 4):
        path = P/'results/source05/r27_s05_bad1311_auto'/f'endpoint_{index:03d}.json'
        endpoint_files.append(path)
        result = json.loads(path.read_text())
        table = {r['id']: r for r in result['methods']['full279']['rows']}
        requested = wanted | {'096:24:right_arm_direction', '096:16:right_arm_direction'}
        endpoints[str(index)] = {k: compact_target(table[k]) for k in sorted(requested)}
    # The original lag costs use window-dependent support/weights. From saved
    # per-frame errors alone the shorter and longer support cannot be forced
    # equal. Record exact frame/support evidence; no new common-support rescore.
    overlap_comparison = {}
    for index in (3, 4):
        short = endpoints[str(index)]['096:16:right_arm_direction']
        long = endpoints[str(index)]['096:24:right_arm_direction']
        ss = set(map(tuple, short['same_frame_supported_bone_slots']))
        ls = set(map(tuple, long['same_frame_supported_bone_slots']))
        comparison = {'short_same_frame_slots': len(ss), 'long_same_frame_slots': len(ls),
                      'common_same_frame_slots': sorted(map(list, ss & ls)),
                      'short_only_same_frame_slots': sorted(map(list, ss-ls)),
                      'long_added_same_frame_slots': sorted(map(list, ls-ss)),
                      'fixed_lag_curves': {},
                      'limit': 'Existing per-window costs preserve their original support and weights. A causal equal-support dilution test would require a separately registered rescore.'}
        for c in ('0.3', '0.5'):
            sc = {x['lag_frames']: x for x in short['measurements'][c]['curve']}
            lc = {x['lag_frames']: x for x in long['measurements'][c]['curve']}
            comparison['fixed_lag_curves'][c] = {str(lag): {'short': sc[lag], 'long': lc[lag]} for lag in (-2, -1, 0, 1, 2, 5)}
        overlap_comparison[str(index)] = comparison
    output = {'schema': 'posthoc-source-anchor-mechanism-explanation-v1',
              'source_feature_summary': source_feature_summary, 'greedy_trace_until_three': trace,
              'selected_and_qualified_source_candidates': {k: compact_source(by_id[k], ranks[k], selected) for k in sorted(wanted)},
              'existing_target_diagnostics': endpoints, 'right_arm_96_nested_windows': overlap_comparison,
              'existing_numeric_results_only': True, 'pose_or_threshold_recomputed': False,
              'scope': 'Post-hoc development-case explanation; this does not modify the completed selection comparison',
              'input_hashes': {str(x.relative_to(P)): sha(x) for x in [source_file, *endpoint_files, P/'audit/ALL_QUALIFIED_DELAY_ROWS.json']},
              'analysis_seconds': time.monotonic()-begun}
    with (P/'audit/MECHANISM_EXISTING_JSON.json').open('x') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps({'status': 'complete', 'analysis_seconds': output['analysis_seconds'],
                      'greedy_trace': trace,
                      'feature_summary': {k: {kk: vv for kk, vv in v.items() if kk != 'top5'} for k, v in source_feature_summary.items()},
                      'selected_target_states': {i: {k: {kk: vv for kk, vv in v.items() if kk in ('decision', 'status', 'min_gain', 'baseline')}
                                                       for k, v in e.items() if k in {x['id'] for x in selected}}
                                                 for i, e in endpoints.items()}}, ensure_ascii=False))
