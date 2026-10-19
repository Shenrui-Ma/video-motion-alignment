"""Root-operated, model-free same-forward C/Y capture verification."""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import sys
import time

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'extensions'))
from H3TemporalRouter import core
from H3TemporalRouter import target_path_features as features


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError('Require one admitted idle GPU selected by UUID')
    torch.set_num_threads(1)
    n = 87592
    plan = {'seq_len': n, 'signature': [24, 42, 46, 82, 0],
            'frame_rows': 943, 'latent_interval_half_open': [14, 20],
            'reference_video_segment': [7910, 47516],
            'target_video_segment': [47986, 87592],
            'query_interval_half_open': [47986 + 14 * 943, 47986 + 20 * 943]}
    generator = torch.Generator(device='cuda').manual_seed(26101604)
    packed = torch.randn(1, n, 3, 56, 128, generator=generator,
                         device='cuda', dtype=torch.bfloat16)
    q, k, v = packed.permute(2, 0, 3, 1, 4).unbind(0)
    saved = packed.clone()
    cpu_rng = torch.get_rng_state().clone()
    gpu_rng = torch.cuda.get_rng_state().clone()
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    native = core.route_attention(q, k, v, 56, plan, mode='native')
    torch.cuda.synchronize()
    native_seconds = time.monotonic() - started
    records = []
    full_unchanged = []

    def capture(full, lse, q, k, v):
        before = full.clone()
        records.append(features.save_target_path_features(
            full, lse, q, k, v, plan, output_dir=str(args.output.parent / 'smoke_features'),
            run_id='model_free', step=6, block=25, sigma_video=.965517241379,
            attention=core.flash_attention_lse, aligned_attention=core._aligned_attention))
        full_unchanged.append(torch.equal(before, full))

    started = time.monotonic()
    captured = core.route_attention(q, k, v, 56, plan, mode='native', passive_capture=capture)
    torch.cuda.synchronize()
    capture_seconds = time.monotonic() - started
    checks = {'one_capture': len(records) == 1,
              'native_output_bitwise_unchanged': torch.equal(native, captured),
              'full_callback_input_bitwise_unchanged': all(full_unchanged),
              'QKV_bitwise_unchanged': torch.equal(packed, saved),
              'cpu_rng_unchanged': torch.equal(cpu_rng, torch.get_rng_state()),
              'cuda_rng_unchanged': torch.equal(gpu_rng, torch.cuda.get_rng_state())}
    stored = torch.load(records[0]['path'], map_location='cpu', weights_only=True)
    heads = list(features.HEADS)
    ta, tb = plan['target_video_segment']
    qa, qb = plan['query_interval_half_open']
    native_heads = native.reshape(1, n, 56, 128).permute(0, 2, 1, 3)
    checks['stored_Y_bitwise_native'] = torch.equal(
        stored['target'].reshape(1, 4, tb - ta, 128), native_heads[:, heads, ta:tb].cpu())
    del captured, native_heads, native, saved
    gc.collect()
    torch.cuda.empty_cache()
    actual = core.route_attention(q, k, v, 56, plan, mode='mass_preserve')
    actual = actual.reshape(1, n, 56, 128).permute(0, 2, 1, 3)
    wanted = actual[:, heads, qa:qb].cpu()
    candidate = stored['candidate'].reshape_as(wanted)
    checks['stored_C_bitwise_formal_full'] = torch.equal(candidate, wanted)
    delta = candidate.float() - wanted.float()
    peak = {'allocated_bytes': torch.cuda.max_memory_allocated(),
            'reserved_bytes': torch.cuda.max_memory_reserved()}
    record = {'schema': 'h3-target-path-smoke-v1', 'passed': all(checks.values()),
              'checks': checks, 'plan': plan, 'capture': records[0], 'peak': peak,
              'candidate_max_abs_error': float(delta.abs().max()),
              'native_seconds': native_seconds, 'native_plus_capture_seconds': capture_seconds,
              'torch': torch.__version__, 'cuda': torch.version.cuda,
              'device': torch.cuda.get_device_name(0),
              'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in [Path(__file__), Path(core.__file__), Path(features.__file__)]},
              'scope': 'Model-free actual-shape Flash checks; no action/quality inference'}
    del actual, q, k, v, packed
    gc.collect()
    torch.cuda.empty_cache()
    record['end_allocated_bytes'] = torch.cuda.memory_allocated()
    record['end_reserved_bytes'] = torch.cuda.memory_reserved()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({key: value for key, value in record.items() if key != 'capture'}))
    raise SystemExit(0 if record['passed'] else 1)


if __name__ == '__main__':
    main()
