"""Frozen, CPU-only calibration on saved pose arrays, not generated videos."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

import numpy as np

HOME = Path(__file__).resolve().parent
PROTOCOL = HOME / 'protocol.json'
CONF_NAMES = {'arm_direction': 'arm_conf', 'left_arm_direction': 'left_arm_conf',
              'right_arm_direction': 'right_arm_conf', 'wrist_relative': 'wrist_conf',
              'body_xy': 'body_conf'}
BONES = ((5, 7), (7, 9), (6, 8), (8, 10))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pinned_inputs():
    p = json.loads(PROTOCOL.read_text())
    for key, item in p['inputs'].items():
        if sha(item['path']) != item['sha256']:
            raise ValueError(f'Frozen input changed: {key}')
    return p


def transform(xy, conf, variant):
    x, c = xy.copy(), conf.copy()
    family = variant['family']
    audit = {'family': family}
    if family == 'identity':
        pass
    elif family == 'shift':
        delay = variant['known_lag']
        src = np.arange(len(xy)) - delay
        valid = (src >= 0) & (src < len(xy))
        x[:] = np.nan
        c[:] = 0
        x[valid], c[valid] = xy[src[valid]], conf[src[valid]]
        audit['padded_frames'] = np.flatnonzero(~valid).tolist()
    elif family == 'amplitude':
        alpha = variant['alpha']
        audit['bones'] = []
        for a, b in BONES:
            delta = xy[:, b] - xy[:, a]
            lengths = np.linalg.norm(delta, axis=-1)
            theta = np.arctan2(delta[:, 1], delta[:, 0])
            valid = (conf[:, a] >= .3) & (conf[:, b] >= .3)
            valid &= np.isfinite(delta).all(axis=-1) & (lengths > 1e-8)
            win = np.arange(len(xy))
            win = valid & (win >= 50) & (win <= 65)
            if win.sum() < 8:
                raise ValueError(f'Unusable source-only amplitude center for bone {a,b}')
            z = np.exp(1j * theta[win]).mean()
            if abs(z) <= 1e-8:
                raise ValueError(f'Ambiguous circular mean for bone {a,b}')
            mu = float(np.angle(z))
            residual = np.arctan2(np.sin(theta-mu), np.cos(theta-mu))
            new_theta = mu + alpha*residual
            x[:, b] = x[:, a] + lengths[:, None]*np.stack((np.cos(new_theta), np.sin(new_theta)), axis=-1)
            actual = x[:, b] - x[:, a]
            actual_theta = np.arctan2(actual[:, 1], actual[:, 0])
            actual_residual = np.arctan2(np.sin(actual_theta-mu), np.cos(actual_theta-mu))
            audit['bones'].append({'bone': [a, b], 'source_center_radians': mu,
                'mean_resultant': float(abs(z)), 'source_center_valid_frames': int(win.sum()),
                'original_wrapped_branch_jumps': int((np.abs(np.diff(residual)) > np.pi).sum()),
                'max_angular_contract_error': float(np.nanmax(abs(actual_residual-alpha*residual))),
                'max_bone_length_error': float(np.nanmax(abs(np.linalg.norm(actual, axis=-1)-lengths)))})
    elif family == 'linearized':
        for t in range(50, 66):
            u = (t-49)/17
            x[t, [7, 8, 9, 10]] = (1-u)*xy[49, [7, 8, 9, 10]] + u*xy[66, [7, 8, 9, 10]]
        audit['anchors_finite'] = bool(np.isfinite(xy[[49, 66]][:, [7, 8, 9, 10]]).all())
        if not audit['anchors_finite']:
            raise ValueError('Interpolation anchors unavailable; do not repair from other frames')
    elif family == 'missing':
        x[50:66] = np.nan
        c[50:66] = 0
    else:
        raise ValueError(f'Unregistered family {family}')
    return x, c, audit


def basic_correlation(metrics, source, edited, window, feature):
    si, ei, expected = metrics.paired_indices(source, edited, window, 0)
    a, b = source[feature][si], edited[feature][ei]
    valid_joint = np.isfinite(a).all(axis=-1) & np.isfinite(b).all(axis=-1)
    coverage = float(valid_joint.sum() / (expected*a.shape[1]))
    channels = []
    for j in range(a.shape[1]):
        for coord in range(2):
            good = np.isfinite(a[:, j, coord]) & np.isfinite(b[:, j, coord])
            n = int(good.sum())
            av, bv = a[good, j, coord], b[good, j, coord]
            va, vb = (float(np.var(v)) if n else None for v in (av, bv))
            status, r = 'available', None
            if n < 8:
                status = 'unknown_insufficient_pairs'
            elif min(va, vb) <= 1e-12:
                status = 'unknown_constant_channel'
            else:
                r = float(np.corrcoef(av, bv)[0, 1])
            channels.append({'joint_in_feature': j, 'coordinate': coord, 'pairs': n,
                             'source_variance': va, 'edited_variance': vb,
                             'status': status, 'correlation': r})
    available = coverage >= .8 and all(x['status'] == 'available' for x in channels)
    return {'description': 'basic zero-lag Pearson, not full Sync-LoRA',
            'status': 'available' if available else 'unknown', 'coverage': coverage,
            'correlation': float(np.mean([x['correlation'] for x in channels])) if available else None,
            'channels': channels}


def common_support(metrics, source, runs, window, feature):
    """Same formula as pinned compare_runs.py; calibration families kept separate."""
    si = np.flatnonzero((source['frames'] >= window[0]) & (source['frames'] <= window[1]))
    a = source[feature][si]
    cname = CONF_NAMES[feature]
    valid = np.isfinite(a).all(axis=-1)
    weights = source[cname][si].clip(0, 1)
    paired = {}
    for label, edited in runs.items():
        src, dst, _ = metrics.paired_indices(source, edited, window, 0)
        if not np.array_equal(src, si):
            raise ValueError('Common-support inputs have different physical coverage')
        paired[label] = dst
        valid &= np.isfinite(edited[feature][dst]).all(axis=-1)
        weights = np.minimum(weights, edited[cname][dst].clip(0, 1))
    weights = np.where(valid, weights, 0)
    denominator = weights.sum()
    errors = {}
    for label, edited in runs.items():
        distance = np.linalg.norm(a-edited[feature][paired[label]], axis=-1)
        errors[label] = float((np.nan_to_num(distance)*weights).sum()/denominator) if denominator else None
    return {'window': window, 'feature': feature, 'coverage': float(valid.mean()),
            'status': 'usable_exploratory' if valid.mean() >= .8 else 'insufficient_common_support',
            'same_frame_errors': errors}


def synthetic_input():
    n = 141
    t = np.arange(n)
    x = np.zeros((n, 17, 2), dtype=np.float64)
    x[:, 5], x[:, 6], x[:, 11], x[:, 12] = [-.4, 0], [.4, 0], [-.3, 1], [.3, 1]
    for i, (a, b) in enumerate(BONES):
        theta = .6*np.sin(t*.07+i*.3) + .2*np.sin(t*.13)
        x[:, b] = x[:, a] + np.stack((np.cos(theta), np.sin(theta)), axis=-1)
    return x, np.ones((n, 17)), t, {'video': {'fps': 24}}


class CalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = pinned_inputs()
        cls.metrics = import_file('frozen_metrics_test', p['inputs']['metrics']['path'])
        cls.gate = import_file('frozen_gate_test', p['inputs']['combined_gate']['path'])

    def test_frozen_original_selftest(self):
        self.assertTrue(self.metrics.self_test()['passed'])

    def test_identity_is_exact(self):
        x, c, _, _ = synthetic_input()
        y, yc, _ = transform(x, c, {'family': 'identity'})
        np.testing.assert_array_equal(x, y)
        np.testing.assert_array_equal(c, yc)

    def test_shift_sign_and_padding(self):
        x, c, t, raw = synthetic_input()
        for shift in [-12, -8, -4, 4, 8, 12]:
            y, yc, _ = transform(x, c, {'family': 'shift', 'known_lag': shift})
            np.testing.assert_array_equal(y[60+shift], x[60])
            self.assertEqual(int((yc[:, 0] == 0).sum()), abs(shift))
            s = self.metrics.pose_features(x, c, t/24, t, raw, .3)
            e = self.metrics.pose_features(y, yc, t/24, t, raw, .3)
            result = self.metrics.local_diagnostic(s, e, [50, 65], 24, 'arm_direction')
            self.assertEqual(result['reliable_lag_frames'], shift)

    def test_angular_amplitude_preserves_bones(self):
        x, c, _, _ = synthetic_input()
        for alpha in [.5, .25]:
            y, yc, audit = transform(x, c, {'family': 'amplitude', 'alpha': alpha})
            np.testing.assert_array_equal(c, yc)
            np.testing.assert_array_equal(x[:, [5, 6, 11, 12]], y[:, [5, 6, 11, 12]])
            self.assertTrue(all(a['max_bone_length_error'] < 1e-12 for a in audit['bones']))
            self.assertTrue(all(a['max_angular_contract_error'] < 1e-12 for a in audit['bones']))

    def test_linearized_fixed_anchors_and_scope(self):
        x, c, _, _ = synthetic_input()
        y, yc, _ = transform(x, c, {'family': 'linearized'})
        np.testing.assert_array_equal(c, yc)
        np.testing.assert_array_equal(x[:50], y[:50])
        np.testing.assert_array_equal(x[66:], y[66:])
        np.testing.assert_allclose(np.diff(y[49:67, 9], axis=0),
                                   np.broadcast_to((x[66, 9]-x[49, 9])/17, (17, 2)), atol=1e-15)

    def test_missing_rejected_without_silent_zero_fill(self):
        x, c, t, raw = synthetic_input()
        y, yc, _ = transform(x, c, {'family': 'missing'})
        s = self.metrics.pose_features(x, c, t/24, t, raw, .3)
        e = self.metrics.pose_features(y, yc, t/24, t, raw, .3)
        diag = self.metrics.local_diagnostic(s, e, [50, 65], 24, 'arm_direction')
        self.assertIsNone(diag['reliable_lag_frames'])
        self.assertEqual(diag['same_frame']['coverage'], 0)
        corr = basic_correlation(self.metrics, s, e, [50, 65], 'arm_direction')
        self.assertIsNone(corr['correlation'])
        np.testing.assert_array_equal(x[66:], y[66:])

    def test_pearson_affine_blindness_and_constant_unknown(self):
        x, c, t, raw = synthetic_input()
        s = self.metrics.pose_features(x, c, t/24, t, raw, .3)
        e = dict(s)
        e['arm_direction'] = .25*s['arm_direction']+2
        r = basic_correlation(self.metrics, s, e, [50, 65], 'arm_direction')
        self.assertAlmostEqual(r['correlation'], 1)
        e['arm_direction'] = np.zeros_like(s['arm_direction'])
        self.assertIsNone(basic_correlation(self.metrics, s, e, [50, 65], 'arm_direction')['correlation'])

    def test_common_support_includes_missing_denominator(self):
        x, c, t, raw = synthetic_input()
        s = self.metrics.pose_features(x, c, t/24, t, raw, .3)
        y, yc, _ = transform(x, c, {'family': 'missing'})
        e = self.metrics.pose_features(y, yc, t/24, t, raw, .3)
        r = common_support(self.metrics, s, {'identity': s, 'missing': e}, [50, 65], 'arm_direction')
        self.assertEqual(r['coverage'], 0)
        self.assertTrue(all(v is None for v in r['same_frame_errors'].values()))

    def test_missing_wrist_phase_remains_unknown(self):
        rows = {t: {'arm_direction': {'reliable_lag_frames': 8},
                    'wrist_relative': {'reliable_lag_frames': None}} for t in ('0.3', '0.5')}
        self.assertEqual(self.gate.gate(rows)['status'], 'unknown_or_confounded')


def run():
    p = pinned_inputs()
    freeze = json.loads((HOME/'tool_freeze.json').read_text())
    for name, value in freeze['files'].items():
        if sha(HOME/name) != value:
            raise ValueError(f'Tool not frozen: {name}')
    if (HOME/'results.json').exists():
        raise ValueError('Results already exist; refuse to replace a measured run')
    metrics = import_file('frozen_metrics_run', p['inputs']['metrics']['path'])
    gate = import_file('frozen_gate_run', p['inputs']['combined_gate']['path'])
    original = metrics.load_pose(p['inputs']['source']['path'], .3)
    if not np.array_equal(original['frames'], np.arange(141)) or original['raw']['video']['fps'] != 24:
        raise ValueError('Expected original 141 contiguous source05 frames at 24 fps')
    variants = {}
    target_dir = HOME/'transformed_pose_arrays'
    target_dir.mkdir(exist_ok=False)
    for variant in p['variants']:
        x, c, audit = transform(original['xy'], original['conf'], variant)
        path = target_dir/(variant['id']+'.npz')
        np.savez_compressed(path, xy=x, confidence=c, time_s=original['times'], frames=original['frames'])
        variants[variant['id']] = {'definition': variant, 'transform_audit': audit,
            'array_file': str(path), 'array_sha256': sha(path), 'diagnostics': {}, 'observability': {}}
    features_by_threshold = {}
    for threshold in p['confidence_thresholds']:
        key = str(threshold)
        source = metrics.load_pose(p['inputs']['source']['path'], threshold)
        loaded = {}
        for name, item in variants.items():
            with np.load(item['array_file'], allow_pickle=False) as data:
                edited = metrics.pose_features(data['xy'].copy(), data['confidence'].copy(),
                    data['time_s'].copy(), data['frames'].copy(), original['raw'], threshold)
            loaded[name] = edited
            item['diagnostics'][key] = {}
            for window in p['windows']:
                wkey = ':'.join(map(str, window))
                row = {}
                for feature in p['features']:
                    d = metrics.local_diagnostic(source, edited, window, p['max_lag'], feature)
                    d['basic_zero_lag_correlation'] = basic_correlation(metrics, source, edited, window, feature)
                    if 'known_lag' in item['definition']:
                        d['at_known_lag'] = metrics.pair_error(source, edited, window,
                            item['definition']['known_lag'], feature)
                    row[feature] = d
                item['diagnostics'][key][wkey] = row
        features_by_threshold[key] = (source, loaded)
    for name, item in variants.items():
        for window in p['windows']:
            wkey = ':'.join(map(str, window))
            item['observability'][wkey] = gate.gate({t: item['diagnostics'][t][wkey] for t in ('0.3', '0.5')})
    common = {}
    for key, (source, loaded) in features_by_threshold.items():
        common[key] = {family: [common_support(metrics, source, {n: loaded[n] for n in names}, w, f)
            for w in p['windows'] for f in p['features']]
            for family, names in p['common_support_groups'].items()}
    result = {'schema': 'real-source-pose-metric-calibration-result-v1',
        'computed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'protocol_sha256': sha(PROTOCOL), 'tool_freeze_sha256': sha(HOME/'tool_freeze.json'),
        'python': sys.version, 'numpy': np.__version__, 'source_count': 1,
        'scope': 'Synthetic pose-array transforms, no generated or rendered video, no detector rerun',
        'variants': variants, 'common_support': common}
    (HOME/'results.json').write_text(json.dumps(metrics.clean(result), indent=2, allow_nan=False)+'\n')
    lines = ['variant\tthreshold\twindow\tdirection_lag\twrist_lag\tdir_same_error\tdir_best_error\tdir_coverage\tbasic_corr\tcombined_status\tflags']
    for name, item in variants.items():
        for key in ('0.3', '0.5'):
            for wkey, row in item['diagnostics'][key].items():
                d = row['arm_direction']
                vals = [name, key, wkey, d['reliable_lag_frames'], row['wrist_relative']['reliable_lag_frames'],
                    d['same_frame']['error'], d.get('best', {}).get('error'), d['same_frame']['coverage'],
                    d['basic_zero_lag_correlation']['correlation'], item['observability'][wkey]['status'], ','.join(d.get('flags', []))]
                lines.append('\t'.join('unknown' if v is None else str(v) for v in vals))
    (HOME/'all_windows.tsv').write_text('\n'.join(lines)+'\n')
    print('Saved results.json SHA', sha(HOME/'results.json'))
    print('\n'.join([lines[0]]+[x for x in lines[1:] if '\t50:65\t' in x]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test', action='store_true')
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if args.test == args.run:
        parser.error('Select exactly one of --test or --run')
    if args.test:
        unittest.main(argv=[sys.argv[0]], verbosity=2)
    else:
        run()
