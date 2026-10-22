"""Bounded archive audit: three completed component controls plus benchmark intake histories."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
OUT = ROOT / 'prior_component_controls'


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(p):
    return json.loads(p.read_text())


def main():
    OUT.mkdir(exist_ok=True)
    specs = [('r2', 'h3-timing-architecture-r2-20261016', 'r2_s05_dynamic_6to14', 'dynamic'),
             ('r2', 'h3-timing-architecture-r2-20261016', 'r2_s05_static_6to14', 'static'),
             ('r3', 'h3-timing-spatial-r3-20261016', 'r3_s05_dynamic_6to14', 'dynamic')]
    rows = []
    for round_id, name, run, arm in specs:
        pose = BASE / name / 'analysis/pose'
        prov = pose / 'pilot' / (run + '_provenance')
        manifest = read(prov / 'archive_manifest.json')
        graph = read(prov / 'config.json')
        history = read(prov / 'history.json')
        router = read(prov / 'router_audit.json')
        video = pose / 'raw' / manifest['relative_video']
        quality_path = pose / 'pilot' / (run + '.quality_review.json')
        quality = read(quality_path)
        actual = history['prompt'][2]
        assert graph == actual
        assert history['status']['completed'] and history['status']['status_str'] == 'success'
        assert sha(prov / 'config.json') == manifest['config_sha256']
        assert sha(prov / 'history.json') == manifest['history_sha256']
        assert sha(video) == manifest['video_sha256'] == quality['video_sha256']
        assert history['outputs']['14']['images'][0] == manifest['history_output']
        assert router['run_id'] == run and router['mode'] == actual['50']['inputs']['mode']
        assert router['completed_forward_calls'] == 20 and router['routed_calls'] == 450
        gate_path = pose / 'within_round_actual_input_gate.json'
        gate = read(gate_path)
        gr = next(x for x in gate['rows'] if x['run_id'] == run)
        assert gr['passed'] and all(gr['checks'].values())
        compact = read(pose / 'compact_summary.json')
        common = {}
        for threshold in ['0.3', '0.5']:
            pair_path = pose / 'pairs' / ('four_arms_threshold' + threshold + '.json')
            pair = read(pair_path)
            r = next(x for x in pair['results'] if x['window'] == [50, 65] and x['feature'] == 'arm_direction')
            common[threshold] = {
                'path': str(pair_path), 'sha256': sha(pair_path),
                'common_valid_fraction': r['common_valid_fraction'], 'status': r['status'],
                'same_frame_error': {k: v['same_frame_error_on_common_support'] for k,v in r['runs'].items()},
                'primary_lag_frames': compact['threshold_specific_gates'][threshold]['primary_lag'],
            }
        bound = [prov/'archive_manifest.json', prov/'history.json', prov/'config.json', prov/'router_audit.json', quality_path, gate_path, pose/'compact_summary.json']
        rows.append({
            'run_id': run, 'round': round_id, 'benchmark': 'private development source05, not FlexiAct/IVEBench',
            'task': 'Replace dancer by Sam Altman portrait while preserving source room/actions',
            'source_file': actual['22']['inputs']['file'], 'image_file': actual['21']['inputs']['image'],
            'prompt': actual['5']['inputs']['prompt'],
            'source_video_sha256': manifest['source_video_sha256'],
            'operator': actual['50']['inputs'], 'producer_host': manifest['producer_host'],
            'history_success': True, 'history_graph_exact_config': True,
            'actual_noise_conditions_same_round_gate_passed': True,
            'video': {'path': str(video), 'sha256': sha(video), 'bytes': video.stat().st_size, 'expected_geometry': manifest['expected_geometry']},
            'NFE': router['completed_forward_calls'], 'routed_calls': router['routed_calls'],
            'timing': common, 'quality_review': quality,
            'source_identity_retention_reduction': 'UNKNOWN: no exact-identity or full-video review was performed in these records',
            'evidence': [{'path': str(p), 'sha256': sha(p)} for p in bound],
        })
    scans = []
    modes = Counter()
    unique = set()
    found = []
    scopes = []
    for root in sorted(BASE.iterdir()):
        if not root.is_dir() or not root.name.startswith('h3-') or not any(w in root.name for w in ['ive', 'flexiact']):
            continue
        inc = root / 'incoming'
        if not inc.is_dir():
            continue
        paths = sorted(inc.glob('**/*history*.json'))
        if paths:
            scopes.append({'root': str(root), 'history_files': len(paths)})
        for p in paths:
            d = read(p)
            records = [d] if 'prompt' in d else list(d.values())
            for h in records:
                if not isinstance(h, dict) or 'prompt' not in h:
                    continue
                status = h.get('status', {})
                graph = h['prompt'][2]
                record_modes = [n['inputs']['mode'] for n in graph.values() if isinstance(n, dict) and n.get('class_type') == 'H3TemporalRouter']
                success = status.get('completed') is True and status.get('status_str') == 'success'
                scans.append({'path': str(p), 'sha256': sha(p), 'prompt_id': h['prompt'][1], 'success': success, 'H3TemporalRouter_modes': record_modes})
                if success and h['prompt'][1] not in unique:
                    unique.add(h['prompt'][1]); modes.update(record_modes or ['NO_H3TemporalRouter'])
                    if set(record_modes) & {'dynamic_residual','static_component'}:
                        found.append(str(p))
    result = {'schema': 'actual-component-controls-history-review-v1', 'completed_formal_controls': rows,
              'benchmark_incoming_scan': {'scopes': scopes, 'unique_successful_prompt_ids': len(unique), 'mode_counts': dict(modes), 'component_matches': found, 'histories': scans,
                  'scope_limit': 'Only locally archived benchmark incoming histories in listed roots; no claim about absent or unarchived executions.'},
              'GPU_started': False, 'producer_writes': False}
    (OUT/'EVIDENCE.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'formal_controls':len(rows),'benchmark_history_count':len(scans),'unique_successful_prompt_ids':len(unique),'mode_counts':dict(modes),'component_matches':found},indent=2))


if __name__ == '__main__':
    main()
