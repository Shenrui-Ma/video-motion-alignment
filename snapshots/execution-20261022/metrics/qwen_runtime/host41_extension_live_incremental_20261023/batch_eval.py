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


def gpu_admission(visible, minimum_free_mib=37500):
    """Read-only admission for explicitly authorized shared GPUs 0/1, keeping at least 8 GiB free."""
    cards = [part.strip() for part in visible.split(',') if part.strip()]
    if len(cards) != 2 or len(set(cards)) != 2:
        raise RuntimeError('Exactly two distinct explicit GPU indices or UUIDs are required')
    occupied = subprocess.check_output([
        'nvidia-smi', '--query-compute-apps=gpu_uuid', '--format=csv,noheader'], text=True).splitlines()
    occupied = {line.strip() for line in occupied}
    evidence = []
    for card in cards:
        row = subprocess.check_output([
            'nvidia-smi', '-i', card, '--query-gpu=uuid,memory.free,memory.total,utilization.gpu',
            '--format=csv,noheader,nounits'], text=True).strip().split(',')
        if len(row) != 4:
            raise RuntimeError(f'Cannot resolve GPU: {card}')
        uuid, free, total = row[0].strip(), int(row[1]), int(row[2])
        if not row[3].strip().isdigit():
            raise RuntimeError(f'GPU {card} health telemetry unavailable: {row[3].strip()}')
        if free < minimum_free_mib:
            raise RuntimeError(f'GPU {card} has only {free} MiB free')
        if total < 37500 or uuid not in ('GPU-REPLACE-WITH-DEVICE-UUID','GPU-REPLACE-WITH-DEVICE-UUID'):
            raise RuntimeError('Unexpected card identity')
        evidence.append({'selector': card, 'uuid': uuid, 'free_mib': free, 'total_mib': total, 'shared': uuid in occupied, 'own_allocator_limit_mib': 30720, 'reserved_free_mib_at_admission': free-30720})
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
    mapping = {'visual': 0, 'model.embed_tokens': 0, 'model.rotary_emb': 0, 'model.norm': 1, 'lm_head': 1}
    mapping.update({f'model.layers.{i}': 0 if i < 40 else 1 for i in range(80)})
    return mapping


def install_host_bridge():
    """Work around verified peer-copy corruption on this host without changing tensor values."""
    import torch
    original = torch.Tensor.to
    count = {'transfers': 0}
    def via_host(tensor, *args, **kwargs):
        target = kwargs.get('device')
        if args:
            first=args[0]
            if isinstance(first,torch.Tensor):target=first.device
            elif isinstance(first,(str,int,torch.device)):target=first
        if target is not None and tensor.is_cuda:
            device=torch.device('cuda',target) if isinstance(target,int) else torch.device(target)
            index=torch.cuda.current_device() if device.index is None else device.index
            if device.type=='cuda' and index != tensor.device.index:
                count['transfers']+=1
                host=original(tensor,device='cpu',non_blocking=False)
                return original(host,*args,**kwargs)
        return original(tensor,*args,**kwargs)
    torch.Tensor.to=via_host
    # Exercise both directions, integer/float tensors, keyword/device-tensor overloads.
    checks=[]
    for a,b in [(0,1),(1,0)]:
        for dtype in [torch.float16,torch.float32,torch.int64,torch.bool]:
            cpu=(torch.arange(8192)%97).to(dtype)
            x=cpu.to('cuda:'+str(a))
            y=x.to(device='cuda:'+str(b))
            z=y.to(x)
            passed=torch.equal(cpu,y.cpu()) and torch.equal(cpu,z.cpu())
            checks.append({'from':a,'to':b,'dtype':str(dtype),'equal':passed})
    if not all(x['equal'] for x in checks):raise RuntimeError('CPU bridge exact-copy check failed')
    atomic(ROOT/'run/host_bridge_validation.json',{'checks':checks,'transfers':count['transfers'],'time':time.time()})
    return count


