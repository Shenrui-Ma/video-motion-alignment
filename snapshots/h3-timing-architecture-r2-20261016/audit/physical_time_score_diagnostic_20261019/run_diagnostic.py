"""Physical-frame trajectory diagnostic using cached tracks only."""
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
PROJECTS = ROOT.parents[2]
EVAL = PROJECTS / 'h3-ive-followup-quantitative-r97-r99-r100-20261019'
OFFICIAL = EVAL / 'runtime/official_source/metrics/fidelity/motion_fidelity.py'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def official_evaluator():
    for row in json.loads((EVAL/'runtime/OFFICIAL_SOURCE_SHA.json').read_text()):
        path = EVAL/'runtime/official_source'/row['path']
        assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256']
    tree = ast.parse(OFFICIAL.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MotionFidelityEvaluator')
    names = {'interpolate_track', 'compute_frame_by_frame_similarity', 'synchronize_videos', '_compute_similarity_from_tracks'}
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in cls.body} == names
    scope = dict(np=np, torch=torch, interp1d=interp1d, linear_sum_assignment=linear_sum_assignment,
                 logger=logging.getLogger('physical-time-diagnostic'))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), str(OFFICIAL), 'exec'), scope)
    return scope['MotionFidelityEvaluator'].__new__(scope['MotionFidelityEvaluator'])


def official_pairs(ev, a, av, b, bv):
    # Match exactly as official MF, but retain raw point IDs for the diagnostic.
    aa, va, bb, vb = ev.synchronize_videos(a, av, b, bv)
    ia = [i for i in range(aa.shape[1]) if va[:, i].mean() > .3 and (va[:, i] > .5).sum() >= 5]
    ib = [i for i in range(bb.shape[1]) if vb[:, i].mean() > .3 and (vb[:, i] > .5).sum() >= 5]
    if not ia or not ib:
        return [], None
    sims = np.array([[ev.compute_frame_by_frame_similarity(aa[:, i], bb[:, j], va[:, i], vb[:, j]) for j in ib] for i in ia])
    ii, jj = linear_sum_assignment(-sims)
    pairs = [(ia[i], ib[j], float(sims[i, j])) for i, j in zip(ii, jj) if sims[i, j] > .3]
    return pairs, float(np.mean([p[2] for p in pairs])) if pairs else 0.0


