"""Standalone AWQ IS/CF batch; no GPU work unless --run is explicit."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import random
import re
import tempfile
import subprocess
import sys
import time
import traceback
import types

ROOT = Path(__file__).resolve().parent
MODEL_ID = 'Qwen/Qwen2.5-VL-72B-Instruct-AWQ'
REVISION = 'c8b87d4b81f34b6a147577a310d7e75f0698f6c2'
COMMIT = '2dcf8900ee65197f43854c76f61c66a32bb8dbfc'
METRICS = {'instruction_satisfaction': ('compliance', 'QwenVLEvaluator'),
           'content_fidelity': ('fidelity', 'QwenVLContentFidelityEvaluator')}


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def official_modules():
    provenance = json.loads((ROOT / 'official_source_sha256.json').read_text())
    for name, expected in provenance['sha256'].items():
        actual = hashlib.sha256((ROOT / 'official_source' / name).read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f'Official source hash changed: {name}')
    metrics = ROOT / 'official_source/metrics'
    sys.path.insert(0, str(metrics))
    for package in ('compliance', 'fidelity'):
        module = types.ModuleType(package)
        module.__path__ = [str(metrics / package)]
        sys.modules[package] = module
    return {name: importlib.import_module(f'{package}.{name}')
            for name, (package, _) in METRICS.items()}


def gpu_admission(visible, minimum_free_mib=36000):
    """NVML CLI inspection only: refuse every card with any compute process."""
    cards = [part.strip() for part in visible.split(',') if part.strip()]
    if len(cards) != 2 or len(set(cards)) != 2:
        raise RuntimeError('Exactly two distinct explicit GPU indices or UUIDs are required')
    occupied = subprocess.check_output([
        'nvidia-smi', '--query-compute-apps=gpu_uuid', '--format=csv,noheader'], text=True).splitlines()
    occupied = {line.strip() for line in occupied}
    evidence = []
    for card in cards:
        row = subprocess.check_output([
            'nvidia-smi', '-i', card, '--query-gpu=uuid,memory.free,memory.total',
            '--format=csv,noheader,nounits'], text=True).strip().split(',')
        if len(row) != 3:
            raise RuntimeError(f'Cannot resolve GPU: {card}')
        uuid, free, total = row[0].strip(), int(row[1]), int(row[2])
        if uuid in occupied:
            raise RuntimeError(f'GPU {card} has an existing compute process; refusing allocation')
        if free < minimum_free_mib:
            raise RuntimeError(f'GPU {card} has only {free} MiB free')
        evidence.append({'selector': card, 'uuid': uuid, 'free_mib': free, 'total_mib': total})
    if len({x['uuid'] for x in evidence}) != 2:
        raise RuntimeError('GPU selectors resolve to the same physical card')
    return evidence


def remap_job(job, mappings):
    job = dict(job)
    for key in ('metadata_file', 'source_frames_parent', 'target_frames_parent', 'video'):
        value = job.get(key)
        if not value:
            continue
        for original, replacement in mappings:
            if value == original or value.startswith(original.rstrip('/') + '/'):
                job[key] = replacement.rstrip('/') + value[len(original.rstrip('/')):]
                break
    return job


def job_ready(job):
    stem = Path(job['metadata']['src_video_name']).stem
    required = [Path(job['metadata_file']), Path(job['source_frames_parent']) / stem,
                Path(job['target_frames_parent']) / stem]
    if not all(path.exists() for path in required):
        return False
    if 'valid_frames' in job:
        for folder in required[1:]:
            receipt = folder / 'PREPARED.json'
            if not receipt.exists():
                return False
            prepared = json.loads(receipt.read_text())
            if prepared['frames'] != job['valid_frames'] or len(list(folder.glob('*.png'))) != job['valid_frames']:
                return False
    return True


def explicit_device_map():
    mapping = {'visual': 0, 'model.embed_tokens': 0, 'model.norm': 1, 'lm_head': 1}
    mapping.update({f'model.layers.{i}': 0 if i < 40 else 1 for i in range(80)})
    return mapping


def load_shared(model_path, modules):
    import torch
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
    # Explicit split excludes CPU/disk before loading, and leaves activation headroom.
    device_map = explicit_device_map()
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        str(model_path), torch_dtype='auto', device_map=device_map,
        max_memory={0: '36GiB', 1: '36GiB'}, local_files_only=True)
    processor = AutoProcessor.from_pretrained(str(model_path), local_files_only=True)
    evaluators = {}
    for name, (package, class_name) in METRICS.items():
        # Only loading is adapted; every scoring/preprocessing method is inherited unchanged.
        evaluator = getattr(modules[name], class_name).__new__(getattr(modules[name], class_name))
        evaluator.model_path = str(model_path)
        evaluator.device = 'auto'
        evaluator.model = model
        evaluator.processor = processor
        evaluator.process_vision_info = importlib.import_module(f'{package}.qwen_vl_utils').process_vision_info
        evaluators[name] = evaluator
    return evaluators, model


@contextmanager
def official_frame_parents(job):
    """Expose immutable six-digit prepared frames through official five-digit names."""
    stem = Path(job['metadata']['src_video_name']).stem
    parents = [Path(job[key]) for key in ('source_frames_parent', 'target_frames_parent')]
    with tempfile.TemporaryDirectory(prefix='qwen_frame_alias_') as temporary:
        adapted = []
        for index, parent in enumerate(parents):
            folder = parent / stem
            files = []
            for extension in ('.jpg', '.png'):
                files = sorted(folder.glob('*' + extension))
                if files:
                    break
            if not files:
                raise ValueError(f'No official-supported frames in {folder}')
            if all(re.fullmatch(r'\d{5}', file.stem) for file in files):
                adapted.append(str(parent))
                continue
            if not all(file.stem.isdigit() for file in files):
                raise ValueError(f'Non-numeric frame names in {folder}')
            view_parent = Path(temporary) / str(index)
            view = view_parent / stem
            view.mkdir(parents=True)
            for file in files:
                (view / f'{int(file.stem):05d}{file.suffix}').symlink_to(file.resolve())
            adapted.append(str(view_parent))
        yield adapted


def evaluate_one(job, metric, module, evaluator, output, configuration):
    import numpy as np
    import torch
    result = {key: job[key] for key in ('task_id', 'dataset', 'method')}
    result.update(job_id=job['id'], cohort=job.get('cohort', 'main'), metric=metric,
                  official_commit=COMMIT, status='running', score=None,
                  started=time.time(), evaluation_seed=0, evaluator=configuration)
    try:
        random.seed(0)
        np.random.seed(0)
        torch.manual_seed(0)
        from ivebench_utils import load_video_info
        rows = load_video_info(job['metadata_file'], metric)
        if len(rows) != 1 or rows[0]['src_video_name'] != job['metadata']['src_video_name']:
            raise ValueError('Metadata file must contain the one matching job')
        with official_frame_parents(job) as parents:
            result['frame_filename_adapter'] = 'read-only five-digit symlink views when needed; frame bytes/order unchanged'
            row = getattr(module, metric + '_single_video')(evaluator, rows[0], *parents)
        score = float(row['video_results'])
        result['detail'] = row
        if row.get('error') or not math.isfinite(score) or not 1 <= score <= 5:
            raise RuntimeError(f'Official metric failure: {row}')
        result.update(status='done', score=score)
    except Exception as exc:
        result.update(status='failed', error=str(exc), traceback=traceback.format_exc())
    finally:
        result['wall_seconds'] = time.time() - result['started']
        atomic(output, result)
    return result['status'] == 'done'


def main(args):
    mappings = [tuple(item.split('=', 1)) for item in args.path_map]
    jobs = [remap_job(job, mappings) for job in json.loads(Path(args.manifest).read_text())['jobs']]
    output_root = Path(args.output)
    ready = [job for job in jobs if job_ready(job)]
    if not args.run:
        print(json.dumps({'mode': 'dry_run_cpu_only', 'jobs': len(jobs), 'ready': len(ready),
                          'pending_inputs': [job['id'] for job in jobs if not job_ready(job)],
                          'output': str(output_root), 'model_id': MODEL_ID, 'revision': REVISION}, indent=2))
        return
    if not ready:
        raise RuntimeError('No staged inputs are ready; no model was loaded')
    visible = os.environ.get('CUDA_VISIBLE_DEVICES', '')
    admission = gpu_admission(visible)
    output_root.mkdir(parents=True, exist_ok=True)
    lock = (output_root / 'batch.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    import torch
    torch.set_num_threads(4)
    config = json.loads((Path(args.model) / 'config.json').read_text())
    expected = {'bits': 4, 'group_size': 128, 'quant_method': 'awq', 'version': 'gemm', 'zero_point': True}
    if any(config.get('quantization_config', {}).get(key) != value for key, value in expected.items()):
        raise RuntimeError('Unexpected checkpoint quantization config')
    modules = official_modules()
    evaluators, model = load_shared(Path(args.model), modules)
    import importlib.metadata
    configuration = {'configuration_id': 'qwen25vl72b_awq4bit_' + REVISION[:12],
                     'model_id': MODEL_ID, 'revision': REVISION, 'quantization_config': config['quantization_config'],
                     'dtype': str(model.dtype), 'torch_dtype_requested': 'auto', 'original_precision_reproduction': False,
                     'gpu_admission': admission, 'max_memory': {'0': '36GiB', '1': '36GiB'},
                     'device_map': model.hf_device_map,
                     'packages': {name: importlib.metadata.version(name) for name in ['torch', 'transformers', 'autoawq', 'accelerate', 'triton']}}
    atomic(output_root / 'evaluator_configuration.json', configuration)
    for job in ready:
        if Path(job['id']).name != job['id'] or job['id'] in ('.', '..'):
            raise ValueError('Unsafe job id')
        for metric in METRICS:
            target = output_root / 'results' / job['id'] / (metric + '.json')
            if target.exists():
                previous = json.loads(target.read_text())
                if previous.get('status') == 'done' and previous.get('evaluator', {}).get('configuration_id') == configuration['configuration_id']:
                    continue
            for attempt in range(1, args.retries + 1):
                if evaluate_one(job, metric, modules[metric], evaluators[metric], target, configuration):
                    break
                atomic(target.parent / (metric + f'.failed_attempt_{attempt}.json'), json.loads(target.read_text()))
    del evaluators, model


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True, help='Separate AWQ result root; do not use original-precision result root')
    parser.add_argument('--model', default=str(ROOT.parent / 'weights/Qwen2.5-VL-72B-Instruct-AWQ'))
    parser.add_argument('--path-map', action='append', default=[], metavar='OLD=NEW')
    parser.add_argument('--retries', type=int, default=3)
    parser.add_argument('--run', action='store_true', help='Explicitly permit CUDA load after two empty-card checks')
    main(parser.parse_args())