def load_shared(model_path, modules):
    import torch
    from transformers import AutoConfig, AutoProcessor, Qwen2_5_VLForConditionalGeneration
    # Explicit split excludes CPU/disk before loading, and leaves activation headroom.
    bridge_count = install_host_bridge()
    device_map = explicit_device_map()
    # Initialize both GPUs for the imminent two-device model load.
    for device in (0, 1):
        with torch.cuda.device(device):
            torch.cuda.set_per_process_memory_fraction((30*1024**3)/torch.cuda.get_device_properties(device).total_memory, device=device)
            torch.empty(1, device=f"cuda:{device}")
    model_config = AutoConfig.from_pretrained(str(model_path), local_files_only=True)
    # Checkpoint lm_head is dense FP16, while decoder projections are AWQ INT4.
    model_config.quantization_config['modules_to_not_convert'] = ['visual', 'lm_head']
    model, loading_info = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        str(model_path), config=model_config, torch_dtype=torch.float16, device_map=device_map,
        max_memory={0: '30GiB', 1: '30GiB'}, local_files_only=True, output_loading_info=True)
    atomic(ROOT / 'loading_audit.json', loading_info)
    if loading_info.get('missing_keys') or loading_info.get('unexpected_keys') or loading_info.get('mismatched_keys') or loading_info.get('error_msgs'):
        raise RuntimeError('Checkpoint loading audit failed: ' + str(loading_info))
    assert isinstance(model.lm_head, torch.nn.Linear), 'Checkpoint output head must remain dense'
    packed = [(name, value) for name, value in model.named_buffers() if name.endswith(('.qweight', '.qzeros'))]
    assert packed and all(value.dtype == torch.int32 for _, value in packed), 'AWQ packed buffers must preserve INT32'
    atomic(ROOT / 'packed_buffer_audit.json', {'count': len(packed), 'all_int32': True, 'lm_head': type(model.lm_head).__name__})
    # Non-persistent RoPE buffer is absent from the checkpoint weight map.
    model.model.rotary_emb.to('cuda:0')
    if hasattr(model.model.rotary_emb, 'original_inv_freq'):
        model.model.rotary_emb.original_inv_freq = model.model.rotary_emb.original_inv_freq.to('cuda:0')
    numeric=[]
    def check_once(name):
        done=[0]
        def hook(module, inputs, output):
            if done[0]>=3:return
            done[0]+=1
            value=output[0] if isinstance(output,(tuple,list)) else output
            if not torch.is_tensor(value):return
            finite=bool(torch.isfinite(value).all())
            numeric.append({'module':name,'call':done[0],'finite':finite,'shape':list(value.shape),'dtype':str(value.dtype),'abs_max':float(value.abs().max()) if finite else None})
            atomic(ROOT/'run/first_forward_numeric_audit.json',numeric)
            if not finite:raise RuntimeError('Nonfinite activation in '+name)
        return hook
    model.visual.register_forward_hook(check_once('visual'))
    for i,layer in enumerate(model.model.layers):layer.register_forward_hook(check_once('decoder_'+str(i)))
    model.lm_head.register_forward_hook(check_once('lm_head'))
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
    print(json.dumps({k: result.get(k) for k in ['job_id', 'metric', 'status', 'score', 'wall_seconds', 'error']}), flush=True)
    return result['status'] == 'done'



