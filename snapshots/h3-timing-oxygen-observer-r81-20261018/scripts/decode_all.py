"""Root-admitted full20 x0 VAE decode. This program performs zero DiT forwards."""
import argparse
import gc
import json
import os
from pathlib import Path
import sys
import time
from contract import ROOT, check_package, read, require, sha
sys.path.insert(0, str(ROOT / 'vendor'))
from common import write
from decode_reference import admission, install_fallback_guard


def identity():
    path = Path('/proc') / str(os.getpid())
    return {'pid': os.getpid(), 'uid': path.stat().st_uid,
            'start_ticks': (path / 'stat').read_text().rsplit(')', 1)[1].split()[19],
            'cmdline_sha256': sha(path / 'cmdline')}


def root_gate(control, output, config):
    control.mkdir(parents=True, exist_ok=False)
    ready = {'schema': 'r81-vae-preCUDA-v1', 'identity': identity(),
             'gpu_uuid': config['host41']['gpu_uuid'], 'required_free_mib': config['host41']['required_free_mib'],
             'freeze_sha256': sha(ROOT / 'FREEZE.json'), 'protocol_sha256': sha(ROOT / 'configs/PROTOCOL.json'),
             'output': str(output), 'CUDA_started': False}
    write(control / 'ready.json', ready)
    print(json.dumps({'ready': str(control / 'ready.json'), 'identity': ready['identity']}), flush=True)
    deadline = time.monotonic() + 600
    while not (control / 'go.json').exists():
        require(time.monotonic() < deadline, 'root GO wait exceeded600s')
        require(identity() == ready['identity'], 'process identity changed')
        time.sleep(.25)
    require(read(control / 'go.json') == ready, 'exact root ready/go differs')
    require(identity() == ready['identity'] and sha(ROOT / 'FREEZE.json') == ready['freeze_sha256'], 'owner/freeze changed')
    return ready


def validate_inputs(config):
    import torch
    import frozen_x0_reader as reader
    import frozen_capture_core as capture
    gate = read(ROOT / 'configs/PAIR_RUNTIME_GATE.json')
    require(gate['passed'] and all(gate['checks'].values()), 'actual R73 pair gate')
    manifest = read(ROOT / config['snapshot_manifest'])
    require(manifest['run_id'] == config['run_id'] and manifest['status'] == 'complete', 'capture identity/completion')
    for index, item in enumerate(config['snapshots']):
        require(sha(ROOT / item['file']) == item['sha256'], 'actual x0 SHA differs')
        payload = reader.load_snapshot(ROOT / item['file'], capture)
        meta = payload['metadata']
        require(meta['run_id'] == config['run_id'] and meta['step_zero_based'] == index and meta['snapshot_kind'] == 'x0_estimate', 'step identity')
        require(meta['video_latent_scale_factor'] == 1 and meta['normalization_stage'] == 'after_process_latent_out', 'VAE normalization')
        require(tuple(payload['video'].shape) == (1, 24, 32, 46, 82), 'full107 video latent')
    final = reader.load_snapshot(ROOT / 'inputs/sampler_final.pt', capture)
    last = reader.load_snapshot(ROOT / config['snapshots'][-1]['file'], capture)
    endpoint = {name: bool(torch.equal(last[name], final[name])) for name in ('video', 'audio')}
    return endpoint


