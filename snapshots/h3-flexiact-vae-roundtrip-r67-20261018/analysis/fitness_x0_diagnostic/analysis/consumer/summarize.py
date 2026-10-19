"""Aggregate all saved endpoint diagnostics and rebind existing final poses to actual RGB."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
X0 = HERE.parents[1]
R67 = X0.parents[1]
sys.path.insert(0, str(R67 / 'runtime/physical'))
import evaluate

sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
source_path = R67 / 'analysis/fitness_attempt2/prepared/prepared_158.pose.json'
source = json.loads(source_path.read_text())
previous = json.loads((R67 / 'analysis/fitness_attempt2/PHYSICAL.json').read_text())
assert sha(source_path) == previous['poses']['prepared']['sha256']
keys = ['native_step002_attempt1', 'native_step005_attempt1',
        'native_step006_attempt1', 'forced_step006_attempt1']
poses, identities, reports = {}, {}, {}
for key in keys:
    path = HERE / key / 'x0_158.pose.json'
    rec_path = HERE / key / 'PHYSICAL.json'
    rec = json.loads(rec_path.read_text())
    assert rec['status'] == 'complete' and sha(path) == rec['target_pose_sha256']
    assert rec['source_pose_sha256'] == sha(source_path)
    poses[key] = json.loads(path.read_text())
    assert poses[key]['provenance'] == source['provenance']
    identities[key] = {'pose_sha256': sha(path), 'measurement_sha256': sha(rec_path)}
    reports[key] = rec['confidence_results']

metric_root = R67.parent / 'h3-flexiact-forced-metrics-r65-20261018'
gate = json.loads((X0 / 'configs/PAIR_RUNTIME_GATE.json').read_text())
for arm in ['native', 'forced']:
    key = 'final_' + arm
    path = metric_root / 'poses/fitness' / arm / (arm + '.pose.json')
    poses[key] = json.loads(path.read_text())
    assert poses[key]['video']['sha256'] == gate['runs'][arm]['video']['sha256']
    assert poses[key]['provenance'] == source['provenance']
    identities[key] = {'pose_sha256': sha(path), 'gate_video_sha256': poses[key]['video']['sha256']}

result = {'scope': 'fitness predicted x0 evolution and first same-state guidance response',
          'source_pose_sha256': sha(source_path), 'inputs': identities,
          'physical_time_step_ms': 125, 'single_endpoint_diagnostics': reports,
          'same_state_index6': {}, 'final_output_rebound_to_actual_RGB': {}}
for threshold in (.3, .5):
    reference = evaluate.original_time_view(source, threshold)
    for group, methods in [('same_state_index6', ['native_step006_attempt1', 'forced_step006_attempt1']),
                           ('final_output_rebound_to_actual_RGB', ['final_native', 'final_forced'])]:
        views = {key: evaluate.original_time_view(poses[key], threshold) for key in methods}
        rows = []
        for window in evaluate.PROTOCOL['windows_inclusive']:
            for feature in evaluate.FEATURES:
                rows.append({'window': window, 'feature': feature,
                             'diagnostics': {key: evaluate.diagnostic(reference, view, window, feature)
                                             for key, view in views.items()},
                             'common_support': evaluate.common_error(reference, views, window, feature)})
        result[group][str(threshold)] = rows
(HERE / 'SUMMARY.json').write_text(json.dumps(evaluate.metrics.clean(result), ensure_ascii=False, indent=2) + '\n')
print(HERE / 'SUMMARY.json')