VERIFIED_INPUT_JOBS = set()
def verify_job_snapshot(job):
    if job['id'] in VERIFIED_INPUT_JOBS:return
    snapshot=json.loads((ROOT/'run/input_snapshot.json').read_text())
    base=ROOT/'staged';stem=Path(job['metadata']['src_video_name']).stem
    parents={Path(job[k])/stem for k in ('source_frames_parent','target_frames_parent')}
    metadata=Path(job['metadata_file']);wanted=[x for x in snapshot['files'] if (base/x['path']).parent in parents or base/x['path']==metadata]
    required_count=sum(len(list(p.glob('*.png')))+1 for p in parents)+1
    if len(wanted)!=required_count:raise RuntimeError('Snapshot file coverage mismatch')
    for x in wanted:
        p=base/x['path'];h=hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
        if p.stat().st_size!=x['size'] or h.hexdigest()!=x['sha256']:raise RuntimeError('Input SHA mismatch: '+str(p))
    VERIFIED_INPUT_JOBS.add(job['id'])
    atomic(ROOT/'run/input_verification'/f"{job['id']}.json",{'status':'passed','files':len(wanted),'time':time.time()})

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
    for job in ready:verify_job_snapshot(job)
    ready_ids={j['id'] for j in ready}
    ready=ready+[j for j in jobs if j['id'] not in ready_ids]
    visible = 'GPU-REPLACE-WITH-DEVICE-UUID,GPU-REPLACE-WITH-DEVICE-UUID'
    os.environ['CUDA_VISIBLE_DEVICES'] = visible
    admission = gpu_admission(visible)
    atomic(output_root / 'actual_gpu_admission.json', {'cuda_visible_devices': visible, 'cards': admission, 'time': time.time()})
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
    configuration = {'configuration_id': 'qwen25vl72b_awq4bit_fp16_cpu_bridge_' + REVISION[:12],
                     'model_id': MODEL_ID, 'revision': REVISION, 'quantization_config': config['quantization_config'],
                     'load_quantization_config': model.config.quantization_config.to_dict() if hasattr(model.config.quantization_config, 'to_dict') else model.config.quantization_config, 'dtype': str(model.dtype), 'torch_dtype_requested': 'float16', 'dense_checkpoint_modules': ['visual', 'lm_head'], 'original_precision_reproduction': False,
                     'attention_implementation': model.config._attn_implementation, 'cross_gpu_transfer': 'exact_cpu_staging_due_to_failed_p2p_test', 'shared_card_memory_limit_gib': 30, 'execution_host': 'H3_HOST_PRIMARY', 'resource_failover_from': 'H3_HOST_AUXILIARY', 'gpu_admission': admission, 'max_memory': {'0': '30GiB', '1': '30GiB'},
                     'device_map': model.hf_device_map,
                     'packages': {name: importlib.metadata.version(name) for name in ['torch', 'transformers', 'autoawq', 'accelerate', 'triton']}}
    atomic(output_root / 'evaluator_configuration.json', configuration)
    for job_index, job in enumerate(ready):
        deadline=time.time()+3600
        while not job_ready(job):
            if time.time()>deadline:raise TimeoutError('Waiting for input '+job['id'])
            time.sleep(10)
        verify_job_snapshot(job)
        if Path(job['id']).name != job['id'] or job['id'] in ('.', '..'):
            raise ValueError('Unsafe job id')
        for metric in METRICS:
            target = output_root / 'results' / job['id'] / (metric + '.json')
            if target.exists():
                previous = json.loads(target.read_text())
                if previous.get('status') == 'done' and previous.get('evaluator', {}).get('configuration_id') == configuration['configuration_id']:
                    continue
            if target.exists():
                # Preserve the original failure and its attempts before a recovery rerun.
                archive = output_root / 'recovery_history' / str(time.time_ns()) / job['id']
                archive.mkdir(parents=True)
                import shutil
                for old_result in target.parent.glob(metric + '*.json'):
                    shutil.copy2(old_result, archive / old_result.name)
            for attempt in range(1, args.retries + 1):
                if evaluate_one(job, metric, modules[metric], evaluators[metric], target, configuration):
                    break
                atomic(target.parent / (metric + f'.failed_attempt_{attempt}.json'), json.loads(target.read_text()))
        if job_index == 0:
            pilot_results = [json.loads((output_root / 'results' / job['id'] / (metric + '.json')).read_text()) for metric in METRICS]
            atomic(output_root / 'first_sample_validation.json', {'job': job['id'], 'results': [{'metric': r['metric'], 'status': r['status'], 'score': r.get('score')} for r in pilot_results]})
            if not all(r['status'] == 'done' for r in pilot_results):
                raise RuntimeError('First sample IS/CF validation failed; full batch not started')
            print('FIRST_SAMPLE_VALIDATED', job['id'], flush=True)
    del evaluators, model
    counts = {'done': 0, 'failed': 0, 'missing': 0}
    for job in ready:
        for metric in METRICS:
            target = output_root / 'results' / job['id'] / (metric + '.json')
            status = json.loads(target.read_text()).get('status') if target.exists() else 'missing'
            counts['done' if status == 'done' else 'missing' if status == 'missing' else 'failed'] += 1
    atomic(output_root / 'batch_completion.json', {'counts': counts, 'time': time.time()})
    if counts['failed'] or counts['missing']:
        raise RuntimeError('Evaluation batch has unresolved results: ' + str(counts))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True, help='Separate AWQ result root; do not use original-precision result root')
    parser.add_argument('--model', default=str(ROOT.parent / 'weights/Qwen2.5-VL-72B-Instruct-AWQ'))
    parser.add_argument('--path-map', action='append', default=[], metavar='OLD=NEW')
    parser.add_argument('--retries', type=int, default=3)
    parser.add_argument('--run', action='store_true', help='Explicitly permit CUDA load after two empty-card checks')
    main(parser.parse_args())
