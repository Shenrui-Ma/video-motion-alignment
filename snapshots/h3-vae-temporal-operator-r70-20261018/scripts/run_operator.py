"""Root-admitted offline VAE temporal-operator diagnostic. No DiT calls."""
import argparse
import gc
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
from common import sha, write, require, tensor_signature, write_frames
from decode_reference import admission, install_fallback_guard


def process_identity():
    path = Path('/proc') / str(os.getpid())
    raw = (path / 'cmdline').read_bytes()
    require(bool(raw), 'process cmdline must be populated')
    return {'pid': os.getpid(), 'uid': path.stat().st_uid,
            'start_ticks': (path / 'stat').read_text().rsplit(')', 1)[1].split()[19],
            'cmdline_sha256': sha(path / 'cmdline')}


def root_gate(control, gpu, config, output):
    require(control is not None, 'root ready/go control directory required')
    control.mkdir(parents=True, exist_ok=False)
    ready = {'schema': 'r70-vae-root-preCUDA-v1', 'identity': process_identity(),
             'gpu_uuid': gpu, 'CUDA_started': False, 'output': str(output),
             'input_snapshot_sha256': config['input_sha256']['inputs/x0_step006.pt'],
             'offline_mapping_sha256': config['input_sha256']['inputs/OFFLINE_DEVELOPMENT_MAPPING.json'],
             'freeze_sha256': sha(ROOT / 'FREEZE.json'), 'required_free_mib': config['required_free_mib']}
    write(control / 'ready.json', ready)
    print(json.dumps({'ready': str(control / 'ready.json'), 'identity': ready['identity']}), flush=True)
    deadline = time.monotonic() + 600
    while not (control / 'go.json').exists():
        require(process_identity() == ready['identity'], 'process identity changed')
        require(time.monotonic() < deadline, 'root registration timed out')
        time.sleep(.2)
    require(json.loads((control / 'go.json').read_text()) == ready, 'root exact ready/go binding')
    require(process_identity() == ready['identity'] and sha(ROOT / 'FREEZE.json') == ready['freeze_sha256'],
            'process/freeze changed while awaiting root')
    return ready


def validate():
    import torch
    import frozen_x0_reader as reader
    import frozen_capture_core as capture
    config = json.loads((ROOT / 'configs/contract.json').read_text())
    for relative, digest in config['input_sha256'].items():
        require(sha(ROOT / relative) == digest, 'input/source SHA ' + relative)
    for entry in json.loads((ROOT / 'FREEZE.json').read_text())['files']:
        require(sha(ROOT / entry['file']) == entry['sha256'], 'package freeze ' + entry['file'])
    gate = json.loads((ROOT / 'configs/PAIR_RUNTIME_GATE.json').read_text())
    require(gate['passed'] and all(x is True for x in gate['checks'].values()), 'actual parent pair gate')
    actual = next(x for x in gate['runs']['native']['snapshots'] if Path(x['file']).name == 'x0_step006.pt')
    require(actual['sha256'] == sha(ROOT / 'inputs/x0_step006.pt'), 'actual x0 output SHA')
    payload = reader.load_snapshot(ROOT / 'inputs/x0_step006.pt', capture)
    meta = payload['metadata']
    require(meta['run_id'] == 'r65_fitness_seed2026101701_native' and meta['step_zero_based'] == 6
            and meta['normalization_stage'] == 'after_process_latent_out'
            and meta['video_latent_scale_factor'] == 1 and meta['audio_scale'] == 4, 'actual AV normalization')
    z = payload['video']
    require(z.dtype == torch.float32 and tuple(z.shape) == (1, 24, 47, 48, 72), 'x0 video dtype/shape')
    for relative, digest in config['core_sha256'].items():
        require(sha(Path(config['core']) / relative) == digest, 'runtime source ' + relative)
    require(sha(config['vae']) == config['vae_sha256'], 'checkpoint SHA')
    require(sha(config['bootstrap']) == config['bootstrap_sha256'], 'compatibility bootstrap SHA')
    return config, z, meta


