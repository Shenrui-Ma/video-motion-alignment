import argparse
import copy
import json
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
TEMPLATE = Path('/Users/researcher/DevProjects/h3-fast-screen-20261008/configs/firefly_notsin107_original.json')
AUDIT = '/data5/researcher/h3_runs/fast_motion_followup_20261013/audit'
SEEDS = (2026101301, 2026101302)


def prompt_for(meta, arm):
    basic = meta['prompts']['A']
    if arm == 'noop':
        basic = 'Reproduce <Video 1> faithfully. Preserve the original person, clothing, objects, background, camera, every action, motion path, speed and timing. Make no appearance changes.'
    detail = 'Preserve the original source actions, their order, timing and rhythm. Keep the source playback speed, camera and duration.'
    if arm == 'b':
        detail += ' ' + meta['prompts']['B_addition']
    return ('subject_definitions:\n<Video 1>: The complete source video to edit and the reference for all original motion.\n'
            'summary:\n[video editing] ' + basic + '\n'
            'retention_analysis:\n<Video 1>: Preserve source motion, action timing, person, objects, camera and background; apply only the requested appearance change.\n'
            'detailed_description:\n' + detail + '\n'
            'overall_soundscape:\nNo speech or added sound effects are requested.\n'
            'non_diegetic_music:\nNone.\n')


def make_graph(meta, arm, seed_index, *, steps=20, fps=2, phase=0, diagnostics=False, suffix=''):
    case = meta['clip_id']
    run = f'{case}_{arm}_s{seed_index + 1}{suffix}'
    g = json.loads(TEMPLATE.read_text())
    # A100 admission benchmark validated native SDPA; the legacy Sage package
    # cannot implement the intended H3 patch on this host. Freeze this backend.
    del g['42']
    del g['43']
    g['41']['inputs']['model'] = ['1', 0]
    del g['21']
    g['22']['inputs']['file'] = case + '.mp4'
    g['5'] = {'class_type': 'H3EventAuditReference', 'inputs': {
        'clip': ['2', 0], 'vae': ['3', 0], 'ref_video': ['23', 0],
        'prompt': prompt_for(meta, arm), 'width': 1312, 'height': 736, 'length': 107,
        'audit_dir': AUDIT, 'run_id': run, 'semantic_fps': fps, 'phase_frames': phase}}
    g['6'] = {'class_type': 'H3EventAuditNoise', 'inputs': {
        'noise_seed': SEEDS[seed_index], 'audit_dir': AUDIT, 'run_id': run,
        'pair_id': f'{case}_s{seed_index + 1}'}}
    sigmas = [12 * ((steps - i) / steps) / (1 + 11 * ((steps - i) / steps)) for i in range(steps + 1)]
    g['9']['inputs']['sigmas'] = ','.join(format(x, '.12g') for x in sigmas)
    g['14']['inputs']['filename_prefix'] = run
    if diagnostics:
        g['30'] = {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 3], 'vae': ['3', 0]}}
        g['31'] = {'class_type': 'CreateVideo', 'inputs': {'images': ['30', 0], 'fps': 24.0, 'bit_depth': 8}}
        g['32'] = {'class_type': 'SaveVideo', 'inputs': {'video': ['31', 0], 'filename_prefix': case + '_reference_vae_reconstruction', 'format': 'mp4', 'codec': 'h264', 'codec.encoding': 're-encode', 'codec.encoding.crf': 16.0}}
        g['33'] = {'class_type': 'CreateVideo', 'inputs': {'images': ['5', 2], 'fps': 24.0, 'bit_depth': 8}}
        g['34'] = {'class_type': 'SaveVideo', 'inputs': {'video': ['33', 0], 'filename_prefix': case + '_actual_prepared_reference', 'format': 'mp4', 'codec': 'h264', 'codec.encoding': 're-encode', 'codec.encoding.crf': 16.0}}
    return run, g


def save(run, graph):
    p = LAB / 'configs' / (run + '.json')
    encoded = json.dumps(graph, ensure_ascii=False, indent=2) + '\n'
    if p.exists() and p.read_text() != encoded:
        raise RuntimeError(f'Refusing to overwrite changed graph: {p}')
    p.write_text(encoded)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('metadata', type=Path)
    parser.add_argument('--benchmark', action='store_true')
    args = parser.parse_args()
    meta = json.loads(args.metadata.read_text())
    jobs = []
    if args.benchmark:
        run, graph = make_graph(meta, 'a', 0, steps=2, diagnostics=True, suffix='_benchmark2')
        save(run, graph)
        jobs.append(run)
    else:
        for seed_index in range(2):
            for arm in ('a', 'b'):
                run, graph = make_graph(meta, arm, seed_index, diagnostics=(arm == 'a' and seed_index == 0))
                save(run, graph)
                jobs.append(run)
    print(json.dumps({'jobs': jobs}))
