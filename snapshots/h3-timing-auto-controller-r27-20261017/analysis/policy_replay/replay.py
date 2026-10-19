"""Replay completed observations only. Standard library; never imports inference code."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import time

HERE = Path(__file__).resolve().parent


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


original = module('frozen_policy', HERE / 'frozen/automatic_window_policy.py')
layout = module('frozen_layout', HERE / 'frozen/layout.py')


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def rgb_union(intervals):
    return sorted({i for a, b in intervals for i in range(a, b + 1)})


def bins_for(intervals):
    bins, mapping = set(), []
    for a, b in intervals:
        require(type(a) is int and type(b) is int and 0 <= a <= b < 141,
                'invalid physical interval')
        lo, hi = layout.event_latent_range(a, b, 42)
        bins.update(range(lo, hi))
        mapping.append({'physical_interval': [a, b],
                        'latent_interval_half_open': [lo, hi]})
    return sorted(bins), mapping


def decorate(decision):
    bins, mapping = bins_for(decision['physical_intervals'])
    return dict(decision, latent_bins=bins, mapping=mapping, chosen_full=bool(bins))


def support(selected, reason):
    return decorate({'selected': selected, 'physical_intervals': [r['window'] for r in selected],
                     'active': bool(selected), 'reason': reason})


def global_score(rows):
    measured = [r for r in rows if r['status'] == 'measured']
    for row in measured:
        require(isinstance(row.get('min_gain'), (int, float)) and
                math.isfinite(row['min_gain']), 'measured gain is nonfinite/missing')
        require(row['baseline'] in ('delayed_candidate', 'advanced_candidate'),
                'unexpected measured baseline')
    return {'score': sum(max(0, r['min_gain']) for r in measured) / len(measured)
            if measured else None,
            'measured_count': len(measured), 'total_count': len(rows),
            'advanced_contributors': sum(r['baseline'] == 'advanced_candidate' for r in measured),
            'negative_gain_clipped': sum(r['min_gain'] < 0 for r in measured),
            'status': 'measured' if measured else 'UNKNOWN'}


def lag_edges(current, previous):
    result = []
    for ci, c in enumerate(current):
        for pi, p in enumerate(previous):
            if not original.persistent(c, p):
                continue
            require(set(c['lags']) == set(p['lags']) == {'0.3', '0.5'}, 'lag schema')
            delta = {k: c['lags'][k] - p['lags'][k] for k in ('0.3', '0.5')}
            result.append({'current_representative': ci, 'previous_representative': pi,
                           'current_window': c['window'], 'previous_window': p['window'],
                           'current_feature': c['feature'], 'previous_feature': p['feature'],
                           'same_feature': c['feature'] == p['feature'],
                           'shared_arms': sorted(original.PARTS[c['feature']] & original.PARTS[p['feature']]),
                           'current_lags': c['lags'], 'previous_lags': p['lags'],
                           'signed_delta_frames': delta,
                           'max_absolute_delta_frames': max(abs(v) for v in delta.values()),
                           'any_delta_over_2_descriptive_only': any(abs(v) > 2 for v in delta.values())})
    return result


def component_coverage(groups, selected):
    chosen = {canonical_hash(r) for r in selected}
    result = []
    for i, g in enumerate(groups):
        member_intervals = [r['window'] for r in g['members']]
        rep = g['representative']
        union, rep_rgb = rgb_union(member_intervals), rgb_union([rep['window']])
        ub, _ = bins_for(member_intervals)
        rb, _ = bins_for([rep['window']])
        require(set(rep_rgb) <= set(union) and set(rb) <= set(ub), 'representative outside members')
        result.append({'component': i, 'span': g['span'], 'members': len(g['members']),
                       'representative_window': rep['window'],
                       'representative_feature': rep['feature'],
                       'selected_by_local_policy': canonical_hash(rep) in chosen,
                       'member_rgb_union': union, 'representative_rgb': rep_rgb,
                       'excluded_rgb': sorted(set(union) - set(rep_rgb)),
                       'rgb_coverage_fraction': len(rep_rgb) / len(union),
                       'member_bin_union': ub, 'representative_bins': rb,
                       'excluded_bins': sorted(set(ub) - set(rb)),
                       'bin_coverage_fraction': len(rb) / len(ub)})
    return result


def compare_support(a, b):
    x, y = set(a['latent_bins']), set(b['latent_bins'])
    return {'choice_differs': a['chosen_full'] != b['chosen_full'],
            'support_differs': x != y,
            'only_first_bins': sorted(x-y), 'only_second_bins': sorted(y-x),
            'bin_jaccard': len(x & y)/len(x | y) if x | y else 1.0}


def replay(observers, actual_steps=None):
    policy, previous_reps, previous_global, rows = original.Policy(.5), [], None, []
    for i, ob in enumerate(observers):
        require(ob['physical_index'] == i and ob['status'] in ('measured', 'unknown_visibility'),
                'observer order/status')
        source_rows = ob['windows']
        require(ob['status'] != 'unknown_visibility' or not source_rows,
                'unknown visibility contains candidates')
        local = policy.update(i, source_rows)
        if ob['status'] == 'unknown_visibility':
            local['reason'] = 'unknown_visibility'
        local = decorate(local)
        reps = [g['representative'] for g in local['groups']]
        one = support(reps, 'current_qualifying_representatives' if reps else 'no_current_candidate')
        gs = global_score(source_rows)
        prev = previous_global['score'] if previous_global else None
        mean = (gs['score'] + prev)/2 if gs['score'] is not None and prev is not None else None
        scalar_on = mean is not None and mean > .5
        glob = support(reps if scalar_on else [], 'global_mean_W2_on' if scalar_on else
                       ('global_mean_W2_UNKNOWN' if mean is None else 'global_mean_W2_below_threshold'))
        glob.update(current_global=gs, previous_global=previous_global,
                    two_step_mean=mean, scalar_gate_on=scalar_on)
        if actual_steps is not None:
            actual = actual_steps[i]['decision']
            require(actual_steps[i]['physical_index'] == i, 'actual step order')
            for key, value in local.items():
                require(actual.get(key) == value, 'actual local policy mismatch: '+str(i)+'/'+key)
        rows.append({'index': i, 'observer_status': ob['status'],
                     'local_compatible': local, 'one_step': one, 'global_mean_W2': glob,
                     'compatible_lag_edges': lag_edges(reps, previous_reps),
                     'component_coverage': component_coverage(local['groups'], local['selected']),
                     'local_vs_one_step': compare_support(local, one),
                     'local_vs_global_mean_W2': compare_support(local, glob)})
        previous_reps, previous_global = reps, gs
    names = ('local_compatible', 'one_step', 'global_mean_W2')
    summary = {name: {'active_indices': [r['index'] for r in rows if r[name]['chosen_full']],
                     'bin_step_count': sum(len(r[name]['latent_bins']) for r in rows)} for name in names}
    edges = [e for r in rows for e in r['compatible_lag_edges']]
    summary.update(compatible_edges=len(edges),
                   compatible_edges_over_2=sum(e['any_delta_over_2_descriptive_only'] for e in edges),
                   same_feature_edges_over_2=sum(e['same_feature'] and e['any_delta_over_2_descriptive_only'] for e in edges),
                   component_count=sum(len(r['component_coverage']) for r in rows),
                   components_excluding_member_bins=sum(bool(g['excluded_bins']) for r in rows for g in r['component_coverage']))
    return {'steps': rows, 'summary': summary,
            'interpretation': 'Observed-trajectory decision replay only; alternate decisions were never integrated.'}


def expected_rows():
    result = set()
    for length in (16, 32):
        for start in sorted(set(range(0, 142-length, 4)) | {141-length}):
            for feature in original.PARTS:
                result.add((start, start+length-1, feature))
    require(len(result) == 186, 'window specification')
    return result


def validate_observer(ob, index, protocol):
    require(ob['schema'] == 'r27-whole-timeline-observation-v1' and ob['physical_index'] == index,
            'observer schema/index')
    require(ob['source_pose_sha256'] == protocol['source_pose_sha256'], 'source pose changed')
    require(ob['thresholds'] == [.3, .5], 'confidence thresholds changed')
    if ob['status'] == 'unknown_visibility':
        require(ob['windows'] == [], 'unknown rows')
        return
    require(ob['status'] == 'measured', 'technical failure cannot be UNKNOWN')
    keys = [(r['window'][0], r['window'][1], r['feature']) for r in ob['windows']]
    require(len(keys) == 186 and set(keys) == expected_rows(), 'missing/duplicate scan window')
    for row in ob['windows']:
        require(set(row['measurements']) == {'0.3', '0.5'}, 'confidence inventory')
        for value in row['measurements'].values():
            require(len(value['curve']) == 49, '49 lag inventory required')


def inside(root, rel):
    r = Path(rel)
    require(not r.is_absolute() and '..' not in r.parts, 'unsafe relative path')
    p = root / r
    require(not p.is_symlink() and p.resolve().is_relative_to(root.resolve()), 'outside/symlink input')
    return p


def ingest(archive, protocol):
    archive = Path(archive).resolve()
    gate_path = archive / 'RUN_GATE.json'
    gate = read(gate_path)
    run = gate.get('run_id')
    require(gate.get('passed') is True and run in protocol['allowed_runs'], 'completed registered RUN_GATE required')
    runtime_path = archive / 'RUNTIME_GATE.json'
    runtime = read(runtime_path)
    require(runtime.get('status') == 'pass', 'runtime integrity gate missing')
    inv_path = archive / 'FILE_INVENTORY.json'
    inv = read(inv_path)
    require(gate.get('file_inventory_sha256') == sha(inv_path), 'gate inventory SHA mismatch')
    require(gate.get('runtime') == runtime, 'gate runtime result differs')
    checked = {}

    def checked_json(rel, expected_sha=None):
        p = inside(archive, rel)
        require(rel in inv and sha(p) == inv[rel]['sha256'], 'raw archive hash mismatch: '+rel)
        h = sha(p)
        require(expected_sha is None or h == expected_sha, 'raw declared SHA mismatch: '+rel)
        checked[rel] = h
        return read(p)

    def relative_remote(path):
        p, r = PurePosixPath(path), PurePosixPath(protocol['producer_root_remote'])
        require(p.is_absolute() and p.is_relative_to(r), 'unexpected remote record root')
        return str(p.relative_to(r))

    audit = checked_json('audit/counterfactual/'+run+'.json')
    config = checked_json('configs/protocol.json', protocol['producer_protocol_sha256'])
    checked_json('configs/source.pose.json', protocol['source_pose_sha256'])
    require(run in [c['run_id'] for c in config['cases']], 'protocol run binding')
    history = checked_json('logs/'+run+'_history.json')
    require(history['status']['completed'] is True and history['status']['status_str'] == 'success',
            'Comfy history incomplete')
    require(audit['status'] == 'complete', 'actual controller incomplete')
    c = audit['counterfactual']
    require(len(c['steps']) == len(c['measurements']) == 20, 'twenty actual observations required')
    require(c['actual_euler_updates'] == c['callback_count'] == 20, 'not twenty completed Euler callbacks')
    native = {r['physical_index']: r for r in c['branches'] if r['branch'] == 'native'}
    require(len(native) == 20 and sorted(native) == list(range(20)), 'unique current Native branches required')
    observers, bindings = [], []
    for i, m in enumerate(c['measurements']):
        require(m['physical_index'] == i and m['status'] == 'complete', 'actual observation order/status')
        req = checked_json(relative_remote(m['request_file']), m['request_sha256'])
        res = checked_json(relative_remote(m['response_file']), m['response_sha256'])
        require(req['run_id'] == run and req['physical_index'] == i and req['branch'] == 'native', 'request identity')
        require(res['status'] == 'complete' and res['physical_index'] == i and
                res['request_sha256'] == m['request_sha256'] and res['request_id'] == req['request_id'],
                'response current request binding')
        nr = native[i]
        for key in ('nfe_index', 'seed', 'condition_sha256', 'reference_sha256', 'sigma'):
            require(req[key] == nr[key] == res[key], 'native/observation signature mismatch: '+key)
        require(req['endpoint_file_sha256'] == res['endpoint_file_sha256'] == nr['file_sha256'],
                'native endpoint hash mismatch')
        endpoint_rel = relative_remote(nr['file'])
        require(inv[endpoint_rel]['sha256'] == nr['file_sha256'], 'endpoint not in integrity inventory')
        ob = checked_json(relative_remote(res['observer']['file']), res['observer']['sha256'])
        require(ob == m['observer'], 'embedded observation differs from raw output')
        pose_rel = relative_remote(res['pose']['file'])
        require(inv[pose_rel]['sha256'] == res['pose']['sha256'] == ob['edited_pose_sha256'],
                'pose hash link')
        validate_observer(ob, i, protocol)
        observers.append(ob)
        bindings.append({'index': i, 'native_nfe': nr['nfe_index'],
                         'native_endpoint_sha256': nr['file_sha256'],
                         'condition_sha256': nr['condition_sha256'], 'reference_sha256': nr['reference_sha256'],
                         'native_raw_stream_signatures': nr['raw_stream_signatures'],
                         'request_sha256': m['request_sha256'], 'response_sha256': m['response_sha256'],
                         'observer_sha256': res['observer']['sha256'], 'pose_sha256': res['pose']['sha256']})
    return run, observers, c['steps'], {'archive': str(archive),
            'RUN_GATE_sha256': sha(gate_path), 'RUNTIME_GATE_sha256': sha(runtime_path),
            'FILE_INVENTORY_sha256': sha(inv_path), 'checked_raw_JSON': checked,
            'endpoint_hash_chain': bindings,
            'tensor_bytes_loaded': False, 'tensor_integrity_owner': 'original completed postrun consumer'}


def verify_freeze():
    frozen = read(HERE / 'FREEZE.json')
    for rel, h in frozen['files'].items():
        require(sha(inside(HERE, rel)) == h, 'replay frozen file changed: '+rel)
    return frozen


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--archive', required=True)
    p.add_argument('--output-name', required=True)
    args = p.parse_args()
    verify_freeze()
    require(args.output_name and Path(args.output_name).name == args.output_name,
            'output must be one directory name')
    output = HERE / 'results' / args.output_name
    require(not output.exists(), 'result exists; immutable run, do not overwrite')
    protocol = read(HERE/'PROTOCOL.json')
    # A pure JSON consumer uses one local thread, no remote compute and no inference imports.
    os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                      OPENBLAS_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    with open(protocol['CPU_lock'], 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        start = time.monotonic()
        run, observers, actual, provenance = ingest(args.archive, protocol)
        result = replay(observers, actual)
        # Verify actual raw JSON was not replaced while replaying.
        for rel, h in provenance['checked_raw_JSON'].items():
            require(sha(inside(Path(args.archive), rel)) == h, 'raw changed during replay')
        result.update(run_id=run, protocol_sha256=sha(HERE/'PROTOCOL.json'),
                      freeze_sha256=sha(HERE/'FREEZE.json'), script_sha256=sha(__file__),
                      provenance=provenance, cpu_wall_seconds=time.monotonic()-start,
                      completed_utc_unix=time.time(), actual_local_decisions_exact=True,
                      no_GPU=True, no_pose_or_VAE_or_model=True)
        output.mkdir(parents=True)
        (output/'RESULTS.json').write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
        summary = ['R27 observed-trajectory policy replay', 'run: '+run,
                   'Actual local policy: exact match.',
                   json.dumps(result['summary'], ensure_ascii=False, indent=2),
                   'Only decision/support differences. No alternate Euler rollout or causal video/efficiency claim.',
                   'All 20 original observations and native endpoint hash links retained.']
        (output/'SUMMARY.txt').write_text('\n'.join(summary)+'\n')
        (output/'COMPLETE.json').write_text(json.dumps({'status':'complete',
            'results_sha256':sha(output/'RESULTS.json'),'summary_sha256':sha(output/'SUMMARY.txt')},indent=2)+'\n')
        print(json.dumps({'output':str(output),'run':run,'summary':result['summary']}))


if __name__ == '__main__':
    main()
