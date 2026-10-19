"""CPU-only same-input endpoint perturbation footprint; no new generation."""
import argparse
import fcntl
import hashlib
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not args.execute:
        print('Prepared endpoint footprint diagnostic')
        return
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    manifest = json.loads((HERE / 'FREEZE.json').read_text())
    for name, digest in manifest['files'].items():
        assert sha(HERE / name) == digest, name
    output = HERE / 'RESULT.json'
    assert not output.exists(), 'Review existing result before any rerun'
    lock = Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
    with lock.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(75)
        for name in ['timing_auto_fresh_r32_20261017', 'timing_auto_bedside_r35_20261017']:
            root = lock.parents[3] / name
            for request in (root / 'audit/observations').glob('*/request.json'):
                if not (request.parent / 'response.json').exists():
                    raise SystemExit(75)
        import torch
        torch.set_num_threads(4)
        assert not torch.cuda.is_initialized()
        protocol = json.loads((HERE / 'PROTOCOL.json').read_text())
        started = time.monotonic()
        native_previous = None
        rows = []
        for case in protocol['cases']:
            values = {}
            for branch in ['native', 'full']:
                path = Path(case['files'][branch]['path'])
                assert sha(path) == case['files'][branch]['sha256']
                value = torch.load(path, map_location='cpu', weights_only=True)
                assert set(value) == {'video', 'audio', 'metadata'}
                m = value['metadata']
                assert m['physical_index'] == 4 and m['branch'] == branch
                assert m['seed'] == 2026101311
                assert tuple(value['video'].shape) == (1, 24, 42, 46, 82)
                assert value['video'].dtype == torch.float32
                assert torch.isfinite(value['video']).all()
                values[branch] = value
            native, guided = values['native'], values['full']
            for key in ['physical_index', 'sigma', 'sigma_next', 'seed', 'condition_sha256', 'reference_sha256']:
                assert native['metadata'][key] == guided['metadata'][key], key
            if native_previous is not None:
                assert torch.equal(native_previous['video'], native['video'])
                assert torch.equal(native_previous['audio'], native['audio'])
            native_previous = native
            delta = guided['video'].double() - native['video'].double()
            energy = delta.square().sum(dim=(0, 1, 3, 4))
            inside = torch.tensor(case['query_bins'], dtype=torch.long)
            total = float(energy.sum())
            assert total > 0
            inside_energy = float(energy[inside].sum())
            outside_energy = total - inside_energy
            # A uniform perturbation is the analytic density reference, not a null test.
            uniform_fraction = len(case['query_bins']) / 42
            video_sigma = native['metadata']['sigma']
            rows.append({
                'case': case['name'], 'query_bins': case['query_bins'],
                'clean_endpoint_delta_squared_L2_by_bin': energy.tolist(),
                'total_squared_L2': total, 'inside_squared_L2': inside_energy,
                'outside_squared_L2': outside_energy,
                'outside_energy_fraction': outside_energy / total,
                'inside_energy_fraction': inside_energy / total,
                'uniform_inside_fraction': uniform_fraction,
                'inside_per_bin_mean_energy': inside_energy / len(inside),
                'outside_per_bin_mean_energy': outside_energy / (42 - len(inside)),
                'video_velocity_delta_squared_L2': total / video_sigma**2,
                'all42_bins_changed': bool((energy > 0).all()),
                'audio_normalized_delta_squared_L2': float((guided['audio'].double() - native['audio'].double()).square().sum()),
                'within_pair_condition_match': True,
            })
        result = {
            'status': 'complete', 'rows': rows,
            'both_native_AV_exact': True, 'new_GPU_forwards': 0,
            'elapsed_seconds': time.monotonic() - started,
            'freeze_sha256': sha(HERE / 'FREEZE.json'),
            'files': protocol['cases'],
            'scope': 'One same-state DiT output footprint. Every route acts through all50blocks. This does not identify which layer spreads the perturbation, measure semantic quality, or establish that outside energy causes final timing repair.',
        }
        output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
        print(json.dumps({'status': 'complete', 'rows': [{k: r[k] for k in ['case', 'outside_energy_fraction', 'all42_bins_changed']} for r in rows], 'seconds': result['elapsed_seconds']}))


if __name__ == '__main__':
    main()