def runtime(config, cpu):
    c = config['host41']
    for relative, digest in c['core_sha256'].items():
        require(sha(Path(c['core']) / relative) == digest, 'Core SHA: ' + relative)
    require(sha(c['vae']) == c['vae_sha256'], 'FP16 VAE SHA')
    sys.path[:0] = [c['dependencies'], c['core']]
    from compatibility_bootstrap import install, install_video_compat
    install(); install_video_compat()
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
    parser.add_argument('--control', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    require(args.validate_only != args.execute, 'choose CPU validation or root execution')
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    import torch
    import frozen_x0_reader as reader
    import frozen_capture_core as capture
    torch.set_num_threads(2)
    require(not torch.cuda.is_initialized(), 'no CUDA before admission')
    config = check_package()
    endpoint = validate_inputs(config)
    if args.validate_only:
        runtime(config, cpu=True)
        require(not torch.cuda.is_initialized(), 'CPU import initialized CUDA')
        print(json.dumps({'status': 'CPU_VALIDATED', 'observations': 20, 'endpoint_video_audio_equal': endpoint,
                          'torch': torch.__version__, 'CUDA_initialized': False}))
        return
    require(args.control is not None and args.output is not None, 'new control/output directories required')
    args.output.mkdir(parents=True, exist_ok=False)
    record = dict(schema='r81-full20-decode-v1', status='waiting_for_root',
                  protocol_sha256=sha(ROOT / 'configs/PROTOCOL.json'), started_unix=time.time(),
                  endpoint_video_audio_equal=endpoint, DiT_forward_calls=0, steps=[], decode_host='41',
                  torch=torch.__version__, cross_host_boundary=config['cross_host_boundary'])
    vae = images = state = payload = None
    manager = None
    try:
        record['root_gate'] = root_gate(args.control, args.output, config)
        c = config['host41']
        record['admission'] = [admission(c['gpu_uuid'], c['required_free_mib'])]
        os.environ['CUDA_VISIBLE_DEVICES'] = c['gpu_uuid']
        sd, utils, manager = runtime(config, cpu=False)
        record['admission'].append(admission(c['gpu_uuid'], c['required_free_mib']))
        require(torch.cuda.device_count() == 1, 'one visible GPU')
        record['fallback_guard'] = install_fallback_guard(sd.VAE)
        state, metadata = utils.load_torch_file(c['vae'], return_metadata=True)
        vae = sd.VAE(sd=state, metadata=metadata, dtype=torch.float16)
        vae.throw_exception_if_invalid()
        require(type(vae.first_stage_model).__name__ == 'MiniMaxH3VideoVAE', 'H3 VAE class')
        state = None
        record['status'] = 'running'
        deadline = time.monotonic() + config['max_decode_seconds']
        for index, item in enumerate(config['snapshots']):
            require(time.monotonic() < deadline, 'bounded decode lifetime')
            payload = reader.load_snapshot(ROOT / item['file'], capture)
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
            started = time.monotonic()
            with torch.inference_mode():
                images = vae.decode(payload['video'])
            torch.cuda.synchronize()
            if images.ndim == 5 and images.shape[0] == 1:
                images = images.flatten(0, 1)
            require(tuple(images.shape) == (107, 736, 1312, 3) and bool(torch.isfinite(images).all()), 'complete finite107 decode')
            images = images.detach().cpu()
            out = args.output / f'step{index:03d}.mp4'
            row = {'index': index, 'status': 'complete', 'snapshot_sha256': item['sha256'],
                   'decode_seconds': time.monotonic() - started,
                   'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
                   'peak_reserved_bytes': torch.cuda.max_memory_reserved(),
                   'driver_free_bytes': torch.cuda.mem_get_info()[0],
                   'frames': 107, 'valid_frames': 98, 'fps': 24}
            row.update(reader.write_video(images, out, 'ffmpeg'))
            row.update(file=out.name, sha256=sha(out), total_seconds=time.monotonic() - started)
            write(out.with_suffix('.json'), row)
            record['steps'].append(row)
            write(args.output / 'RESULT.json', record)
            print(json.dumps({'step': index, 'decode_seconds': row['decode_seconds'], 'peak_reserved_bytes': row['peak_reserved_bytes']}), flush=True)
            images = payload = None
            gc.collect()
        require(len(record['steps']) == 20 and record['fallback_guard']['calls'] == 0, 'full20/no fallback')
        record['status'] = 'complete'
    except BaseException as exc:
        record['status'] = 'failed'
        record['error'] = repr(exc)
        raise
    finally:
        state = vae = images = payload = None
        try:
            if manager is not None:
                manager.unload_all_models(); gc.collect(); manager.soft_empty_cache()
        except BaseException as cleanup:
            record['cleanup_error'] = repr(cleanup)
            if record['status'] == 'complete':
                record['status'] = 'failed_cleanup'
        record['finished_unix'] = time.time()
        record['wall_seconds'] = record['finished_unix'] - record['started_unix']
        write(args.output / 'RESULT.json', record)
    require(record['status'] == 'complete', 'decode cleanup failed')


if __name__ == '__main__':
    main()
