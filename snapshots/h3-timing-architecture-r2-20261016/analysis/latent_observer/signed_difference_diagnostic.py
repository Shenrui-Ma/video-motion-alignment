"""Exploratory ablation of magnitude-only temporal-change matching.

Keeps the existing source-only ROI, time geometry, windows and lag search.
Uses signed channel differences to test direction ambiguity. This diagnostic
does not change the registered pose endpoints or provide an online controller.
"""
import json
from pathlib import Path
import numpy as np
import torch
import probe_motion_energy as base

HERE = Path(__file__).resolve().parent


def interpolate_vectorized(times, values, queries):
    upper = np.searchsorted(times, queries, side='right').clip(1, len(times) - 1)
    lower = upper - 1
    weight = ((queries - times[lower]) / (times[upper] - times[lower])).clip(0, 1)
    return values[lower] * (1 - weight[:, None]) + values[upper] * weight[:, None]


def signed_signal(z, roi):
    if tuple(z.shape) != (1, 24, 42, 46, 82):
        raise ValueError(tuple(z.shape))
    centers, times = base.geometry()
    y0, y1, x0, x1 = roi
    diff = z[0, :, 1:] - z[0, :, :-1]
    diff = diff / torch.tensor(np.diff(centers), dtype=z.dtype)[None, :, None, None]
    return times, diff[:, :, y0:y1, x0:x1].permute(1, 0, 2, 3).reshape(41, -1).numpy()


def compact(records):
    return [dict(best=r['best'], margin=r['margin'], boundary=r['boundary_optimum']) for r in records]


def main():
    # Same linear interpolation and endpoint clamping; avoid a Python loop
    # over every channel/pixel for this much wider signed feature vector.
    rng = np.random.default_rng(20261016)
    t = np.arange(7, dtype=float) ** 1.3
    v = rng.normal(size=(7, 11))
    q = np.linspace(-2, t[-1] + 2, 29)
    np.testing.assert_allclose(interpolate_vectorized(t, v, q), base.interpolate(t, v, q), atol=1e-12)
    base.interpolate = interpolate_vectorized
    protocol = {
        'status': 'exploratory ablation after inspecting magnitude-only errors',
        'signal': 'signed adjacent-bin 24-channel differences / physical position-center frame spacing',
        'comparison': 'cosine of flattened signed channel-spatial vector; original lag scan -24..24',
        'roi': 'same frozen source-only upper-body union and full-frame sensitivity',
        'fixed_constraints': ['no source-target channel fitting', 'no threshold or gain search', 'no output-dependent window selection'],
        'limitations': ['appearance contrast may change signed differences', 'early x0 noise affects differences', 'not a calibrated observer', 'same old examples are exploratory, not independent validation'],
    }
    (HERE / 'signed_protocol.json').write_text(json.dumps(protocol, indent=2) + '\n')
    ref = torch.load(HERE / 'reference_video_vae.pt', map_location='cpu', weights_only=True)
    roi = base.source_roi()
    window = [50, 65]
    a = signed_signal(ref, roi)
    checks = {}
    for name, changed in [('identity', ref), ('positive_gain', 3 * ref), ('static_offset', ref + 5)]:
        record = base.scan(a, signed_signal(changed, roi), window)
        checks[name] = record['best']['lag_frames'] == 0
    if not all(checks.values()):
        raise AssertionError(checks)
    report = {'protocol': protocol, 'sanity': checks, 'sources': {}}
    for source in ['05', '07']:
        if source == '05':
            windows = [[50, 65], [69, 81], [80, 92], [99, 111]]
            files = [(mode + '/' + file, base.OLD / 'audit/x0' / ('s05_full_seed1_' + mode + '_x0') / file)
                     for mode in ['native', 'mass'] for file in ['x0_step005.pt', 'x0_step010.pt', 'x0_step015.pt', 'sampler_final.pt']]
        else:
            d = json.loads((HERE / 'source07/results.json').read_text())
            roi = d['source_only_roi_yxyx']
            windows = d['windows']
            ref = torch.load(HERE / 'source07/reference.pt', map_location='cpu', weights_only=True)
            files = [(mode, HERE / 'source07' / (mode + '.pt')) for mode in ['native', 'mass']]
        entries = {}
        for name, path in files:
            data = torch.load(path, map_location='cpu', weights_only=True)
            if data['metadata']['normalization_stage'] != 'after_process_latent_out':
                raise ValueError('normalization mismatch')
            entry = {'file': str(path), 'sha256': base.digest(path), 'regions': {}}
            for label, region in [('source_upper_body_union', roi), ('full_frame_sensitivity', [0, 46, 0, 82])]:
                a = signed_signal(ref, region)
                b = signed_signal(data['video'], region)
                entry['regions'][label] = [base.scan(a, b, w) for w in windows]
            entries[name] = entry
            print(source, name, compact(entry['regions']['source_upper_body_union']))
        report['sources'][source] = {'windows': windows, 'source_only_roi': roi, 'runs': entries}
    (HERE / 'signed_results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
