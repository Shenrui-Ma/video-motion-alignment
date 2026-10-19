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
    graph=json.loads((root/'configs/r12_s05_native_observer.json').read_text())
    canonical=json.loads(json.dumps(graph).replace('timing_native_observer_r12_20261016','timing_spatial_r3_20261016').replace('r12_s05_native_observer','r3_s05_full_6to14'))
    expected={'class_type':'H3NativeObserverRouter','inputs':{'model':['41',0],'positive':['51',0],
        'policy':'native_observer','fixed_indices':'','run_id':'r12_s05_native_observer','audit_dir':'/data5/researcher/h3_runs/timing_native_observer_r12_20261016/audit/counterfactual'}}
    if graph['50']!=expected:raise ValueError('counterfactual node parameters changed')
    canonical['50']=parent['50']
    if canonical!=parent:raise ValueError('scientific graph changed beyond diagnostic node/admin')
    queue=json.loads((root/'configs/queue.json').read_text())
    if queue!={'jobs':['r12_s05_native_observer'],'sealed':True}:raise ValueError('queue changed')
    warmup=json.loads((root/'audit/parent_warmup_gate.json').read_text())
    values=warmup['seconds_per_iteration_seen']
    if warmup['job']!='r3_s05_spatial_bench2' or warmup['limit']!=100.0 or not values or any(not math.isfinite(v) or not 0<v<=100 for v in values):
        raise ValueError('parent backend warmup invalid')
    bench=json.loads((root/'audit/parent_bench_graph.json').read_text())
    for key in ('width','height','length','prompt'):
        if bench['5']['inputs'][key]!=parent['5']['inputs'][key]:raise ValueError('warmup conditioning geometry differs')
    for node in ('1','2','3','4','41','8','21','22'):
        if bench[node]!=parent[node]:raise ValueError('warmup backend/input recipe differs')
    return {'validated':True,'scope':'R3 spatial warmup supports backend/shape admission only; new variableNFE observer wrapper correctness requires separateCPU and pairedGPU checks',
            'timings':values,'target_run':'r3_s05_full_6to14','expected_NFE':'20+actual_full_count','euler_updates':20,'evidence':binding}
