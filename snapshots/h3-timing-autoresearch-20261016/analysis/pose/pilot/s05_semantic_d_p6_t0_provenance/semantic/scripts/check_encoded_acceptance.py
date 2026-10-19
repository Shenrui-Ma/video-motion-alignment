"""Read-only CPU audit of actual encoded manifests; no imports of torch/models."""
import argparse
import hashlib
import json
from pathlib import Path
PINNED_BASELINE_SHA = {'05_sam_1312x736_shared_v3_conditioning.json': 'ce14565bc7279b3a75ef9f5239f8e264049e8dc02cdc4e1e4e59d3dbe51528a3', 's05_full_seed1_native_noise.json': 'd23d4260b878c5cb0aaaa4416487522899c69989673743c2c44c2d0edb77b47f'}

def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if k != 'tensor_file'}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value

def check(root, require_all=False):
    root = Path(root)
    audit = root / 'audit'
    for name, expected in PINNED_BASELINE_SHA.items():
        if hashlib.sha256((root / 'baseline' / name).read_bytes()).hexdigest() != expected:
            raise ValueError('pinned baseline hash mismatch: ' + name)
    baseline = json.loads((root / 'baseline/05_sam_1312x736_shared_v3_conditioning.json').read_text())
    noise = json.loads((root / 'baseline/s05_full_seed1_native_noise.json').read_text())
    zero = 's05_semantic_a0_p0_t0_condition'
    gate = json.loads((audit / (zero + '_zero_gate.json')).read_text())
    core = root / 'extensions/H3SemanticClock'
    actual_provenance = {'conditioning': PINNED_BASELINE_SHA['05_sam_1312x736_shared_v3_conditioning.json'], 'noise': PINNED_BASELINE_SHA['s05_full_seed1_native_noise.json'], 'implementation': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(core.glob('*.py'))}}
    if gate['provenance'] != actual_provenance or not actual_provenance['implementation']:
        raise ValueError('actual baseline/extension files do not match accepted zero provenance')
    if not (gate['passed'] and gate['zero_gate'] and (gate['condition_run_id'] == zero)):
        raise ValueError('encoding acceptance condition failed')
    if not gate['condition_sha256'] == hashlib.sha256((audit / (zero + '_conditioning.json')).read_bytes()).hexdigest():
        raise ValueError('encoding acceptance condition failed')
    arms = {}
    results = {}
    for arm, p, t in [('a0_p0_t0', 0, 0), ('b_p6_t6', 6, 6), ('c_p0_t6', 0, 6), ('d_p6_t0', 6, 0)]:
        cid = 's05_semantic_' + arm + '_condition'
        file = audit / (cid + '_conditioning.json')
        if not file.exists():
            if not not require_all:
                raise ValueError('missing ' + arm)
            continue
        m = json.loads(file.read_text())
        a = json.loads((audit / (cid + '_accepted.json')).read_text())
        if not (a['passed'] and a['actual_noise_streams'] == clean(noise['actual_noise_streams'])):
            raise ValueError('encoding acceptance condition failed')
        if not a['condition_sha256'] == hashlib.sha256(file.read_bytes()).hexdigest():
            raise ValueError('encoding acceptance condition failed')
        if not m['semantic_clock']['provenance'] == gate['provenance']:
            raise ValueError('encoding acceptance condition failed')
        for k in ('prompt', 'input_video', 'native_vae_calls', 'token_tags', 'target_latent_shapes', 'packed_layout'):
            if not clean(m[k]) == clean(baseline[k]):
                raise ValueError(arm + ' invariant ' + k)
        v = next((x for x in m['qwen_presentation'] if x['type'] == 'video'))
        if not v['sampling']['sample_indices'] == list(range(p, 141, 12)):
            raise ValueError('encoding acceptance condition failed')
        if not v['sampling']['rendered_labels'] == ['<%.1f seconds>' % (i + 0.25 + t / 24) for i in range(6)]:
            raise ValueError('encoding acceptance condition failed')
        if not m['semantic_clock']['checks']['reference_target_time_gap'] == 235.0:
            raise ValueError('encoding acceptance condition failed')
        if not m['semantic_clock']['checks']['non_timestamp_text_ids_equal'] is True:
            raise ValueError('encoding acceptance condition failed')
        if not (p or t):
            if not clean(m['conditioning_embedding']) == clean(baseline['conditioning_embedding']):
                raise ValueError('encoding acceptance condition failed')
        arms[arm] = (m, v)
        results[arm] = {'passed': True, 'condition_sha256': a['condition_sha256'], 'embedding_sha256': m['conditioning_embedding']['sha256'], 'video_pixel_sha256': v['actual_sampled_frames']['sha256']}
    for a, b in [('a0_p0_t0', 'c_p0_t6'), ('b_p6_t6', 'd_p6_t0')]:
        if a in arms and b in arms:
            if not clean(arms[a][1]['actual_sampled_frames']) == clean(arms[b][1]['actual_sampled_frames']):
                raise ValueError('same P must mean identical actual pixels')

            def vision_blocks(manifest):
                return [e[0]['data']['tensor'] for e in manifest['tokenization_before_vision_expansion']['qwen3vl_32b'][0] if isinstance(e[0], dict)]
            if not clean(vision_blocks(arms[a][0])) == clean(vision_blocks(arms[b][0])):
                raise ValueError('same P must keep every vision block identical')
    for a, b in [('a0_p0_t0', 'd_p6_t0'), ('b_p6_t6', 'c_p0_t6')]:
        if a in arms and b in arms:
            if not arms[a][1]['sampling']['presented_timestamps_seconds'] == arms[b][1]['sampling']['presented_timestamps_seconds']:
                raise ValueError('encoding acceptance condition failed')
    return {'schema': 'h3-semantic-actual-encoding-check-v1', 'arms': results, 'all_four_available': len(arms) == 4, 'scope': 'actual encoded inputs/noise/layout; does not evaluate generated video or claim mechanism'}
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('root')
    p.add_argument('--require-all', action='store_true')
    a = p.parse_args()
    print(json.dumps(check(a.root, a.require_all), indent=2))
