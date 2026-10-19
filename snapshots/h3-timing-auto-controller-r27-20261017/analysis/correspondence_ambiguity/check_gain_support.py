"""Check whether ambiguous positive correspondences survive frozen gain gates."""
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import pairwise_gain
import timing_metrics
from physical_tolerance import align, CONF


def common_arrays(source, confidence, proposals, nulls):
    pairs = [(source, confidence), *proposals, *nulls]
    valid = np.logical_and.reduce([np.isfinite(x).all(-1) for x, _ in pairs])
    weights = np.where(valid, np.minimum.reduce([c for _, c in pairs]).clip(0, 1), 0)
    result = {'coverage': float(valid.mean()),
              'frames': int((weights.sum(-1) > 0).sum()),
              'weight_sum': float(weights.sum())}
    if result['coverage'] < .8 or result['frames'] < 8 or weights.sum() <= 0:
        return result | {'status': 'unknown_support'}
    def cost(value):
        return float((np.nan_to_num(np.linalg.norm(source - value, axis=-1)) * weights).sum() / weights.sum())
    cp = [cost(x) for x, _ in proposals]
    cn = [cost(x) for x, _ in nulls]
    gain = min((b - a) / max(b, 1e-8) for a in cp for b in cn)
    return result | {'proposal_costs': cp, 'null_costs': cn, 'min_gain': gain,
                     'status': 'measured' if max(cp) <= .5 else 'unknown_residual_shape'}


def common_support(source, edited, window, lags, feature):
    selected = (source['frames'] >= window[0]) & (source['frames'] <= window[1])
    times = source['times'][selected]
    fps = source['raw']['video']['fps']
    return common_arrays(source[feature][selected], source[CONF[feature]][selected],
                         [align(edited, times + d / fps, feature) for d in lags],
                         [align(edited, times + d / fps, feature) for d in range(-2, 3)])


def tests():
    source = np.zeros((16, 2, 2))
    confidence = np.ones((16, 2))
    exact = source.copy()
    shifted = source.copy(); shifted[..., 0] = 1
    result = common_arrays(source, confidence, [(exact, confidence * .7)], [(shifted, confidence * .6)])
    assert result['min_gain'] == 1 and abs(result['weight_sum'] - 19.2) < 1e-10
    equal = common_arrays(source, confidence, [(exact, confidence)], [(exact, confidence)])
    assert equal['min_gain'] == 0
    hidden = exact.copy(); hidden[:4] = np.nan
    assert common_arrays(source, confidence, [(hidden, confidence)], [(shifted, confidence)])['status'] == 'unknown_support'
    bad = shifted * .7
    assert common_arrays(source, confidence, [(exact, confidence), (bad, confidence)], [(shifted, confidence)])['status'] == 'unknown_residual_shape'
    a = common_arrays(source, confidence, [(exact, confidence), (exact + .1, confidence * .8)], [(shifted, confidence)])
    b = common_arrays(source, confidence, [(exact + .1, confidence * .8), (exact, confidence)], [(shifted, confidence)])
    assert a['min_gain'] == b['min_gain'] and a['weight_sum'] == b['weight_sum']
    return {'passed': True, 'tests': 5}


def main():
    lockpath = '/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock'
    with open(lockpath, 'a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: print('CPU_LOCK_BUSY'); return
        test = tests()
        prerequisites = json.loads((HERE / 'RESULT.json').read_text())
        archive = ROOT / 'analysis/postrun/captured/r27_s05_bad1311_auto'
        source_path = archive / 'configs/source.pose.json'
        source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        paths = {int(p.parent.name[4:7]): p for p in archive.glob('audit/observations/step*/observer.json')}
        outputs = []
        for row in prerequisites['records']:
            if not row['both_delay_only']: continue
            path = paths[row['denoising_index']]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == prerequisites['input_sha256'][str(path)]
            observation = json.loads(path.read_bytes())
            pose_path = path.parent / 'pose/native.pose.json'
            assert observation['source_pose_sha256'] == source_hash
            assert hashlib.sha256(pose_path.read_bytes()).hexdigest() == observation['edited_pose_sha256']
            measurements = {}
            for c, value in row['measurements'].items():
                source = timing_metrics.load_pose(source_path, float(c))
                edited = timing_metrics.load_pose(pose_path, float(c))
                lags = value['lags']
                pairs = [pairwise_gain.compare(source, edited, row['window'], d, row['feature']) for d in lags]
                separate_pass = all(p['status'] == 'measured' and p['min_gain'] > .5 for p in pairs)
                common = common_support(source, edited, row['window'], lags, row['feature'])
                measurements[c] = {'separate_pairwise_pass': separate_pass, 'pairwise': pairs,
                                   'all_lags_common': common,
                                   'all_lags_common_pass': common['status'] == 'measured' and common['min_gain'] > .5}
            boundary = any(abs(d) == 24 for m in row['measurements'].values() for d in m['lags'])
            outputs.append({k: row[k] for k in ('denoising_index', 'window', 'feature')} |
                           {'search_boundary_in_set': boundary, 'measurements': measurements,
                            'passes_separate_both': not boundary and all(m['separate_pairwise_pass'] for m in measurements.values()),
                            'passes_common_both': not boundary and all(m['all_lags_common_pass'] for m in measurements.values())})
        result = {'tests': test, 'rows': outputs,
                  'source_pose_sha256': source_hash,
                  'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'prerequisite_sha256': hashlib.sha256((HERE / 'RESULT.json').read_bytes()).hexdigest(),
                  'import_sha256': {str(Path(m.__file__)): hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in (pairwise_gain, timing_metrics)},
                  'scope': '13 correlated posthoc descriptors; actual controller unchanged; sets use heuristic 5% margin and retain boundary UNKNOWN',
                  'passes_separate_both': sum(r['passes_separate_both'] for r in outputs),
                  'passes_common_both': sum(r['passes_common_both'] for r in outputs)}
        (HERE / 'GAIN_SUPPORT_RESULT.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
        print(json.dumps({k: v for k, v in result.items() if k not in ('rows', 'import_sha256')}))


if __name__ == '__main__': main()