def diagnose(a, av, b, bv, pairs):
    assert a.shape[0] == b.shape[0] and a.shape[-1] == b.shape[-1] == 2
    n = len(a)
    limit = min(36, (n-1)//4)
    lags = np.arange(-limit, limit+1)
    times = np.arange(limit, n-1-limit)
    minimum = max(5, int(np.ceil(.2*(n-1))))
    details, masks, sa, sb = [], [], [], []
    for i, j, similarity in pairs:
        mask = av[times, i] & av[times+1, i]
        for lag in lags:
            mask = mask & bv[times+lag, j] & bv[times+lag+1, j]
        v = a[times+1, i]-a[times, i]
        variance = float(np.mean(np.sum((v[mask]-v[mask].mean(0))**2, axis=1))) if mask.any() else 0.
        energy = float(np.mean(np.sum(v[mask]**2, axis=1))) if mask.any() else 0.
        selected = bool(mask.sum() >= minimum and variance > 1e-6)
        details.append(dict(source_id=i, target_id=j, official_pair_similarity=similarity,
                            common_adjacent_frames=int(mask.sum()), source_velocity_energy=energy,
                            source_temporal_velocity_variance=variance, selected=selected))
        if selected:
            sa.append(i); sb.append(j); masks.append(mask)
    out = dict(status='UNKNOWN_INSUFFICIENT', frame_count=n, matched_points=len(pairs),
               lag_limit=limit, min_common_frames=minimum, supported_moving_points=len(sa),
               per_point=details, lag_curve=[], candidate_bands=[], local_minima=[])
    if not sa:
        return out
    mask = np.stack(masks, axis=1)
    out['support'] = dict(source_frames=times.tolist(), point_pairs=list(zip(sa, sb)),
                          common_mask=mask.tolist(), observations=int(mask.sum()),
                          fraction_of_all_physical_point_steps=float(mask.sum()/((n-1)*len(pairs))))
    va = a[times+1][:, sa]-a[times][:, sa]
    energy = float(np.mean(np.sum(va[mask]**2, axis=1)))
    variance = sum(d['source_temporal_velocity_variance'] * d['common_adjacent_frames'] for d in details if d['selected']) / mask.sum()
    curves, halves = [], [[], []]
    for lag in lags:
        vb = b[times+lag+1][:, sb]-b[times+lag][:, sb]
        squared = np.sum((va-vb)**2, axis=2)
        mse = float(squared[mask].mean())
        curves.append(mse)
        out['lag_curve'].append(dict(lag_frames=int(lag), velocity_rmse_px_per_frame=float(np.sqrt(mse)), normalized_error=float(mse/variance)))
        for h in range(2):
            hm = mask.copy(); hm[:len(times)//2] &= (h == 0); hm[len(times)//2:] &= (h == 1)
            halves[h].append(float(squared[hm].mean()) if hm.any() else None)
    curves = np.asarray(curves)
    best = int(np.argmin(curves))
    tolerance = max(1e-12, .05*float(curves.max()-curves.min()))
    candidates = np.where(curves <= curves.min()+tolerance)[0]
    groups = np.split(candidates, np.where(np.diff(candidates) > 1)[0]+1)
    out['candidate_bands'] = [[int(lags[g[0]]), int(lags[g[-1]])] for g in groups]
    out['local_minima'] = [dict(lag_frames=int(lags[i]), velocity_mse=float(curves[i])) for i in range(len(lags)) if (i == 0 or curves[i] <= curves[i-1]) and (i == len(lags)-1 or curves[i] <= curves[i+1])]
    out.update(candidate_lag_frames=int(lags[best]), candidate_tolerance_mse=tolerance,
               source_velocity_energy=energy, source_temporal_velocity_variance=float(variance))
    out['split_curves'] = halves
    split = [int(lags[np.argmin(h)]) if all(v is not None for v in h) else None for h in halves]
    out['split_candidate_lags'] = split
    out['spatial'] = {}
    for label, lag in [('zero_lag', 0), ('candidate_lag', int(lags[best]))]:
        delta = (b[times+lag][:, sb]-a[times][:, sa])[mask]
        offset = np.median(delta, axis=0)
        out['spatial'][label] = dict(lag_frames=lag, position_rmse_px=float(np.sqrt(np.mean(np.sum(delta**2, axis=1)))),
                                    median_target_minus_source_translation_px=offset.tolist(),
                                    translation_removed_rmse_px=float(np.sqrt(np.mean(np.sum((delta-offset)**2, axis=1)))))
    reasons = []
    if len(groups) > 1 or any(g[-1]-g[0] > 4 for g in groups): reasons.append('AMBIGUOUS')
    if best in [0, len(lags)-1]: reasons.append('RANGE_BOUNDARY')
    if any(x is None for x in split) or abs(split[0]-split[1]) > 2: reasons.append('NONUNIFORM')
    out['status'] = 'UNKNOWN_'+'_'.join(reasons) if reasons else 'CANDIDATE_LAG_DIAGNOSTIC'
    return out


def load(folder):
    report = json.loads((folder/'REPORT.json').read_text())
    assert report['passed'] and sha(folder/'tracks.npz') == report['tracks_sha256']
    with np.load(folder/'tracks.npz', allow_pickle=False) as z:
        a, v = z['tracks'][0].astype(float), z['visibility'][0].astype(bool)
    assert report['score_frame_indices'] == list(range(len(a)))
    return a, v, dict(file=str(folder/'tracks.npz'), sha256=sha(folder/'tracks.npz'), report_sha256=sha(folder/'REPORT.json'))


def main():
    assert not (ROOT/'RESULT.json').exists()
    tick = time.monotonic()
    ev = official_evaluator()
    t = np.arange(145, dtype=float)
    a = np.stack([t, 20*np.sin(t/20)], axis=-1)[:, None]
    b = a[np.maximum(np.arange(145)-24, 0)]
    av, bv = (t < 121)[:, None], (t >= 24)[:, None]
    artificial = diagnose(a, av, b, bv, [(0, 0, 1.)])
    assert artificial['candidate_lag_frames'] == 24
    # The smooth constructed path leaves a broad low-error band. Preserve the
    # preregistered ambiguity result instead of relaxing the diagnostic rule.
    assert artificial['status'] == 'UNKNOWN_AMBIGUOUS'
    assert artificial['split_candidate_lags'] == [24, 24]
    visible = np.ones((145, 1), dtype=bool)
    translation = diagnose(a, visible, a+np.array([40, 0]), visible, [(0, 0, 1.)])
    assert translation['candidate_lag_frames'] == 0
    assert abs(translation['spatial']['zero_lag']['position_rmse_px']-40) < 1e-10
    assert translation['spatial']['zero_lag']['translation_removed_rmse_px'] < 1e-10
    periodic = np.stack([np.sin(2*np.pi*t/16), np.cos(2*np.pi*t/16)], -1)[:, None]
    repeated = diagnose(periodic, visible, np.roll(periodic, 8, axis=0), visible, [(0, 0, 1.)])
    assert 'AMBIGUOUS' in repeated['status']
    static = diagnose(np.zeros_like(a), visible, np.zeros_like(a), visible, [(0, 0, 1.)])
    assert static['status'] == 'UNKNOWN_INSUFFICIENT'
    empty = diagnose(a, visible, b, np.zeros_like(visible), [(0, 0, 1.)])
    assert empty['status'] == 'UNKNOWN_INSUFFICIENT'
    sets = {
        'R73_short0252': {role: PROJECTS/'h3-ivebench-expanded-metrics-r73-20261018/tracks'/role/'short_0252/attempt1' for role in ['source', 'native', 'forced']},
        'R89_short0358': {role: PROJECTS/'h3-quantitative-evaluation-recovery-20261019/tracks'/role for role in ['source', 'native', 'forced']},
        'R107_long0174': {role: EVAL/'audit/recovery_20261019/r107_long_0174/actual_host41/cases/r107_long_0174/tracks'/role for role in ['source', 'native', 'forced']}}
    real = {}
    for name, paths in sets.items():
        sa, sv, se = load(paths['source']); results = {}
        for role in ['native', 'forced']:
            ta, tv, te = load(paths[role]); pairs, mf = official_pairs(ev, sa, sv, ta, tv)
            official_mf = float(ev._compute_similarity_from_tracks(torch.tensor(sa)[None], torch.tensor(sv)[None], torch.tensor(ta)[None], torch.tensor(tv)[None]))
            assert abs(mf-official_mf) < 1e-12
            result = diagnose(sa, sv, ta, tv, pairs)
            result.update(official_mf_reproduction=official_mf, source_evidence=se, target_evidence=te)
            results[role] = result
        real[name] = results
    result = dict(scope='Constructed trajectory tests and cached-track diagnosis only',
                  script_sha256=sha(__file__), definition_sha256=sha(ROOT/'DEFINITION.json'), official_file=str(OFFICIAL),
                  official_file_sha256=sha(OFFICIAL), synthetic=dict(visibility_delay_24=artificial, fixed_translation_40=translation,
                  periodic_ambiguity=repeated, static=static, no_common_visibility=empty), real=real,
                  cuda_initialized=torch.cuda.is_initialized(), elapsed_seconds=time.monotonic()-tick)
    assert result['cuda_initialized'] is False
    (ROOT/'RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'synthetic_passed':5, 'real': {k: {r:{key:v[key] for key in ['status','candidate_lag_frames','supported_moving_points','split_candidate_lags']} for r,v in rows.items()} for k,rows in real.items()}, 'CUDA_started':False}))


if __name__ == '__main__':
    main()
