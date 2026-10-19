"""Reuse host9 R3 resource warmup; this does not validate the off wrapper."""
import hashlib
import json
import math
from pathlib import Path

def validate(root):
    root = Path(root)
    binding = json.loads((root / 'configs/warmup_reuse_manifest.json').read_text())
    for rel, item in binding['files'].items():
        raw = (root / rel).read_bytes()
        if len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('changed archived warmup evidence: ' + rel)
    evidence = root / 'audit/r3_warmup'
    gate = json.loads((evidence / 'gate.json').read_text())
    history = json.loads((evidence / 'history.json').read_text())
    graph = json.loads((evidence / 'graph.json').read_text())
    provenance = json.loads((evidence / 'runtime_provenance.json').read_text())
    if gate['job'] != 'r3_s05_spatial_bench2' or gate['limit'] != 100.0:
        raise ValueError('wrong host9 warmup')
    values = gate['seconds_per_iteration_seen']
    if not values or any(not math.isfinite(x) or not 0 < x <= 100 for x in values):
        raise ValueError('invalid historical timing evidence')
    if history['status']['status_str'] != 'success' or not history['status']['completed'] or history['prompt'][2] != graph:
        raise ValueError('parent warmup did not execute the archived graph successfully')
    current = json.loads((root / 'configs/r14_s05_seed1313_native_host9.json').read_text())
    for key in ['width', 'height', 'length', 'prompt', 'semantic_fps', 'phase_frames', 'ref_image']:
        if current['5']['inputs'][key] != graph['5']['inputs'][key]:
            raise ValueError('warmup recipe changed: ' + key)
    for node in ['1','2','3','4','41','8','21','22']:
        if current[node] != graph[node]: raise ValueError('warmup model/source changed')
    models = json.loads((root / 'configs/model_hashes_host9.json').read_text())
    for name, item in provenance['models'].items():
        if item['prior_full_sha256'] != models[name]['sha256']:
            raise ValueError('warmup model differs')
    code = ['scripts/compatibility_bootstrap.py', 'scripts/int8_row_chunking.py',
            'scripts/backend_dispatch_audit.py', 'extensions/H3TemporalRouter/layout.py',
            'extensions/H3PhaseRoPE/audited_flash.py', 'extensions/H3EventEmphasis/core.py']
    for rel in code:
        if hashlib.sha256((root / rel).read_bytes()).hexdigest() != provenance['code'][rel]:
            raise ValueError('warmup numerical helper changed: ' + rel)
    return {'status':'pass', 'new_gpu_warmup':False, 'host':'.9', 'warmup_job':gate['job'],
            'timings':values, 'scope':'Historical same-host resource/backend recipe only; current wrapper and current speed are not inferred',
            'backend_helpers_checked':code}

if __name__ == '__main__': print(json.dumps(validate(Path(__file__).resolve().parents[1]), indent=2))
