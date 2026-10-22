"""Read only five frozen small JSON collections; never load tensors or media."""
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
CASES = [
    ('oxygen', 'R73 氧气设备0252', 'h3-ivebench-expanded-metrics-r73-20261018', 'short_0252', 'h3-timing-ivebench-expanded-r73-20261018', '局部动作有帮助'),
    ('glasses', 'R89 眼镜0358', 'h3-ive-subject-capacity-metrics-r89-20261018', 'short_0358', 'h3-timing-ive-subject-capacity-r89-20261018', '早段稍改善，后段仍延后'),
    ('one_leg', 'R85 单腿/movie9', 'h3-flexiact-expanded-metrics-r85-20261018', 'one_leg__movie_man_9', 'h3-timing-flexiact-expanded-r85-20261018', '明显延后，固定引导未修复'),
    ('rotate', 'R85 转身/gamegirl1', 'h3-flexiact-expanded-metrics-r85-20261018', 'rotate__game_girl_1', 'h3-timing-flexiact-expanded-r85-20261018', '普通编辑已同相'),
    ('identity_failure', 'R66 俯卧/game4', 'h3-flexiact-expanded-evaluation-r66-20261018', 'human2animal_1__game_man_4', 'h3-timing-flexiact-expanded-r66-20261018', '基础角色替换失败'),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def summary(rows):
    m = [r['ref_mass_mean'] for r in rows]
    c = [r['correction_ratio'] for r in rows]
    return {
        'count': len(rows), 'ref_mass_mean': mean(m),
        'ref_mass_mean_range': [min(m), max(m)],
        'ref_mass_sample_max': max(r['ref_mass_max'] for r in rows),
        'correction_ratio_mean': mean(c), 'correction_ratio_median': median(c),
        'correction_ratio_range': [min(c), max(c)],
        'all_sampled_finite': all(r['finite'] for r in rows),
        'correction_ratio_exact_zero_count': sum(v == 0 for v in c),
        'correction_ratio_below_0p01_count': sum(v < .01 for v in c),
        'correction_ratio_below_0p05_count': sum(v < .05 for v in c),
        'threshold_note': '0.01/0.05 are descriptive output-ratio bins, not calibrated adequacy thresholds.',
    }


def main():
    results = []
    provenance = []
    csv_rows = []
    for key, title, consumer, case, producer, prior_review in CASES:
        incoming = BASE / consumer / 'incoming' / case
        collection = json.loads((incoming / 'COLLECTION.json').read_text())
        docs = {}
        for filename in ['COLLECTION.json', 'PAIR_RUNTIME_GATE.json', 'native_router.json', 'forced_router.json', 'native_history.json', 'forced_history.json']:
            src = incoming / filename
            digest = sha(src)
            expected = collection['files'].get(filename)
            if filename != 'COLLECTION.json':
                assert expected == digest, (key, filename, expected, digest)
            dst = ROOT / 'inputs' / key / filename
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            docs[filename] = json.loads(dst.read_text())
            provenance.append({'case': key, 'source': str(src), 'snapshot': str(dst.relative_to(ROOT)), 'sha256': digest, 'bytes': src.stat().st_size, 'matches_collection': filename != 'COLLECTION.json'})
        core = BASE / producer / 'extensions/H3TemporalRouter/core.py'
        core_sha = sha(core)
        assert core_sha == '7a7e9c8067c9c0287659fafed06b775549aaa8cab5141c60220c0536b0eeb650'
        provenance.append({'case': key, 'source': str(core), 'sha256': core_sha, 'bytes': core.stat().st_size})
        gate = docs['PAIR_RUNTIME_GATE.json']
        guided, native = docs['forced_router.json'], docs['native_router.json']
        assert gate['passed'] is True and all(v is True for v in gate['checks'].values())
        assert guided['run_id'] == gate['runs']['forced']['run_id']
        assert guided['completed_forward_calls'] == 20
        assert guided['routed_calls'] == gate['runs']['forced']['routed_blocks'] == 450
        assert native['routed_calls'] == 0
        assert guided['mode'] == 'mass_preserve' and guided['alpha'] == 1
        assert guided['radius'] == guided['time_offset'] == 0
        assert guided['step_interval_half_open'] == [6, 15]
        assert guided['block_interval_half_open'] == [0, 50]
        history_statuses = {}
        for arm in ['native', 'forced']:
            history = docs[arm + '_history.json']
            entries = [history] if 'status' in history else list(history.values())
            statuses = [x.get('status', {}) for x in entries]
            assert len(statuses) == 1 and statuses[0]['completed'] is True and statuses[0]['status_str'] == 'success', (key, arm, statuses)
            history_statuses[arm] = statuses[0]
        rows = []
        steps = []
        active = [s for s in guided['forward_summaries'] if s['routed_blocks']]
        assert [s['forward_index'] for s in active] == list(range(6, 15))
        for step in active:
            layers = step['layer_stats']
            assert len(layers) == 50 and [x['block'] for x in layers] == list(range(50))
            for x in layers:
                row = dict(x, step_zero_based=step['forward_index'])
                rows.append(row)
                csv_rows.append(dict(case=key, **row))
            sm = summary(layers)
            assert math.isclose(sm['ref_mass_mean'], step['sampled_ref_mass_mean'], abs_tol=1e-12)
            assert math.isclose(sm['correction_ratio_mean'], step['sampled_correction_ratio_mean'], abs_tol=1e-12)
            steps.append(dict(step_zero_based=step['forward_index'], sigma=guided['sample_sigmas'][step['forward_index']], **sm))
        plan = guided['validated_layout']
        qa, qb = plan['query_interval_half_open']
        _, heads, _, channels = guided['first_attention']['qkv_shape']
        hs, qs, ds = math.ceil(heads / 8), math.ceil((qb - qa) / 128), math.ceil(channels / 16)
        query_offsets = list(range(0, qb - qa, qs))
        fr = plan['frame_rows']
        lo, hi = plan['latent_interval_half_open']
        sampling = {
            'head_indices': list(range(0, heads, hs)), 'channel_indices': list(range(0, channels, ds)),
            'query_stride': qs, 'query_count': len(query_offsets),
            'query_rows': [{'packed_index': qa + q, 'latent_bin': lo + q // fr, 'spatial_index': q % fr} for q in query_offsets],
            'all_active_bins_sampled': sorted({lo + q // fr for q in query_offsets}) == list(range(lo, hi)),
            'covered_latent_bins': sorted({lo + q // fr for q in query_offsets}),
            'selected_query_rows': qb - qa, 'selected_latent_bins_half_open': [lo, hi],
            'pixel_interval_inclusive': plan['pixel_interval_inclusive'],
            'position_bin_coverage_inclusive': plan['position_bin_coverage_inclusive'],
            'reference_temporal_bins': (plan['reference_video_segment'][1] - plan['reference_video_segment'][0]) // fr,
            'has_reference_image_segment': bool(plan['reference_image_segments']),
            'scope': 'Deterministic strided bounded sample; no identity/body mask; mass spans all reference VIDEO keys including padded bins.',
        }
        readouts = []
        for arm, d in [('native', native), ('forced', guided)]:
            for rd in d['temporal_readouts']:
                qrs = rd['query_records']
                readouts.append({
                    'arm': arm, 'step_zero_based': rd['forward_index'], 'block_zero_based': rd['block_index'],
                    'head_indices': rd['head_indices'], 'spatial_indices': rd['spatial_indices'],
                    'query_bins': [x['query_latent_bin'] for x in qrs],
                    'reference_temporal_bins': rd['reference_temporal_bins'],
                    'same_bin_mass_mean_conditional_on_reference': mean(x['same_bin_mass'] for x in qrs),
                    'within_one_bin_mass_mean_conditional_on_reference': mean(x['within_one_bin_mass'] for x in qrs),
                    'mean_minus_query_bins_mean': mean(x['mean_minus_query_bins'] for x in qrs),
                    'scope': rd['scope'],
                })
        groups = {name: summary([r for r in rows if r['step_zero_based'] in indices]) for name, indices in [('steps_6_8', range(6,9)), ('steps_9_11', range(9,12)), ('steps_12_14', range(12,15))]}
        layers = [dict(block_zero_based=b, **summary([r for r in rows if r['block'] == b])) for b in range(50)]
        results.append({
            'id': key, 'title': title, 'source_case': case, 'prior_visual_review_from_root': prior_review,
            'run_id': guided['run_id'], 'host': gate['runtime_profile']['host'], 'router_core_sha256': core_sha,
            'status_note': 'Router last dump retains status=sampling; complete history and passed actual pair gate establish completion.',
            'passed_actual_gate': gate['passed'], 'router_sha256': sha(incoming / 'forced_router.json'),
            'gate_sha256': sha(incoming / 'PAIR_RUNTIME_GATE.json'),
            'valid_frames': gate['runs']['forced']['valid_frames'], 'total_frames': int(gate['runs']['forced']['video']['properties']['nb_read_frames']),
            'NFE': gate['runs']['forced']['NFE'], 'routed_calls': guided['routed_calls'],
            'sampling': sampling, 'all_active': summary(rows), 'per_step': steps, 'denoising_step_groups': groups,
            'per_layer_across_active_steps': layers, 'conditional_time_readouts': readouts,
            'sigmas': guided['sample_sigmas'],
            'missing': ['absolute old/output/correction RMS', 'reference image or text/audio/canvas group mass', 'per-head/per-position raw mass and correction', 'global full-tensor norm', 'Native reference group total mass', 'inactive-step reference group total mass', 'post-block/post-CFG/x0/video change', 'identity/motion-correctness labels tied to attention sample'],
        })
    save(ROOT / 'results/COMPARISON.json', {'schema': 'existing-router-five-case-audit-v1', 'case_count': len(results), 'cases': results})
    save(ROOT / 'results/INPUT_PROVENANCE.json', {'files': provenance, 'only_small_json_and_core_read': True, 'GPU_started': False})
    with (ROOT / 'results/ALL_ACTIVE_LAYER_STATS.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(csv_rows[0]))
        writer.writeheader(); writer.writerows(csv_rows)
    (ROOT / 'inputs/router_core.py').write_bytes((BASE / CASES[0][4] / 'extensions/H3TemporalRouter/core.py').read_bytes())
    print(json.dumps([{k: c[k] for k in ['id','all_active','denoising_step_groups']} for c in results], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
