"""Validate the explicitly reused R7 warmup before starting the R8 service."""
import hashlib
import json
import math
from pathlib import Path


def validate_reused_warmup(root):
    root = Path(root)
    binding = json.loads((root / 'audit/parent_provenance_binding.json').read_text())
    for relative, expected in binding['files'].items():
        path = root / relative
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('parent evidence path escaped task root')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('parent evidence changed: ' + relative)
    warmup = json.loads((root / 'audit/parent_warmup_gate.json').read_text())
    if warmup['job'] != 'r7_s05_normal_native_bench2' or warmup['limit'] != 100.0:
        raise ValueError('unexpected parent warmup')
    measured = warmup['seconds_per_iteration_seen']
    if not measured or any(not math.isfinite(v) or not 0 < v <= 100 for v in measured):
        raise ValueError('parent warmup failed its existing100s limit')
    parent = json.loads((root / 'audit/parent_native_graph.json').read_text())
    bench = json.loads((root / 'audit/parent_bench_graph.json').read_text())
    formal = json.loads((root / 'configs/r8_s05_normal_feedback.json').read_text())
    for graph in (parent, bench, formal):
        if [graph['5']['inputs'][key] for key in ('width', 'height', 'length')] != [1024, 576, 141]:
            raise ValueError('parent warmup geometry differs')
        if graph['8']['inputs']['sampler_name'] != 'euler' or graph['41']['inputs']['shift_video'] != 12 or graph['41']['inputs']['shift_audio'] != 3:
            raise ValueError('sampler/backend recipe changed')
        if any('lora' in node['class_type'].lower() or 'sage' in node['class_type'].lower() for node in graph.values()):
            raise ValueError('unexpected approximation or LoRA in frozen graph')
    # Verify all scientific graph data except the explicitly new feedback node.
    canonical = json.loads(json.dumps(formal).replace('timing_normal_feedback_r8_20261016',
        'timing_normal_replay_r7_20261016').replace('r8_s05_normal_feedback', 'r7_s05_normal_native_x0'))
    canonical['50'] = parent['50']
    if canonical != parent:
        raise ValueError('formal graph changed beyond router/admin fields')
    return {'schema': 'h3-r8-reused-warmup-v1', 'validated': True,
            'basis': 'Immediately preceding R7 same-host1024 native warmup; no new benchmark run',
            'parent_remote_root': binding['parent_remote_root'],
            'parent_job': warmup['job'], 'seconds_per_iteration_seen': measured,
            'limit_seconds_per_iteration': 100.0,
            'new_feedback_overhead': 'not measured by this inherited warmup; formal walltime/readout audit required',
            'input_model_core_backend_checks': 'unchanged graph outside feedback; model/core runtime hashes checked by launch',
            'evidence_sha256': binding['files']}
