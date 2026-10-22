"""CPU sensitivity audit of the unmodified official MF functions."""
import ast
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.interpolate import interp1d
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'runtime/official_source/metrics/fidelity/motion_fidelity.py'
OUT = ROOT / 'audit/official_mf_time_calibration'


class ArrayTensor:
    def __init__(self, value):
        self.value = np.asarray(value)

    def squeeze(self, axis):
        return ArrayTensor(self.value.squeeze(axis))

    def cpu(self):
        return self

    def numpy(self):
        return self.value


def official_evaluator():
    tree = ast.parse(SOURCE.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'MotionFidelityEvaluator')
    names = {'interpolate_track', 'compute_frame_by_frame_similarity',
             'synchronize_videos', '_compute_similarity_from_tracks'}
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in methods} == names
    module = ast.Module(body=[ast.ClassDef(name='OfficialFunctions', bases=[],
                                          keywords=[], body=methods, decorator_list=[])],
                        type_ignores=[])
    namespace = {'np': np, 'interp1d': interp1d,
                 'linear_sum_assignment': linear_sum_assignment}
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), 'exec'), namespace)
    return namespace['OfficialFunctions']()


def score(evaluator, first, first_vis, second, second_vis):
    return float(evaluator._compute_similarity_from_tracks(
        *(ArrayTensor(a[None]) for a in (first, first_vis, second, second_vis))))


def main():
    evaluator = official_evaluator()
    length, offset, visible_length = 32, 8, 16
    first = np.zeros((length, 1, 2))
    second = np.zeros_like(first)
    first_vis = np.zeros((length, 1))
    second_vis = np.zeros_like(first_vis)
    trajectory = np.stack((np.arange(visible_length), np.zeros(visible_length)), axis=1)
    first[:visible_length, 0] = trajectory
    first_vis[:visible_length] = 1
    second[offset:offset + visible_length, 0] = trajectory
    second_vis[offset:offset + visible_length] = 1
    value = score(evaluator, first, first_vis, second, second_vis)
    common = (first_vis[:, 0] > .5) & (second_vis[:, 0] > .5)
    common_error = np.linalg.norm(first[common, 0] - second[common, 0], axis=1)
    assert abs(value - 1.) < 1e-12
    assert np.all(common_error == offset)
    result = {
        'official_source': str(SOURCE),
        'official_source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'method': 'Compile exactly four original AST method bodies; only the tensor container is replaced with a NumPy wrapper. No scoring arithmetic changed.',
        'synthetic_visibility_shift': {
            'frames': length, 'visible_frames': visible_length, 'true_shift_frames': offset,
            'source_visible_interval': [0, 15], 'target_visible_interval': [8, 23],
            'official_MF': value,
            'same_physical_time_common_visible_mean_position_error': float(common_error.mean()),
            'interpretation': 'The official interpolator discards invisible frames and spreads the remaining visible positions uniformly over the full sequence. Identical visible paths at different physical times can therefore receive MF=1.'
        },
        'actual_short_0252': {},
        'scope': 'Metric sensitivity diagnostic. This synthetic example does not prove the observed real-case score is caused by visibility interpolation.'
    }
    caches = {}
    for method in ('source', 'native', 'forced'):
        path = ROOT / 'tracks' / method / 'short_0252/attempt1/tracks.npz'
        with np.load(path) as data:
            tracks, visibility = data['tracks'][0].copy(), data['visibility'][0].copy()
            caches[method] = (tracks, visibility)
            valid_counts = (visibility > .5).sum(axis=0)
            time_displacements = []
            for column in visibility.T:
                visible = np.flatnonzero(column > .5)
                if len(visible) >= 2:
                    remapped = np.linspace(0, len(column) - 1, len(visible))
                    time_displacements.append(float(np.max(np.abs(visible - remapped))))
            result['actual_short_0252'][method] = {
                'archive': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'arrays': {name: list(data[name].shape) for name in data.files},
                'fully_visible_tracks': int(np.sum(valid_counts == len(visibility))),
                'partially_visible_tracks': int(np.sum((valid_counts > 0) & (valid_counts < len(visibility)))),
                'median_max_interpolation_time_displacement_frames': float(np.median(time_displacements))
            }
    for method in ('native', 'forced'):
        actual = score(evaluator, *caches['source'], *caches[method])
        recorded = json.loads((ROOT / 'results/short_0252' / f'{method}_source1_target1.json').read_text())['motion_fidelity']
        assert abs(actual - recorded) < 1e-12
        result['actual_short_0252'][method]['official_MF_reproduced'] = actual
    full_visible = np.ones((length, 1))
    wave = np.zeros_like(first)
    wave[:, 0, 0] = np.sin(np.arange(length) / 4.)
    delayed = np.roll(wave, offset, axis=0)
    full_visible_score = score(evaluator, wave, full_visible, delayed, full_visible)
    assert full_visible_score < .99
    result['fully_visible_shift_control'] = {
        'shift_frames': offset, 'official_MF': full_visible_score,
        'interpretation': 'With full visibility, frame timing differences do affect the official score.'
    }
    OUT.mkdir(exist_ok=True)
    (OUT / 'RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
