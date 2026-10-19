"""Frozen R3 target and same-host resource warmup provenance; no GPU operations."""
import hashlib
import json
import math
from pathlib import Path


def check(root):
    root=Path(root)
    binding=json.loads((root/'audit/parent_binding.json').read_text())
    for rel,expected in binding['files'].items():
        p=root/rel
        if not p.resolve().is_relative_to(root.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            raise ValueError('parent evidence changed: '+rel)
    parent=json.loads((root/'audit/parent_full_graph.json').read_text())
    graph=json.loads((root/'configs/r10_s05_fixed_full_probe.json').read_text())
    canonical=json.loads(json.dumps(graph).replace('timing_counterfactual_r10_20261016','timing_spatial_r3_20261016').replace('r10_s05_fixed_full_probe','r3_s05_full_6to14'))
    expected={'class_type':'H3CounterfactualRouter','inputs':{'model':['41',0],'positive':['51',0],
        'run_id':'r10_s05_fixed_full_probe','audit_dir':'/data5/researcher/h3_runs/timing_counterfactual_r10_20261016/audit/counterfactual'}}
    if graph['50']!=expected:raise ValueError('counterfactual node parameters changed')
    canonical['50']=parent['50']
    if canonical!=parent:raise ValueError('scientific graph changed beyond diagnostic node/admin')
    queue=json.loads((root/'configs/queue.json').read_text())
    if queue!={'jobs':['r10_s05_fixed_full_probe'],'sealed':True}:raise ValueError('queue changed')
    warmup=json.loads((root/'audit/parent_warmup_gate.json').read_text())
    values=warmup['seconds_per_iteration_seen']
    if warmup['job']!='r3_s05_spatial_bench2' or warmup['limit']!=100.0 or not values or any(not math.isfinite(v) or not 0<v<=100 for v in values):
        raise ValueError('parent backend warmup invalid')
    bench=json.loads((root/'audit/parent_bench_graph.json').read_text())
    for key in ('width','height','length','prompt'):
        if bench['5']['inputs'][key]!=parent['5']['inputs'][key]:raise ValueError('warmup conditioning geometry differs')
    for node in ('1','2','3','4','41','8','21','22'):
        if bench[node]!=parent[node]:raise ValueError('warmup backend/input recipe differs')
    return {'validated':True,'scope':'R3 spatial warmup supports backend/shape admission only; new29NFE wrapper correctness requires separateCPU and pairedGPU checks',
            'timings':values,'target_run':'r3_s05_full_6to14','expected_NFE':29,'euler_updates':20,'evidence':binding}
