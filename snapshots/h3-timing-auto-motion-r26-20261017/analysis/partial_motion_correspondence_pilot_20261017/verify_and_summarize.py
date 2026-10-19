"""Post-run verification and descriptive exports; never changes frozen results."""
import ast
import csv
import fcntl
import json
import time
from pathlib import Path
import numpy as np
import pilot

HERE = Path(__file__).resolve().parent


def main():
    inputs = pilot.verify()
    with Path(pilot.PROTOCOL['cpu_lock']).open('r') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('CPU_LOCK_BUSY'); return 75
        start = time.perf_counter()
        syntax = []
        for name in ('partial.py', 'pilot.py', 'test_partial.py', 'verify_and_summarize.py'):
            ast.parse((HERE / name).read_text(), filename=name)
            syntax.append(name)
        feature_checks, failures = 0, []
        for item in inputs['cases']:
            for threshold in (.3, .5):
                for kind in ('source', 'target'):
                    candidate = pilot.load_pose(item[kind], threshold, item['last_frame'])
                    try:
                        original = pilot.baseline.load_pose(item[kind], threshold)
                    except ValueError as error:
                        failures.append({'case': item['id'], 'kind': kind, 'threshold': threshold, 'error': str(error)})
                        continue
                    count = item['last_frame'] + 1
                    for name, (score, _) in pilot.FEATURES.items():
                        np.testing.assert_allclose(candidate[name], original[name][:count], rtol=0, atol=0, equal_nan=True)
                        np.testing.assert_allclose(candidate[score], original[score][:count], rtol=0, atol=0)
                    feature_checks += 1
        path_checks, real_rows, synthetic_rows, runtimes = 0, [], [], []
        for attempt in sorted((HERE / 'results').iterdir()):
            complete = json.loads((attempt / 'COMPLETE.json').read_text())
            runtimes.append({'attempt': attempt.name, **complete})
            if attempt.name.startswith('tests'):
                assert complete['success'] is True
                continue
            for file in sorted(attempt.glob('*.npz')):
                with np.load(file) as archive:
                    pairs, cost = archive['pairs'], archive['cost']
                    assert pairs.ndim == 2 and pairs.shape[1] == 2
                    assert (np.diff(pairs, axis=0) >= 0).all()
                    assert np.isfinite(cost[tuple(pairs.T)]).all()
                    assert len(np.unique(pairs, axis=0)) == len(pairs)
                    path_checks += 1
                row = json.loads(file.with_suffix('.json').read_text())
                flat = {key: row.get(key) for key in ('case', 'feature', 'confidence_threshold', 'drop_cost_each_side',
                    'matched_geometry_residual_source_mean', 'same_frame_geometry_residual',
                    'source_unmatched_fraction', 'target_unmatched_fraction', 'source_unobservable_fraction', 'target_unobservable_fraction',
                    'lag_median_frames', 'lag_q25_q75_frames', 'max_sources_per_target', 'max_targets_per_source')}
                if attempt.name.startswith('real'):
                    whole = row['window_summaries'][0]['constant_lag24']
                    flat['whole_clip_original_reliable_lag24'] = whole['reliable_lag_frames']
                    flat['whole_clip_original_status'] = whole['status']
                    real_rows.append(flat)
                else:
                    flat.update(row['truth'])
                    if row['drop_cost_each_side'] == .25:
                        center = next(x for x in row['window_summaries'] if x['window'] == [64, 95])
                        flat['center64_95_lag24'] = center['constant_lag24']['reliable_lag_frames']
                        flat['center64_95_lag48'] = center['constant_lag48']['reliable_lag_frames']
                        flat['center64_95_partial_lag'] = center['lag_median']
                    synthetic_rows.append(flat)
        # Output order follows declared cases, never performance.
        real_rows.sort(key=lambda x: (pilot.PROTOCOL['real_cases_order'].index(x['case']), x['confidence_threshold'], x['feature']))
        synthetic_rows.sort(key=lambda x: (pilot.PROTOCOL['synthetic']['cases'].index(x['case']), x['drop_cost_each_side']))
        for name, rows in (('REAL_SUMMARY', real_rows), ('SYNTHETIC_SUMMARY', synthetic_rows)):
            pilot.save(HERE / (name + '.json'), rows)
            fields = list(dict.fromkeys(key for row in rows for key in row))
            with (HERE / (name + '.csv')).open('x') as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader(); writer.writerows(rows)
        result = {'syntax_checked': syntax, 'input_files_sha_verified': 2 * len(inputs['cases']),
                  'exact_feature_comparisons': feature_checks, 'original_loader_errors': failures,
                  'path_invariant_checks': path_checks, 'synthetic_rows': len(synthetic_rows),
                  'real_rows': len(real_rows), 'runtimes': runtimes, 'audit_seconds': time.perf_counter() - start,
                  'code_freeze_sha256': pilot.sha(HERE / 'FREEZE.json'), 'new_diagnostic_is_not_original_benchmark_metric': True}
        pilot.save(HERE / 'VERIFICATION.json', result)
        print(json.dumps({k: v for k, v in result.items() if k != 'runtimes'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
