"""Task-local MF admission: actual measured peak plus margin and own-card cap."""
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent


def decide(rows, current_uid, gpu_uuid, free_bytes, required_bytes):
    own_cards = {r['gpu_uuid'] for r in rows if r.get('uid') == current_uid}
    if len(own_cards | {gpu_uuid}) > 2:
        raise ValueError('two own GPU card cap exceeded')
    if any(r['gpu_uuid'] == gpu_uuid and r.get('uid') == current_uid for r in rows):
        raise ValueError('another own job already occupies selected GPU')
    if free_bytes < required_bytes:
        raise ValueError('insufficient free memory for measured tracker peak plus margin')
    return {'planned_owned_GPUs': sorted(own_cards | {gpu_uuid}), 'required_free_bytes': required_bytes,
            'actual_free_bytes': free_bytes, 'foreign_compute_allowed': True, 'compute_rows': rows}


def check_gpu(uuid):
    if not isinstance(uuid, str) or not uuid.startswith('GPU-') or os.environ.get('CUDA_VISIBLE_DEVICES') != uuid:
        raise ValueError('exact admitted GPU UUID required')
    raw = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid',
                                   '--format=csv,noheader,nounits'], text=True, timeout=5)
    rows = []
    for line in raw.splitlines():
        pid, gpu = [v.strip() for v in line.split(',')]
        process = Path('/proc') / pid
        rows.append({'pid': int(pid), 'gpu_uuid': gpu, 'uid': process.stat().st_uid if process.exists() else None})
    memory = subprocess.check_output(['nvidia-smi', '-i', uuid, '--query-gpu=memory.free,memory.used',
                                      '--format=csv,noheader,nounits'], text=True, timeout=5)
    free, used = [int(v.strip()) for v in memory.strip().split(',')]
    required = json.loads((HERE / 'MEMORY_REQUIREMENT.json').read_text())['require_free_bytes']
    result = decide(rows, os.getuid(), uuid, free * 1024**2, required)
    result['selected_memory_MiB'] = used
    return result
