"""CPU-only sensitivity study using unchanged pinned official IVE MF methods.

Synthetic track perturbations are diagnostics, not generated benchmark results.
The five scoring methods are loaded through AST to avoid importing video I/O or
tracking dependencies that are unused by this cache-only calculation.
"""
from pathlib import Path
import ast
import hashlib
import json
import logging
import time

import numpy as np
import torch
from scipy.interpolate import interp1d
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parent
EVAL = Path('/Users/researcher/DevProjects/h3-ive-followup-quantitative-r97-r99-r100-20261019')
VENDOR = EVAL / 'runtime'
CASE = EVAL / 'audit/recovery_20261019/r107_long_0174/actual_host41/cases/r107_long_0174'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = ROOT / 'RESULT.json'
    if output.exists():
        raise FileExistsError('Keep the previous diagnostic result.')
    for row in json.loads((VENDOR / 'OFFICIAL_SOURCE_SHA.json').read_text()):
        p = VENDOR / 'official_source' / row['path']
        assert p.stat().st_size == row['bytes'] and sha(p) == row['sha256']
    source_file = VENDOR / 'official_source/metrics/fidelity/motion_fidelity.py'
    tree = ast.parse(source_file.read_text())
    definition = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MotionFidelityEvaluator')
    names = {'interpolate_track', 'compute_frame_by_frame_similarity', 'synchronize_videos', '_compute_similarity_from_tracks'}
    definition.body = [n for n in definition.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in definition.body} == names
    code = ast.fix_missing_locations(ast.Module(body=[definition], type_ignores=[]))
    namespace = {'np': np, 'torch': torch, 'interp1d': interp1d, 'linear_sum_assignment': linear_sum_assignment,
                 'logger': logging.getLogger('official-mf-diagnostic')}
    exec(compile(code, str(source_file), 'exec'), namespace)
    cls = namespace['MotionFidelityEvaluator']
    evaluator = cls.__new__(cls)
    torch.set_num_threads(2)

    def read(role):
        folder = CASE / 'tracks' / role
        report = json.loads((folder / 'REPORT.json').read_text())
        assert sha(folder / 'tracks.npz') == report['tracks_sha256']
        with np.load(folder / 'tracks.npz', allow_pickle=False) as z:
            return torch.from_numpy(z['tracks'].copy()), torch.from_numpy(z['visibility'].copy())

    st, sv = read('source')
    nt, nv = read('native')
    gt, gv = read('forced')
    assert st.shape == (1, 145, 100, 2)

    def score(a, av, b, bv):
        return float(evaluator._compute_similarity_from_tracks(a, av, b, bv))

    tick = time.monotonic()
    reproduction = {'native': score(st, sv, nt, nv), 'forced': score(st, sv, gt, gv)}
    for role in ['native', 'forced']:
        previous = json.loads((CASE / 'results' / (role + '.json')).read_text())['motion_fidelity']
        assert abs(reproduction[role] - previous) < 1e-10
    self_score = score(st, sv, st, sv)
    assert abs(self_score - 1.0) < 1e-12
    perturbed = []
    for lag in [-24, -12, -6, 6, 12, 24]:
        indices = torch.clamp(torch.arange(145) - lag, 0, 144)
        perturbed.append({'shift_frames': lag, 'shift_seconds': lag / 24,
                          'score': score(st, sv, st[:, indices], sv[:, indices]),
                          'construction': 'Shift every cached source track and visibility; clamp boundary indices.'})
    translations = []
    for xy in [(40, 0), (0, 40), (80, 0)]:
        translated = st + torch.tensor(xy, dtype=st.dtype)
        translations.append({'translation_pixels': xy, 'score': score(st, sv, translated, sv)})

    # An exact counterexample to preserving physical frame time after visibility
    # compression: the same 121 visible positions occur 24 frames later.
    index = torch.arange(145, dtype=torch.float32)
    trajectory = torch.stack([index, 20 * torch.sin(index / 20)], dim=-1)[None, :, None, :]
    lagged = trajectory[:, torch.clamp(torch.arange(145) - 24, 0, 144)]
    all_visible = torch.ones((1, 145, 1), dtype=torch.bool)
    source_visible = (index < 121)[None, :, None]
    target_visible = (index >= 24)[None, :, None]
    hidden_score = score(trajectory, source_visible, lagged, target_visible)
    assert abs(hidden_score - 1.0) < 1e-12
    synthetic = {'physical_delay_frames': 24, 'physical_delay_seconds': 1.0,
                 'all_visible_score': score(trajectory, all_visible, lagged, all_visible),
                 'different_visibility_intervals_score': hidden_score,
                 'source_visible_frames': [0, 120], 'target_visible_frames': [24, 144],
                 'meaning': 'The official interpolation reindexes visible points by their order, so identical visible paths at different physical times can receive a perfect score.',
                 'scope': 'Constructed trajectory counterexample; not a generated video or observed benchmark failure rate.'}
    result = {'official_commit': '2dcf8900ee65197f43854c76f61c66a32bb8dbfc',
              'official_file': str(source_file), 'official_file_sha256': sha(source_file),
              'script_sha256': sha(__file__), 'loaded_methods': sorted(names),
              'cache_root': str(CASE / 'tracks'), 'cached_score_reproduction': reproduction,
              'source_self_score': self_score, 'synthetic_delays_of_cached_source': perturbed,
              'synthetic_translations_of_cached_source': translations,
              'visibility_counterexample': synthetic,
              'elapsed_seconds': time.monotonic() - tick, 'cuda_initialized': torch.cuda.is_initialized(),
              'interpretation': 'Keep official MF unchanged for comparison; report task completion and visible event timing separately. Synthetic transformations do not measure an editing method.'}
    assert result['cuda_initialized'] is False
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
