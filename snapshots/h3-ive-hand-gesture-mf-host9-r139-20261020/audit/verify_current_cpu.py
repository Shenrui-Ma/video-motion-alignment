"""Small deployment check for new manifests against the existing host9 runtime."""
from pathlib import Path
import os, sys, time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import read, save, sha, bound, verify_seal, validate_case

started = time.monotonic()
assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
verify_seal()
plan = read(ROOT / 'configs/PLAN.json')
domains = []
for key in plan['groups']:
    folder = ROOT / 'cases' / key
    manifest = read(folder / 'INPUTS.json')
    for role in ['source'] + [row['role'] for row in manifest['targets']]:
        validate_case(folder, role)
    domains.append({'case': key, 'frames': manifest['evaluation_frames'],
                    'fps': manifest['evaluation_fps'], 'input': bound(folder / 'INPUTS.json')})
sys.path.insert(0, str(ROOT / 'runtime/ive/metric_runtime'))
from ive_mf_adapter import verify_vendor
verify_vendor()
runtime = read(ROOT / 'configs/RUNTIME.json')
weight = ROOT / 'runtime/ive/weights/baseline_offline.pth'
assert sha(weight) == sha(runtime['checkpoint']) == runtime['checkpoint_sha256']
import torch
assert not torch.cuda.is_initialized()
for folder in ['audit', 'state', 'results']:
    target = ROOT / folder
    target.mkdir(exist_ok=True)
    assert os.access(target, os.W_OK)
result = {'passed': True, 'seal': bound(ROOT / 'SEAL.json'),
          'runtime_actual': str((ROOT / 'runtime').resolve()),
          'checkpoint': bound(weight), 'checkpoint_actual': str(weight.resolve()),
          'domains': domains, 'CUDA_initialized': False, 'torch': torch.__version__,
          'wall_seconds': time.monotonic() - started, 'unix': time.time()}
save(ROOT / 'audit/TARGET_CPU_VERIFIED.json', result)
print({'passed': True, 'domains': domains, 'receipt_sha256': sha(ROOT / 'audit/TARGET_CPU_VERIFIED.json')})
