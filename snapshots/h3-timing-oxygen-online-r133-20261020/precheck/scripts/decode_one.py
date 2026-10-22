"""One frozen R113 endpoint, same full VAE/RGB writer as R86; zero DiT calls."""
import argparse
import gc
import json
import os
from pathlib import Path
import sys
import time
from precheck_support import ROOT, approved, config, lifetime, require, sha, write, admission


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--parent-json', required=True)
    args = parser.parse_args()
    lifetime.install_lifetime_guard(json.loads(args.parent_json))
    approved()
    value = config()
    require(args.index in value['indices'], 'bounded index')
    require(args.output.resolve().is_relative_to(ROOT / 'audit'), 'output outside owned audit')
    require(not args.output.exists(), 'output already exists')
    c = value['runtime']
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'CPU before admission')
    import torch
    import frozen_x0_reader as reader
    import parent_capture_core as capture
    require(not torch.cuda.is_initialized(), 'CUDA initialized before admission')
    item = value['snapshots'][args.index]
    require(sha(item['file']) == item['sha256'], 'snapshot file differs')
    payload = reader.load_snapshot(Path(item['file']), capture)
    require(payload['metadata']['run_id'] == value['run_id'] and payload['metadata']['seed'] == value['seed'], 'actual seed/run')
    require(payload['metadata']['step_zero_based'] == args.index, 'physical step')
    require(sha(c['vae']) == c['vae_sha256'], 'VAE checkpoint differs')
    admitted = admission(value)
    os.environ['CUDA_VISIBLE_DEVICES'] = c['gpu_uuid']
    sys.path[:0] = [c['core'], c['dependencies']]
    from compatibility_bootstrap import install, install_video_compat
    install(); install_video_compat()
    import comfy.cli_args
    comfy.cli_args.args.disable_dynamic_vram = True
    comfy.cli_args.args.disable_cuda_malloc = True
    comfy.cli_args.args.use_pytorch_cross_attention = True
    import comfy.sd
    import comfy.utils
    import comfy.model_management as manager
    from decode_reference import install_fallback_guard
    fallback = install_fallback_guard(comfy.sd.VAE)
    record = dict(schema='r133-cached-endpoint-decode-v1', status='running', index=args.index,
                  parent_run=value['run_id'], seed=value['seed'], snapshot=item,
                  identity=lifetime.identity(os.getpid()), admission=admitted,
                  started_unix=time.time(), DiT_forward_calls=0, fallback=fallback,
                  frames=107, valid_frames=98, fps=24, torch=torch.__version__)
    record_path = args.output.with_suffix('.json')
    state = vae = images = None
    try:
        require(torch.cuda.device_count() == 1, 'one visible decoder GPU')
        started = time.monotonic()
        state, metadata = comfy.utils.load_torch_file(c['vae'], return_metadata=True)
        vae = comfy.sd.VAE(sd=state, metadata=metadata, dtype=torch.float16)
        vae.throw_exception_if_invalid()
        require(type(vae.first_stage_model).__name__ == 'MiniMaxH3VideoVAE' and vae.latent_channels == 24 and vae.latent_dim == 3, 'H3 VAE class')
        state = None
        record['load_seconds'] = time.monotonic() - started
        torch.cuda.synchronize(); started = time.monotonic()
        with torch.inference_mode():
            images = vae.decode(payload['video'])
        torch.cuda.synchronize()
        record['decode_seconds'] = time.monotonic() - started
        if images.ndim == 5 and images.shape[0] == 1:
            images = images.flatten(0, 1)
        require(tuple(images.shape) == (107, 736, 1312, 3) and bool(torch.isfinite(images).all()), 'full finite decode')
        images = images.detach().cpu()
        record['decoded_dtype'] = str(images.dtype)
        record['decoded_range'] = [float(images.min()), float(images.max())]
        record.update(reader.write_video(images, args.output, 'ffmpeg'))
        record['output_sha256'] = sha(args.output)
        require(fallback['calls'] == 0, 'fallback occurred')
        record['status'] = 'complete'
    except BaseException as error:
        record.update(status='failed', error=repr(error))
        raise
    finally:
        images = vae = state = payload = None
        manager.unload_all_models(); gc.collect(); manager.soft_empty_cache()
        record.update(finished_unix=time.time(), max_reserved_bytes=torch.cuda.max_memory_reserved(),
                      max_allocated_bytes=torch.cuda.max_memory_allocated(),
                      reserved_after_cleanup=torch.cuda.memory_reserved())
        write(record_path, record)


if __name__ == '__main__':
    main()
