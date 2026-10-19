"""Offline frozen graph and completed-source validation. No GPU/service operations."""
import hashlib
import json
from pathlib import Path
import sys

PROTOCOL_SHA = '48b89d1b0118e742ef057647b2aea41fde9ae1f78d4f2b5e4051822253750770'

def check(root, *, require_source=True):
    root = Path(root)
    assert hashlib.sha256((root/'configs/protocol.json').read_bytes()).hexdigest() == PROTOCOL_SHA
    parent = json.loads((root/'audit/parent_graph.json').read_text())
    graph = json.loads((root/'configs/r13_s05_one_step_fork.json').read_text())
    canonical = json.loads(json.dumps(graph).replace('timing_one_step_fork_r13_20261016',
        'timing_counterfactual_r10_20261016').replace('r13_s05_one_step_fork','r10_s05_fixed_full_probe'))
    retained = set(parent)-{'7','8','10','11','12','13','14','50','52'}
    assert set(canonical) == retained|{'60'}
    assert all(canonical[k] == parent[k] for k in retained), 'conditioning/model/noise/sigma graph changed'
    assert graph['60'] == {'class_type':'H3OneStepForkAudit','inputs':{
        'model':['41',0],'positive':['51',0],'noise':['6',0],'sigmas':['9',0],'latent_image':['51',1],
        'source_manifest':'/data5/researcher/h3_runs/timing_one_step_fork_r13_20261016/configs/source_manifest.json',
        'run_id':'r13_s05_one_step_fork','audit_dir':'/data5/researcher/h3_runs/timing_one_step_fork_r13_20261016/audit/fork'}}
    assert json.loads((root/'configs/queue.json').read_text()) == {'jobs':['r13_s05_one_step_fork'],'sealed':True}
    source = json.loads((root/'configs/source_manifest.json').read_text())
    if require_source:
        sys.path.insert(0,str(root/'extensions'))
        from H3OneStepForkAudit.core import Source, POINTS
        bound = Source(root/'configs/source_manifest.json')
        assert str(bound.root) == '/data5/researcher/h3_runs/timing_counterfactual_r10_20261016'
        for n in POINTS:
            bound.input(n)
            for step, branch in [(n,'native'),(n,'full'),(n+1,'native')]:bound.endpoint(step,branch)
        assert source['gpu_uuid']=='GPU-REDACTED'
    return {'validated':True,'source_required':require_source,'source_status':source['status'],
            'NFE':6,'Euler_updates':0,'sampler_callbacks':0,'protocol_sha256':PROTOCOL_SHA,
            'graph_scope':'same conditioning/noise/model/full schedule; report-only diagnostic output'}
