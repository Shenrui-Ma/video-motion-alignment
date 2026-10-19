"""One root-admitted model-free routing memory measurement; no model inference."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHAPE = (27, 23, 41)
ROWS = 23 * 41
LOCAL_BINS = (0, 14, 15, 16, 17, 18, 19, 26)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    def reject(value):
        raise ValueError('nonfinite JSON: ' + value)
    return json.loads(Path(path).read_text(), parse_constant=reject)


def put(path, value):
    with Path(path).open('x') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')


def owned_path(root, relative):
    root = Path(root).resolve()
    path = root / relative
    if Path(relative).is_absolute() or path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError('path escapes audit or parent root')
    return path.resolve()


def select_layout(root):
    root = Path(root)
    protocol = read(root / 'configs/protocol.json')
    closure = read(root / 'configs/PARENT_CLOSURE.json')
    if closure.get('ready') is not True or closure.get('status') != 'READY':
        raise ValueError('actual R54 parent closure must be bound first')
    cases = protocol['cases']
    if len(cases) != 5 or len({c['run_id'] for c in cases}) != 5:
        raise ValueError('expected the five distinct R55 cases')
    records = []
    for case in cases:
        rel = case['parent_conditioning']
        path = owned_path(root, rel)
        bound = closure['cases'][case['source_id']]
        if bound.get('ready') is not True or bound['parent_run'] != case['parent_run']:
            raise ValueError('actual parent identity differs')
        if sha(path) != bound['actual_file_sha256'][rel]:
            raise ValueError('actual conditioning hash differs')
        layout = read(path)['packed_layout']
        if layout != bound['packed_layout']:
            raise ValueError('closure packed layout differs')
        n, segments = layout['seq_len'], layout['segments']
        if type(n) is not int or n <= 0:
            raise ValueError('invalid sequence length')
        end = 0
        for start, stop, label in segments:
            if type(start) is not int or type(stop) is not int or start != end or not start < stop <= n:
                raise ValueError('segments must partition actual packed sequence')
            end = stop
        if end != n:
            raise ValueError('incomplete packed sequence')
        refs = [s for s in segments if s[2] == 'ref_img']
        targets = [s for s in segments if s[2] == 'video']
        if len(refs) != 1 or len(targets) != 1 or any(s[1] - s[0] != 27 * ROWS for s in (refs[0], targets[0])):
            raise ValueError('expected one 27-bin video reference and one 27-bin target')
        records.append({'run_id': case['run_id'], 'source_id': case['source_id'],
                        'conditioning_file': rel, 'conditioning_sha256': sha(path),
                        'plan': {'seq_len': n, 'frame_rows': ROWS,
                                 'latent_interval_half_open': [0, 27],
                                 'query_interval_half_open': targets[0][:2],
                                 'reference_video_segment': refs[0][:2]}})
    # Python max keeps protocol order when sequence lengths tie.
    selected = max(records, key=lambda r: r['plan']['seq_len'])
    return {'selected': selected, 'all_actual_layouts': records,
            'protocol_sha256': sha(root / 'configs/protocol.json'),
            'parent_closure_sha256': sha(root / 'configs/PARENT_CLOSURE.json')}


def check_compute(rows, target, lookup, own_uid, own_pid=None):
    owned = set()
    for row in rows:
        uid = lookup(row['pid'])
        if uid is None:
            raise RuntimeError('compute ownership unresolved')
        if row['gpu_uuid'] == target and row['pid'] != own_pid:
            raise RuntimeError('target GPU has another compute process')
        if uid == own_uid:
            owned.add(row['gpu_uuid'])
    if len(owned | {target}) > 2:
        raise RuntimeError('probe would exceed two owned GPUs')
    return sorted(owned)


def resource_snapshot(target, own_pid=None):
    raw = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid',
                                   '--format=csv,noheader,nounits'], text=True, timeout=10)
    rows = []
    for line in raw.splitlines():
        if line.strip():
            gpu, pid = [v.strip() for v in line.split(',')]
            rows.append({'gpu_uuid': gpu, 'pid': int(pid)})
    def uid(pid):
        try:
            return (Path('/proc') / str(pid)).stat().st_uid
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            return None
    record = {'observed_unix': time.time(), 'compute_raw': raw, 'compute_rows': rows}
    try:
        record['owned_gpu_uuids'] = check_compute(rows, target, uid, os.getuid(), own_pid)
    except Exception as error:
        error.resource_snapshot = record
        raise
    return record


def memory_snapshot(cuda):
    free, total = cuda.mem_get_info()
    stats = cuda.memory_stats()
    return {'allocated_bytes': cuda.memory_allocated(), 'reserved_bytes': cuda.memory_reserved(),
            'active_bytes': stats['active_bytes.all.current'],
            'driver_free_bytes': free, 'driver_total_bytes': total}


def measure_once(cuda, call):
    cuda.synchronize()
    before = memory_snapshot(cuda)
    cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    try:
        output = call()
        cuda.synchronize()
    except BaseException as error:
        partial = {'before': before, 'status': 'call_failed',
                   'wall_seconds_until_error': time.perf_counter() - started}
        try:
            partial.update(after_error=memory_snapshot(cuda),
                           max_allocated_bytes=cuda.max_memory_allocated(),
                           max_reserved_bytes=cuda.max_memory_reserved())
        except Exception as snapshot_error:
            partial['snapshot_error'] = type(snapshot_error).__name__ + ': ' + str(snapshot_error)
        error.allocator_measurement = partial
        raise
    elapsed = time.perf_counter() - started
    # Capture all peaks before any tensor checks or a second operator call.
    peak_allocated = cuda.max_memory_allocated()
    peak_reserved = cuda.max_memory_reserved()
    after = memory_snapshot(cuda)
    return output, {'before': before, 'after': after, 'wall_seconds_synchronized': elapsed,
                    'max_allocated_bytes': peak_allocated, 'max_reserved_bytes': peak_reserved,
                    'increment_peak_allocated_bytes': peak_allocated - before['allocated_bytes'],
                    'increment_peak_reserved_bytes': peak_reserved - before['reserved_bytes'],
                    'single_route_attention_calls': 1,
                    'boundary': 'one route_attention call including internal diagnostics and cold gain cache; input creation and output validation excluded'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', choices=('native', 'local', 'full'), required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--root-admitted', action='store_true')
    args = parser.parse_args()
    runtime = read(ROOT / 'configs/runtime.json')
    target = runtime['gpu_uuid']
    if not args.root_admitted or os.environ.get('CUDA_VISIBLE_DEVICES') != target:
        raise ValueError('explicit root admission and exact configured GPU UUID required')
    output_dir = args.output_dir.absolute()
    if output_dir.is_symlink() or not output_dir.resolve().is_relative_to(HERE):
        raise ValueError('output must stay in this engineering audit directory')
    output_dir.mkdir(parents=True, exist_ok=False)
    result = {'schema': 'r55-single-routing-allocator-audit-v1', 'status': 'started',
              'variant': args.variant, 'gpu_uuid': target, 'pid': os.getpid(),
              'script_sha256': sha(__file__), 'NFE': 0, 'model_weights_loaded': False}
    torch = None
    packed = q = k = v = gain = output = diagnostics = generator = None
    try:
        source_binding = read(HERE / 'ALLOCATOR_SOURCE_BINDING.json')
        for rel, expected in source_binding['files'].items():
            if sha(owned_path(ROOT, rel)) != expected:
                raise ValueError('routing source changed: ' + rel)
        result['source_binding'] = source_binding
        result['source_binding_sha256'] = sha(HERE / 'ALLOCATOR_SOURCE_BINDING.json')
        result['selection'] = select_layout(ROOT)
        result['admission'] = resource_snapshot(target)
        put(output_dir / 'BEFORE_CUDA.json', result)
        import torch as imported_torch
        torch = imported_torch
        torch.set_num_threads(1)
        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise RuntimeError('exactly one visible CUDA device required')
        sys.path.insert(0, str(ROOT / 'extensions'))
        from H3TemporalRouter import core
        from H3TemporalRouter.mask import QueryGain
        for module, rel in ((core, 'extensions/H3TemporalRouter/core.py'),
                            (sys.modules[QueryGain.__module__], 'extensions/H3TemporalRouter/mask.py')):
            if Path(module.__file__).resolve() != (ROOT / rel).resolve():
                raise ValueError('loaded routing module path differs')
        result['post_context_admission'] = resource_snapshot(target, os.getpid())
        plan = result['selection']['selected']['plan']
        generator = torch.Generator(device='cuda').manual_seed(26101616)
        packed = torch.randn(1, plan['seq_len'], 3, 56, 128, device='cuda', dtype=torch.bfloat16, generator=generator)
        q, k, v = packed.permute(2, 0, 3, 1, 4).unbind(0)
        if args.variant != 'native':
            values = torch.ones(SHAPE) if args.variant == 'full' else torch.zeros(SHAPE)
            if args.variant == 'local':
                values[list(LOCAL_BINS)] = 1
            gain = QueryGain(values, SHAPE)
        diagnostics = []
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        result['measurement_setup'] = {
            'input': 'synthetic BF16 QKV with actual largest packed layout',
            'qkv_shape': list(q.shape), 'seed': 26101616, 'warmup_calls': 0,
            'cache': 'fresh process; empty_cache once after input creation and before measurement',
            'local_bins': list(LOCAL_BINS), 'diagnostics': True,
            'torch': torch.__version__, 'cuda': torch.version.cuda,
            'device_name': torch.cuda.get_device_name(),
            'allocator_env': {k: os.environ.get(k) for k in ('PYTORCH_ALLOC_CONF', 'PYTORCH_CUDA_ALLOC_CONF')}}
        output, result['measurement'] = measure_once(torch.cuda, lambda: core.route_attention(
            q, k, v, 56, plan, mode='native' if args.variant == 'native' else 'mass_preserve',
            query_gain=gain, diagnostics=diagnostics))
        # This check happens after the measurement record has captured peaks.
        result['post_measurement_checks'] = {'output_shape': list(output.shape),
                                              'finite': bool(torch.isfinite(output).all())}
        if not result['post_measurement_checks']['finite']:
            raise ValueError('nonfinite routing output')
        result['status'] = 'complete'
    except BaseException as error:
        result.update(status='failed', error=type(error).__name__ + ': ' + str(error))
        if hasattr(error, 'resource_snapshot'):
            result['rejected_resource_snapshot'] = error.resource_snapshot
        if hasattr(error, 'allocator_measurement'):
            result['failed_measurement'] = error.allocator_measurement
        raise
    finally:
        packed = q = k = v = gain = output = diagnostics = generator = None
        if torch is not None and torch.cuda.is_initialized():
            try:
                torch.cuda.synchronize()
                torch.cuda.empty_cache()
                result['after_cleanup'] = memory_snapshot(torch.cuda)
            except Exception as error:
                result['cleanup_error'] = type(error).__name__ + ': ' + str(error)
        result['scope'] = 'standalone operator memory evidence; existing correctness and decoder gates remain separate; no resident DiT/TE/VAE or end-to-end capacity proof'
        put(output_dir / 'RESULT.json', result)
    print(json.dumps({'status': result['status'], 'result': str(output_dir / 'RESULT.json'),
                      'measurement': result['measurement']}, allow_nan=False))


if __name__ == '__main__':
    main()
