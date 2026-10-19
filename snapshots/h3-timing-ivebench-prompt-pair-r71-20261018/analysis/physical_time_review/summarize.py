"""Read-only aggregation of completed, frozen CPU observations."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    if path.suffix == '.gz':
        with gzip.open(path, 'rt') as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def main():
    protocol = read(ROOT / 'PROTOCOL.json')
    for item in protocol['bindings']:
        assert sha(ROOT / item['relative']) == item['sha256']
    coverage = {}
    for arm, path in [('source', ROOT / 'poses/source.pose.json'),
                      ('p0', ROOT / 'poses/p0/p0.pose.json'),
                      ('p1', ROOT / 'poses/p1/p1.pose.json')]:
        raw = read(path)
        scores = [row['persons'][row['selected_person']]['coco17_score']
                  if row['selected_person'] is not None else [0] * 17
                  for row in raw['frames'][:87]]
        coverage[arm] = {}
        for threshold in (.3, .5):
            coverage[arm][str(threshold)] = {
                'valid_frames': 87,
                'torso_anchor_frames': sum(all(c[j] >= threshold for j in (5, 6, 11, 12)) for c in scores),
                'both_complete_arm_frames': sum(all(c[j] >= threshold for j in range(5, 11)) for c in scores),
                'joint_visible_frame_counts': {str(j): sum(c[j] >= threshold for c in scores) for j in range(5, 13)}}
    scans = {}
    for version in ('original', 'visible'):
        scans[version] = {}
        for arm in ('p0', 'p1'):
            path = ROOT / 'results' / (version + '_' + arm + '.json.gz')
            obj = read(path)['observer']
            rows = obj['windows']
            counts = Counter(row['baseline'] for row in rows)
            scans[version][arm] = {
                'status': obj['status'], 'reasons': obj['reasons'],
                'expected_overlapping_rows': 102, 'actual_rows': len(rows),
                'baseline_counts': dict(counts),
                'lag_histogram_confidence_03': dict(Counter(str(row['measurements']['0.3']['reliable_lag_frames']) for row in rows)),
                'lag_histogram_confidence_05': dict(Counter(str(row['measurements']['0.5']['reliable_lag_frames']) for row in rows)),
                'diagnostic_status_counts_two_confidences': dict(Counter(d['status'] for row in rows for d in row['measurements'].values())),
                'unknown_rows': [{'window': row['window'], 'feature': row['feature'],
                                  'reasons': {c: d.get('flags', [d['status']]) for c, d in row['measurements'].items()}}
                                 for row in rows if row['baseline'] == 'unknown'],
                'scan_seconds': obj['scan_seconds'], 'result_sha256': sha(path)}
    old = read(ROOT / 'results/original_p1.json.gz')['observer']['windows']
    new = read(ROOT / 'results/visible_p1.json.gz')['observer']['windows']
    assert old == new, 'Visible variant changed a fully supported observation'
    physical = read(ROOT / 'results/physical_independent.json.gz')
    result = {
        'schema': 'r71-final-physical-review-summary-v1',
        'sample_count': 1, 'generated_variants': ['P0', 'P1'],
        'overlapping_rows_are_not_independent_samples': True,
        'scope': protocol['scope'], 'coverage': coverage, 'scans': scans,
        'p1_original_and_visible_observer_rows_exactly_equal': True,
        'independent_physical': {
            arm: {'confidence_statuses': {key: row['status'] for key, row in value['confidence_results'].items()},
                  'lag_summary': value['lag_summary']}
            for arm, value in physical['result'].items()},
        'pose_cpu_seconds': {arm: read(ROOT / 'poses' / arm / 'COMPLETE.json')['cpu_seconds']
                            for arm in ('p0', 'p1')},
        'source_cache_exact': sha(ROOT / 'poses/source.pose.json') == protocol['source_pose']['sha256'],
        'all_frozen_numeric_files_unchanged': True, 'gpu_started': False}
    (ROOT / 'SUMMARY.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
