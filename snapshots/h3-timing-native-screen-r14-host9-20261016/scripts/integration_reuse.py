"""Gate launch on this package's actual host9 real Comfy CPU smoke."""
import hashlib
import json
from pathlib import Path

CORE = '/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI'
LOG = 'audit/real_comfy_cpu_smoke_host9.log'

def runtime_hashes(root):
    root = Path(root)
    paths = list((root / 'extensions').rglob('*.py'))
    paths += [root / 'scripts/compatibility_bootstrap.py', root / 'tests/feedback_wrapper_smoke.py']
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if '__pycache__' not in p.parts}

def validate(root):
    root = Path(root)
    path = root / LOG
    if not path.is_file():
        raise ValueError('host9 actual Comfy CPU smoke pending: ' + LOG)
    lines = [line.split('=',1)[1] for line in path.read_text().splitlines()
             if line.startswith('H3_FEEDBACK_CPU_SMOKE=')]
    if len(lines) != 1: raise ValueError('expected exactly one successful real host9 CPU report')
    report = json.loads(lines[0])
    required = ['success', 'actual_node_loader_module_alias_tested', 'off_equals_native',
                'fixed_mask_equals_feedback', 'expanded_readout_common_x0_and_final_bitwise_equal']
    if not all(report.get(k) is True for k in required): raise ValueError('host9 CPU integration failed')
    if report.get('device') != 'cpu' or report.get('CUDA_initialized') is not False or report.get('loaded_model_weights') is not False:
        raise ValueError('CPU scope invalid')
    if report.get('comfy_root') != CORE: raise ValueError('wrong Comfy host/runtime')
    if report.get('runtime_sha256') != runtime_hashes(root): raise ValueError('runtime changed since host9 smoke')
    expected = json.loads((root / 'configs/parent_core_hashes.json').read_text())
    if report.get('comfy_source_sha256') != expected: raise ValueError('Comfy core changed since host9 smoke')
    if report.get('core_sha256') != runtime_hashes(root)['extensions/H3FeedbackRouter/core.py']:
        raise ValueError('feedback core mismatch')
    return {'status':'pass', 'new_gpu_benchmark':False, 'host':'.9',
            'scope':'Actual existing CPU smoke for this exact host9 package; no model weights or CUDA',
            'log_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

if __name__ == '__main__': print(json.dumps(validate(Path(__file__).resolve().parents[1]), indent=2))
