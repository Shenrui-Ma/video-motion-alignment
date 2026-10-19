"""Read historical captures; export a bound, CPU-only prompt-control design."""
import csv
import hashlib
import json
from pathlib import Path

BASE = Path('/Users/researcher/DevProjects')
OUT = Path(__file__).resolve().parent
SPECS = [
    ('Native', 'h3-timing-new-actions-native-r38-20261017', 'batch',
     'r38_source_51310_seed2026101701_native', 'r38_source_51310_shared'),
    ('Auto', 'h3-timing-auto-source51310-r40-20261017', 'r40_source51310_seed2026101701_auto',
     'r40_source51310_seed2026101701_auto', 'r40_source51310_shared'),
    ('Manual', 'h3-timing-manual-source51310-r41-20261017',
     'r41_source51310_seed2026101701_manual56to127_6to14',
     'r41_source51310_seed2026101701_manual56to127_6to14', 'r41_source_51310_shared'),
]
BOUND = {}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def bind(path):
    path = Path(path)
    result = {'file': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}
    BOUND[str(path)] = result
    return result


def read(path):
    bind(path)
    return json.loads(Path(path).read_text())


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def stats(x):
    return {k: x.get(k) for k in ('lag_frames', 'lag_seconds', 'error', 'coverage', 'valid_frame_count')}