def install_runtime(config, cpu):
    sys.path.insert(0, config['dependencies'])
    sys.path.insert(0, config['core'])
    spec = importlib.util.spec_from_file_location('compatibility_bootstrap', config['bootstrap'])
    compat = importlib.util.module_from_spec(spec)
    sys.modules['compatibility_bootstrap'] = compat
    spec.loader.exec_module(compat)
    compat.install()
    compat.install_video_compat()
    import comfy.cli_args
    comfy.cli_args.args.cpu = cpu
    comfy.cli_args.args.disable_dynamic_vram = True
    comfy.cli_args.args.disable_cuda_malloc = True
    comfy.cli_args.args.use_pytorch_cross_attention = True
    import comfy.sd, comfy.utils, comfy.model_management
    return comfy.sd, comfy.utils, comfy.model_management


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--gpu-uuid')
    parser.add_argument('--control', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    require(args.validate_only != args.execute, 'choose validate-only or execute')
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    import torch
    import numpy as np
    import operators
    torch.set_num_threads(2)
    require(not torch.cuda.is_initialized(), 'CUDA not initialized before root registration')
    config, z, metadata = validate()
    mapping = json.loads((ROOT / 'inputs/OFFLINE_DEVELOPMENT_MAPPING.json').read_text())
    maps = operators.make_maps([x['native_index'] for x in mapping['mapping']])
    if args.validate_only:
        install_runtime(config, cpu=True)
        require(not torch.cuda.is_initialized(), 'CPU startup import must not initialize CUDA')
        print(json.dumps({'status': 'CPU_VALIDATED', 'CUDA_initialized': False,
                          'input_video_signature': tensor_signature(z), 'torch': torch.__version__,
                          'maps': {name: operators.coordinates(phi) for name, phi in maps.items()}}))
        return
    require(args.gpu_uuid == config['gpu_uuid'], 'root-approved exact GPU UUID')
    require(args.output is not None and not args.output.exists(), 'new execution output directory')
    args.output.mkdir(parents=True)
    record = {'schema': 'r70-offline-temporal-operator-v1', 'status': 'waiting_for_root',
              'pid': os.getpid(), 'uid': os.getuid(), 'input_metadata': metadata,
              'started_unix': time.time(), 'contract_sha256': sha(ROOT / 'configs/contract.json'),
              'model_forward_calls': 0, 'vae_encode_calls': 0, 'vae_decode_calls': 0,
              'scope': 'offline final-output-fitted mapping applied to saved index6 x0 for operator diagnosis',
              'normalization': config['checkpoint_normalization'], 'operations': [], 'products': {}, 'comparisons': {}}
    write(args.output / 'RESULT.json', record)
    state = vae = base = target = decoded = latent_decoded = encoded = None
    manager = None
    try:
        record['root_gate'] = root_gate(args.control, args.gpu_uuid, config, args.output)
        record['gpu_admission'] = [admission(args.gpu_uuid, config['required_free_mib'])]
        os.environ['CUDA_VISIBLE_DEVICES'] = args.gpu_uuid
        sd, utils, manager = install_runtime(config, cpu=False)
        record['gpu_admission'].append(admission(args.gpu_uuid, config['required_free_mib']))
        guard = install_fallback_guard(sd.VAE)
        def forbidden_encode(*a, **kw):
            guard['calls'] += 1
            raise RuntimeError('R70 refuses wrapper encode OOM fallback')
        for name in ('encode_tiled', 'encode_tiled_', 'encode_tiled_1d', 'encode_tiled_3d', '_encode_tiled_owned'):
            if hasattr(sd.VAE, name):
                setattr(sd.VAE, name, forbidden_encode)
                guard['installed'].append(name)
        record['fallback_guard'] = guard
        require(torch.cuda.device_count() == 1, 'exact one visible GPU')
        torch.cuda.reset_peak_memory_stats()
        state, model_metadata = utils.load_torch_file(config['vae'], return_metadata=True)
        vae = sd.VAE(sd=state, metadata=model_metadata, dtype=torch.float16)
        vae.throw_exception_if_invalid()
        require(vae.latent_channels == 24 and vae.latent_dim == 3, 'native H3 VAE')
        require(type(vae.first_stage_model).__name__ == 'MiniMaxH3VideoVAE', 'exact native model')
        state = None
        record['status'] = 'running'

        def operation(name, kind, value):
            torch.cuda.synchronize()
            started = time.monotonic()
            with torch.inference_mode():
                out = vae.decode(value) if kind == 'decode' else vae.encode(value)
            torch.cuda.synchronize()
            if kind == 'decode' and out.ndim == 5:
                out = out.flatten(0, 1)
            out = out.detach().cpu().contiguous()
            expected = (158, 768, 1152, 3) if kind == 'decode' else (1, 24, 47, 48, 72)
            require(tuple(out.shape) == expected and out.dtype == torch.float32, 'native output shape/dtype')
            record['vae_' + kind + '_calls'] += 1
            record['operations'].append({'name': name, 'kind': kind, 'seconds': time.monotonic() - started,
                'signature': tensor_signature(out), 'max_memory_allocated_bytes': torch.cuda.max_memory_allocated(),
                'max_memory_reserved_bytes': torch.cuda.max_memory_reserved()})
            write(args.output / 'RESULT.json', record)
            return out

        def save_video(name, frames):
            record['products'][name] = write_frames(frames, range(158), 24, args.output / (name + '.mp4'))
            write(args.output / 'RESULT.json', record)

        base = operation('baseline_Dz', 'decode', z)
        save_video('baseline_Dz', base)
        for name, phi in maps.items():
            coordinates = operators.coordinates(phi)
            write(args.output / (name + '_coordinates.json'), coordinates)
            target = base if name == 'identity' else operators.interpolate(base, phi, axis=0)
            if name != 'identity':
                save_video(name + '_RGB_target', target)
            encoded = operation(name + '_encode_RGB_target', 'encode', target)
            encoded_path = args.output / (name + '_encoded.pt')
            torch.save(encoded, encoded_path)
            record['operations'][-1]['saved_latent_sha256'] = sha(encoded_path)
            decoded = operation(name + '_decode_encoded_target', 'decode', encoded)
            save_video(name + '_RGB_roundtrip', decoded)
            error = operators.frame_mae(decoded, target)
            comparison = {'RGB_roundtrip_vs_target': {'frame_mae': error, 'groups': operators.reductions(error, coordinates)}}
            encoded = None
            if name != 'identity':
                target = None
                warped = operators.interpolate(z, coordinates['latent_positions'], axis=2)
                latent_decoded = operation(name + '_decode_latent_warp', 'decode', warped)
                save_video(name + '_latent_warp', latent_decoded)
                error = operators.frame_mae_to_rgb_warp(latent_decoded, base, phi)
                comparison['latent_warp_vs_target'] = {'frame_mae': error, 'groups': operators.reductions(error, coordinates)}
                error = operators.frame_mae(latent_decoded, decoded)
                comparison['latent_warp_vs_RGB_roundtrip'] = {'frame_mae': error, 'groups': operators.reductions(error, coordinates)}
                warped = latent_decoded = None
            record['comparisons'][name] = comparison
            target = decoded = None
            gc.collect()
            write(args.output / 'RESULT.json', record)
        require(record['vae_encode_calls'] == 3 and record['vae_decode_calls'] == 6 and guard['calls'] == 0,
                'registered operation count and no fallback')
        record['status'] = 'complete'
    except BaseException as error:
        record['status'] = 'failed'
        record['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        if torch.cuda.is_initialized():
            record['max_memory_allocated_bytes'] = torch.cuda.max_memory_allocated()
            record['max_memory_reserved_bytes'] = torch.cuda.max_memory_reserved()
        state = vae = base = target = decoded = latent_decoded = encoded = None
        try:
            if manager is not None:
                manager.unload_all_models()
                gc.collect()
                manager.soft_empty_cache()
        except BaseException as cleanup:
            record['cleanup_error'] = f'{type(cleanup).__name__}: {cleanup}'
            if record['status'] == 'complete':
                record['status'] = 'failed_cleanup'
        record['finished_unix'] = time.time()
        record['wall_seconds'] = record['finished_unix'] - record['started_unix']
        write(args.output / 'RESULT.json', record)
    require(record['status'] == 'complete', 'failure retained')
    print(json.dumps({'status': 'complete', 'result': str(args.output / 'RESULT.json')}))


if __name__ == '__main__':
    main()
