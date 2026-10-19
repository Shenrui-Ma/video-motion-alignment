"""CPU replay of stored R81 observations through unchanged prepared R59 Controller."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
R59 = ROOT.parent / 'h3-timing-visible-feedback-r59-execution-20261017'
OUT = ROOT / 'audit/consumer_attempt1'
assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

inherited = [
    'scripts/scan_current_pose.py', 'scripts/arm_features.py',
    'scripts/timing_metrics.py', 'scripts/pairwise_gain.py',
    'scripts/physical_tolerance.py', 'scripts/pose_domain.py',
    'extensions/H3AutomaticWindowRouter/automatic_window_policy.py',
    'extensions/H3AutomaticWindowRouter/delayed_window_policy.py',
    'extensions/H3AutomaticWindowRouter/geometry.py',
]
comparison = []
for rel in inherited:
    a, b = ROOT / 'vendor/visible' / rel, R59 / rel
    row = dict(path=rel, r81_sha256=sha(a), r59_sha256=sha(b))
    row['byte_equal'] = row['r81_sha256'] == row['r59_sha256']
    comparison.append(row)
assert all(row['byte_equal'] for row in comparison)

sys.path[:0] = [str(R59 / 'scripts'), str(R59 / 'extensions')]
from H3AutomaticWindowRouter.selector import Controller
from H3AutomaticWindowRouter.geometry import Geometry

protocol = json.loads((ROOT / 'configs/PROTOCOL.json').read_text())
geometry = Geometry(**protocol['geometry'])
controllers = {arm: Controller(geometry, arm=arm) for arm in ('visible_only', 'visible_fallback')}
results = {arm: [] for arm in controllers}
evidence = []
for index in range(20):
    path = ROOT / 'results/attempt1/visible' / f'step{index:03d}.json.gz'
    with gzip.open(path, 'rt') as stream:
        data = json.load(stream)
    evidence.append(dict(index=index, path=str(path.relative_to(ROOT)), sha256=sha(path)))
    # This wrapper exercises the pure Controller interface; no live IPC receipt is claimed.
    measurement = dict(status='complete', physical_index=index, observer=data['observation'])
    for arm, controller in controllers.items():
        decision = controller.select(index, measurement)
        assert all(decision[key] == value for key, value in data['decision'].items()), (index, arm)
        results[arm].append({key: decision[key] for key in (
            'index', 'active', 'reason', 'physical_intervals', 'selected', 'chosen_full',
            'latent_bins', 'mapping', 'bin_coverage', 'all_unknown', 'reliable_rows',
            'total_rows', 'control_state', 'route_alpha', 'spatial_support', 'blocks')})

extra = [
    'extensions/H3AutomaticWindowRouter/selector.py',
    'extensions/H3AutomaticWindowRouter/dynamic_support.py',
    'extensions/H3AutomaticWindowRouter/core.py',
    'scripts/pose_live_child.py',
]
report = dict(schema='r81-r59-observation-controller-parity-v1', status='complete',
    kind='CPU replay on stored Native observations; no online IPC/model execution',
    original_r81_protocol_sha256=sha(ROOT / 'configs/PROTOCOL.json'),
    r59_source_root=str(R59), geometry=protocol['geometry'], inherited=comparison,
    r59_additional_sources={rel: sha(R59 / rel) for rel in extra}, input_evidence=evidence,
    observations_per_arm=20, all_original_policy_keys_equal=True,
    results=results, ON_indices={arm: [r['index'] for r in rows if r['chosen_full']]
                               for arm, rows in results.items()},
    fallback_indices=[r['index'] for r in results['visible_fallback'] if r['control_state']=='weak_fallback'],
    boundaries=[
        'R81 applies fixed source-based adult centre gate [.40,.75] after largest/IoU selection. Current R59 pose_live_child passes raw selected-person poses without this gate.',
        'R81 uses full107 frames and valid physical indices0..97 at24fps. R59 Geometry/Controller accept these values; current registered R59 cases do not contain short0252.',
        'All inputs are the old Native trajectory. R59 online computes Native first on each current state, observes it, optionally recomputes Full on that same state, then makes one Euler update.',
        'After the first hypothetical ON, later R81 decisions cannot predict a corrected online trajectory.',
        'R81 x0 was generated on host9 and decoded on host41; source/target pose was computed on host9. Cross-host numerical boundaries remain recorded.',
    ], GPU_calls=0)
(OUT / 'R59_IMPLEMENTATION_PARITY.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: report[k] for k in ('status', 'all_original_policy_keys_equal', 'ON_indices', 'fallback_indices')}))
print(json.dumps({'first_ON_mapping': results['visible_only'][2]['mapping'],
                  'first_ON_bin_coverage': results['visible_only'][2]['bin_coverage']}))