def main():
    captures = {}
    for label, root_name, archive, run, shared in SPECS:
        root = BASE / root_name
        arc = root / 'analysis/postrun/captured' / archive
        history_file = arc / 'logs' / (run + '_history.json')
        condition_file = arc / 'audit' / (shared + '_conditioning.json')
        noise_file = arc / 'audit' / (run + '_noise.json')
        history, cond, noise = read(history_file), read(condition_file), read(noise_file)
        graph = history['prompt'][2]
        assert history['status']['completed'] and history['status']['status_str'] == 'success'
        assert graph['5']['inputs']['prompt'] == cond['prompt']
        captures[label] = {
            'run_id': run, 'archive': str(arc), 'history': bind(history_file),
            'conditioning_capture': bind(condition_file), 'noise_capture': bind(noise_file),
            'prompt': cond['prompt'], 'input_video': cond['input_video'],
            'native_vae_calls': cond['native_vae_calls'], 'qwen_presentation': cond['qwen_presentation'],
            'target_latent_shapes': cond['target_latent_shapes'],
            'noise_signature': noise['signature'], 'actual_noise_streams': noise['actual_noise_streams'],
            'cache_file': noise['cache_file'], 'actual_graph': graph,
        }
        for gate in ('RUN_GATE.json', 'RUNTIME_GATE.json'):
            if (arc / gate).exists():
                captures[label][gate] = bind(arc / gate)
    assert len({x['prompt'] for x in captures.values()}) == 1
    for key in ('input_video', 'actual_noise_streams', 'noise_signature'):
        assert all(x[key] == captures['Native'][key] for x in captures.values()), key
    p0 = captures['Native']['prompt']
    assert all(x not in p0 for x in ('subject_definitions:', '<Video 1>', '<Picture 1>', '[video editing]'))
    (OUT / 'P0_EXACT.txt').write_text(p0)
    save('HISTORICAL_INPUT_AND_PROMPT_BINDINGS.json', captures)

    r41 = Path(captures['Manual']['archive']) / 'analysis/compare'
    r40 = Path(captures['Auto']['archive']) / 'final'
    fixed_file = r41 / 'FIXED_WINDOWS.json'
    fixed = read(fixed_file)
    previous = read(r40 / 'FIXED_WINDOWS.json')
    for name in ('ACTUAL_PARENT_BINDING.json', 'POSE_BINDINGS.json', 'COMPLETE.json', 'EFFICIENCY.json'):
        bind(r41 / name)
    rows = []
    duplicate_exact = 0
    for window in ([64, 95], [96, 127]):
        for label in ('Native', 'Auto', 'Manual'):
            for confidence in ('0.3', '0.5'):
                diagnostics = fixed['results'][label][confidence]['diagnostics']
                picked = [x for x in diagnostics if x['window'] == window]
                assert len(picked) == 5
                for x in picked:
                    if label != 'Manual':
                        old = [z for z in previous['results'][label.lower()][confidence]['diagnostics']
                               if z['window'] == window and z['feature'] == x['feature']]
                        assert len(old) == 1 and old[0] == x, (label, confidence, window, x['feature'])
                        duplicate_exact += 1
                    rows.append({
                        'method': label, 'confidence': float(confidence),
                        'window_start_inclusive': window[0], 'window_end_inclusive': window[1],
                        'feature': x['feature'], 'status': x['status'], 'flags': x.get('flags', []),
                        'reliable_lag_frames': x.get('reliable_lag_frames'),
                        'measurement': 'QUALIFIED' if x.get('reliable_lag_frames') is not None else 'UNKNOWN',
                        'same_frame': stats(x.get('same_frame', {})),
                        'best_qualified_search': stats(x.get('best', {})),
                        'unqualified_best': stats(x.get('unqualified_best', {})),
                        'relative_error_reduction_after_local_shift': x.get('relative_error_reduction_after_local_shift'),
                        'distinct_lag_relative_gap': x.get('distinct_lag_relative_gap'),
                        'source_file': str(fixed_file),
                        'source_json_pointer': f"/results/{label}/{confidence}/diagnostics/{diagnostics.index(x)}",
                    })
    assert len(rows) == 60 and duplicate_exact == 40
    assert len({(r['method'], r['confidence'], r['window_start_inclusive'], r['feature']) for r in rows}) == 60
    save('SAME_WINDOWS_60_ROWS.json', {'schema': 'legacy-same-window-audit-v1',
        'rows': rows, 'fps': 24, 'positive_lag_means': 'generated action appears later than source',
        'independent_videos': 3, 'independent_source_tasks': 1,
        'r40_r41_duplicate_rows_exact': duplicate_exact,
        'warning': '60 feature/window/confidence diagnostics are not 60 independent experimental samples.'})
    flat = []
    for r in rows:
        y = {k: v for k, v in r.items() if not isinstance(v, dict)}
        y['flags'] = '|'.join(y['flags'])
        for block in ('same_frame', 'best_qualified_search', 'unqualified_best'):
            y.update({block + '_' + k: v for k, v in r[block].items()})
        flat.append(y)
    with (OUT / 'SAME_WINDOWS_60_ROWS.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(flat[0]))
        writer.writeheader(); writer.writerows(flat)
    lines = ['帧号含两端；正数为生成动作晚于参考；UNKNOWN 保留原判定。',
             '每格依次为 Native / Auto / Manual，括号为 confidence 阈值。', '']
    for window in (64, 96):
        lines.append(f'窗口 [{window}, {window + 31}]')
        for feature in ('arm_direction', 'wrist_relative', 'body_xy', 'left_arm_direction', 'right_arm_direction'):
            for conf in (0.3, 0.5):
                match = [r for r in rows if r['window_start_inclusive'] == window and r['feature'] == feature and r['confidence'] == conf]
                values = ['UNKNOWN' if r['reliable_lag_frames'] is None else f"{r['reliable_lag_frames']:+d}" for r in match]
                lines.append(f"  {feature} ({conf}): " + ' / '.join(values))
        lines.append('')
    (OUT / 'SAME_WINDOWS_COMPACT_TABLE.txt').write_text('\n'.join(lines))

    original = BASE / SPECS[0][1]
    assets = {name: bind(original / 'inputs' / name) for name in
              ('source_51310_video.mp4', 'source_51310_portrait.jpg', 'source_51310_provenance.json')}
    graph = captures['Native']['actual_graph']
    p1 = '''subject_definitions:
<Video 1> is the source dance video for this editing task.
<Picture 1> provides the identity and appearance of the target man, Sam Altman.

summary:
[video editing] Replace the dancer in <Video 1> with Sam Altman from <Picture 1>.

retention_analysis:
<Video 1>: partially_preserved - replace the dancer's identity and clothing.
Preserve the dance motions and their timing, the sequence of body poses,
the camera movement, and the background of <Video 1>.
<Picture 1>: use the man's identity for the replacement character.

detailed_description:
Sam Altman from <Picture 1> performs the dance in <Video 1>.
He wears a plain gray long-sleeve shirt and dark trousers.
His motions, their timing and body-pose sequence follow <Video 1>.
The camera movement and background remain those of <Video 1>.

overall_soundscape:
No specific soundscape is requested.

non_diegetic_music:
No specific music is requested.
'''
    (OUT / 'P1_PROPOSED.txt').write_text(p1)
    contract = {
        'schema': 'legacy-source51310-prompt-control-design-v1', 'state': 'CPU_DESIGN_ONLY',
        'source_id': '51310', 'character': 'Sam Altman', 'runs': ['fresh_native_P0', 'fresh_native_P1'],
        'seed': 2026101701, 'assets': assets,
        'geometry': {'width': 1312, 'height': 736, 'frames': 141, 'fps': 24},
        'source_frames': 'all141, source physical times0..140/24',
        'semantic_fps': 2, 'phase_frames': 0, 'sampler': 'Euler20', 'CFG': 1,
        'sigmas': graph['9']['inputs']['sigmas'],
        'sigma_shifts': graph['41']['inputs'],
        'models': {k: graph[k] for k in ('1', '2', '3', '4')},
        'intervention': 'Native for both; zero routed attention blocks; no feedback or time warp',
        'actual_noise_streams': captures['Native']['actual_noise_streams'],
        'original_noise_cache_remote': captures['Native']['cache_file'],
        'noise_signature': captures['Native']['noise_signature'],
        'P0': bind(OUT / 'P0_EXACT.txt'), 'P1': bind(OUT / 'P1_PROPOSED.txt'),
        'P1_provenance': 'Researcher-authored format adaptation; not an official dataset prompt or a new method.',
        'paired_runtime': 'same host, GPU, service, precision, backend, model/checkpoint hashes and numerical configuration',
        'required_equal': ['source media bytes and RGB+PTS', 'reference portrait bytes',
            'raw decoded input video tensor', 'reference VAE prepared frames and encoded latents',
            'Qwen reference frames before joint text/image encoding', 'initial AV noise actual tensor hashes',
            '20 Euler predictions/updates and zero actual routing'],
        'expected_different': ['prompt text', 'text cache key', 'joint text/vision embedding',
            'token tags/sequence length and packed positional metadata', 'x0/trajectory after first model prediction'],
        'text_cache': 'separate P0/P1; never reuse historical clean embedding across different prompts',
        'primary_window_inclusive': [64, 95], 'secondary_window_inclusive': [96, 127],
        'additional_frozen_windows': [[0, 31], [32, 63], [125, 140]],
        'primary_readouts': ['arm_direction', 'left_arm_direction', 'right_arm_direction'],
        'all_reported_features': ['arm_direction', 'wrist_relative', 'body_xy', 'left_arm_direction', 'right_arm_direction'],
        'confidence_thresholds': [0.3, 0.5], 'UNKNOWN_policy': 'preserve and report; no alternate-window substitution',
        'evaluation': 'same frozen R41 full-frame pose/lag protocol; additionally whole-clip overlap scan and visibility coverage; visual identity/edit check before timing claims',
        'independent_source_tasks': 1, 'development_selection': True, 'benchmark_generalization_claim': False,
        'production_status': 'not constructed, not deployed, no GPU launched',
    }
    save('FRESH_P0_P1_CONTROL_DESIGN.json', contract)
    source_files = [
        BASE / SPECS[1][1] / 'extensions/H3EventAudit/__init__.py',
        BASE / 'h3-timing-autoresearch-20261016/semantic_runtime_staged/tests/fixtures/frozen_core/comfy_extras/nodes_minimax_h3.py',
        BASE / 'h3-timing-autoresearch-20261016/semantic_runtime_staged/tests/fixtures/frozen_core/text_encoders/minimax.py',
        BASE / SPECS[2][1] / 'analysis/postrun/evaluate_helpers.py',
        BASE / SPECS[2][1] / 'analysis/postrun/timing_metrics.py',
        BASE / 'h3-timing-ivebench-prompt-pair-r71-20261018/configs/scientific_contract.json',
        BASE / 'h3-timing-ivebench-prompt-pair-r71-20261018/analysis/postrun/verify_pair.py',
        BASE / 'h3-timing-flexiact-prompt-pair-r72-20261018/analysis/postrun/verify_pair.py',
        BASE / SPECS[1][1] / 'configs/parent_core_hashes.json',
        BASE / SPECS[2][1] / 'configs/parent_core_hashes.json',
    ]
    for f in source_files:
        bind(f)
    pin = json.loads((BASE / SPECS[1][1] / 'configs/parent_core_hashes.json').read_text())
    assert sha(source_files[1]) == pin['comfy_extras/nodes_minimax_h3.py']
    save('AUDIT_EVIDENCE.json', {'schema': 'legacy-source51310-audit-evidence-v1',
        'inputs_and_sources': list(BOUND.values()),
        'checks': {'60_unique_rows': True, '40_r40_duplicate_rows_exact': True,
            '3_history_success': True, '3_actual_prompts_equal': True,
            '3_actual_AV_noise_equal': True, '3_actual_raw_input_video_equal': True,
            'P0_missing_six_sections_and_task_text_media_references': True},
        'gpu_started': False, 'old_artifacts_changed': False})
    print(json.dumps({'rows': len(rows), 'r40_duplicate_rows_exact': duplicate_exact,
                      'files_bound': len(BOUND), 'output': str(OUT)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
