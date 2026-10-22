"""CPU-only verification of a completed, root-released R70 operator run."""
import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED_PRODUCTS = {'baseline_Dz', 'identity_RGB_roundtrip', 'shift3_RGB_target',
    'shift3_RGB_roundtrip', 'shift3_latent_warp', 'offline_mapping_RGB_target',
    'offline_mapping_RGB_roundtrip', 'offline_mapping_latent_warp'}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def groups(coords):
    valid = [a and b and c for a, b, c in zip(coords['rgb_full_domain_valid'],
        coords['observed147_valid'], coords['output_bin_latent_domain_valid'])]
    return {'full158': [True] * 158, 'common_valid147': valid,
        'cross17_common_valid147': [v and c for v, c in zip(valid, coords['cross17_rgb'])],
        'within17_common_valid147': [v and not c for v, c in zip(valid, coords['cross17_rgb'])],
        'overlap_common_valid147': [v and c for v, c in zip(valid, coords['decoder_overlap_first5'])],
        'invalid_or_padding': [not v for v in valid]}


def reduced(errors, mask):
    selected = [e for e, v in zip(errors, mask) if v]
    return {'frames': len(selected), 'mean_absolute_rgb_error': sum(selected) / len(selected) if selected else None}


def validate_release(result, receipt):
    assert receipt['passed'] is True and receipt['process_absent'] is True
    assert receipt['CUDA_allocation_absent'] is True and receipt['pid'] == result['pid']
    assert result['status'] == 'complete' and not result.get('cleanup_error')
    assert result['vae_encode_calls'] == 3 and result['vae_decode_calls'] == 6
    assert result['model_forward_calls'] == 0 and result['fallback_guard']['calls'] == 0
    assert len(result['operations']) == 9 and set(result['products']) == EXPECTED_PRODUCTS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--exit-receipt', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), 'preserve earlier analysis'
    result = json.loads((args.run / 'RESULT.json').read_text())
    receipt = json.loads(args.exit_receipt.read_text())
    validate_release(result, receipt)
    expected = json.loads((ROOT / 'EXPECTED_COORDINATES.json').read_text())
    freeze = args.run.parent.parent / 'FREEZE.json'
    assert sha(freeze) == result['root_gate']['freeze_sha256']
    products, rows = {}, []
    ffprobe = shutil.which('ffprobe') or '/opt/homebrew/bin/ffprobe'
    for name, entry in result['products'].items():
        path = args.run / entry['file']
        assert path.name == name + '.mp4' and sha(path) == entry['sha256']
        assert entry['frames'] == 158 and entry['width'] == 1152 and entry['height'] == 768
        assert entry['fps'] == 24 and entry['lossless_pixel_verified'] is True
        assert entry['selected_full158_indices'] == list(range(158)) and len(entry['rgb24_frame_sha256']) == 158
        stream = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-select_streams', 'v:0',
            '-count_frames', '-show_entries', 'stream=width,height,nb_read_frames,r_frame_rate',
            '-of', 'json', str(path)]))['streams'][0]
        assert (stream['width'], stream['height'], stream['nb_read_frames'], stream['r_frame_rate']) == (1152, 768, '158', '24/1')
        products[name] = {'file': str(path), 'sha256': entry['sha256'], 'probe': stream}
    for operation in result['operations']:
        if operation['kind'] == 'encode':
            name = operation['name'].replace('_encode_RGB_target', '')
            assert sha(args.run / (name + '_encoded.pt')) == operation['saved_latent_sha256']
    details = {}
    shared_domain = [all(groups(spec['coordinates'])['common_valid147'][i] for spec in expected.values()) for i in range(158)]
    for name, spec in expected.items():
        coords = json.loads((args.run / (name + '_coordinates.json')).read_text())
        assert coords == spec['coordinates'], 'exact frozen map coordinates'
        masks = groups(coords)
        assert all(sum(masks[g]) == item['frames'] for g, item in spec['expected_group_counts'].items())
        details[name] = {'coordinates_sha256': sha(args.run / (name + '_coordinates.json')),
            'common_valid_indices': [i for i, v in enumerate(masks['common_valid147']) if v],
            'excluded_indices': [i for i, v in enumerate(masks['common_valid147']) if not v],
            'cross17_common_indices': [i for i, v in enumerate(masks['cross17_common_valid147']) if v],
            'comparisons': {}}
        for comparison, item in result['comparisons'][name].items():
            errors = item['frame_mae']
            assert len(errors) == 158 and all(math.isfinite(x) and 0 <= x <= 1 for x in errors)
            computed = {g: reduced(errors, mask) for g, mask in masks.items()}
            for g, value in computed.items():
                observed = item['groups'][g]
                assert observed['frames'] == value['frames']
                a, b = observed['mean_absolute_rgb_error'], value['mean_absolute_rgb_error']
                assert a is b if b is None else math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12)
                rows.append({'mapping': name, 'comparison': comparison, 'region': g, **value})
            extra_masks = {'common_domain_shared_across_three_maps': shared_domain,
                'latent_interpolation_cross17_common': [v and coords['cross17_latent_interpolation'][owner] for v, owner in zip(masks['common_valid147'], coords['output_bin_index'])],
                'latent_source_block_change_common': [v and coords['cross17_latent_source_block'][owner] for v, owner in zip(masks['common_valid147'], coords['output_bin_index'])],
                'outside_decoder_overlap_common': [v and not x for v, x in zip(masks['common_valid147'], coords['decoder_overlap_first5'])]}
            extra = {g: reduced(errors, mask) for g, mask in extra_masks.items()}
            for g, value in extra.items():
                rows.append({'mapping': name, 'comparison': comparison, 'region': g, **value})
            details[name]['comparisons'][comparison] = {'groups': computed, 'additional_consumer_regions': extra,
                'highest_error_common_frames': sorted(details[name]['common_valid_indices'], key=lambda i: (-errors[i], i))[:6]}
    args.out.mkdir(parents=True)
    summary = {'passed': True, 'result_sha256': sha(args.run / 'RESULT.json'),
        'exit_receipt_sha256': sha(args.exit_receipt), 'pid': result['pid'],
        'freeze_sha256': result['root_gate']['freeze_sha256'], 'products': products, 'maps': details,
        'operations': result['operations'], 'wall_seconds': result['wall_seconds'],
        'max_memory_reserved_bytes': result['max_memory_reserved_bytes'],
        'scope': 'Photometric error measures the temporal operator and VAE reconstruction, not motion accuracy. Offline mapping was fitted to the final output. Coordinate masks do not establish semantic correspondence validity.'}
    (args.out / 'VERIFIED.json').write_text(json.dumps(summary, indent=2) + '\n')
    with (args.out / 'ERROR_TABLE.csv').open('w') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(json.dumps({'passed': True, 'summary': str(args.out / 'VERIFIED.json')}))


if __name__ == '__main__':
    main()
