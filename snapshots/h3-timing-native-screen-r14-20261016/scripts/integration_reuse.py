"""Verify unchanged runtime against the successful real Comfy CPU R9 smoke."""
import hashlib
import json
from pathlib import Path


def validate(root):
    root = Path(root)
    binding = json.loads((root / 'configs/integration_reuse_manifest.json').read_text())
    for relative, expected in binding['evidence_sha256'].items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
            raise ValueError('changed parent CPU evidence: ' + relative)
    manifest = json.loads((root / 'audit/parent_r9_bundle_manifest.json').read_text())
    log = (root / 'audit/parent_r9_real_comfy_cpu_smoke.log').read_text()
    lines = [line.split('=', 1)[1] for line in log.splitlines() if line.startswith('H3_FEEDBACK_CPU_SMOKE=')]
    if len(lines) != 1:
        raise ValueError('expected exactly one successful parent CPU smoke report')
    report = json.loads(lines[0])
    required = ['success', 'actual_node_loader_module_alias_tested', 'off_equals_native',
                'fixed_mask_equals_feedback', 'expanded_readout_common_x0_and_final_bitwise_equal']
    if not all(report.get(key) is True for key in required):
        raise ValueError('parent real CPU integration did not pass')
    if report['device'] != 'cpu' or report['CUDA_initialized'] or report['loaded_model_weights']:
        raise ValueError('unexpected parent integration scope')
    checked = []
    for relative in manifest['files']:
        if not relative.startswith('extensions/') or not relative.endswith('.py'):
            continue
        data = (root / relative).read_bytes()
        # Only the owned audit-root path is retargeted; H3 math/observer are exact.
        data = data.replace(b'timing_native_screen_r14_20261016', b'timing_hold_control_r9_20261016')
        if hashlib.sha256(data).hexdigest() != manifest['files'][relative]:
            raise ValueError('runtime changed since parent CPU integration: ' + relative)
        checked.append(relative)
    if hashlib.sha256((root / 'extensions/H3FeedbackRouter/core.py').read_bytes()).hexdigest() != report['core_sha256']:
        raise ValueError('feedback core differs from actually tested core')
    return {'status': 'pass', 'parent': 'R9 real Comfy CPU smoke', 'runtime_files_checked': checked,
            'new_cpu_smoke': False, 'new_gpu_benchmark': False,
            'scope': 'Runtime implementation reused; new native graph and seed independently covered by R14 CPU tests'}


if __name__ == '__main__':
    print(json.dumps(validate(Path(__file__).resolve().parents[1]), indent=2))
