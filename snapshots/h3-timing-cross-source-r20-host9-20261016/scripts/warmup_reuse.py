"""Verify historical .9 same-geometry backend evidence; no GPU/startup work."""
import hashlib,json
from pathlib import Path

def validate(root):
    root=Path(root);read=lambda p:json.loads(p.read_text())
    pin=read(root/'configs/backend_reuse_manifest.json')
    for rel,row in pin['files'].items():
        if hashlib.sha256((root/rel).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('backend evidence changed: '+rel)
    for rel,sha in pin['unchanged_backend_sha256'].items():
        if hashlib.sha256((root/rel).read_bytes()).hexdigest()!=sha:raise ValueError('backend helper changed: '+rel)
    e=root/'audit/backend_evidence';hist=read(e/'warmup_history.json');g=read(e/'warmup_graph.json')
    if hist['status']['status_str']!='success' or not hist['status']['completed'] or hist['prompt'][2]!=g:raise ValueError('historical warmup not executed successfully')
    if (g['5']['inputs']['width'],g['5']['inputs']['height'],g['5']['inputs']['length'])!=(1312,736,141):raise ValueError('warmup geometry mismatch')
    full=read(e/'full_history.json');router=read(e/'full_router_audit.json')
    if full['status']['status_str']!='success' or not full['status']['completed']:raise ValueError('R3 Full execution failed')
    if router['first_attention']['qkv_shape']!=[1,56,87592,128] or router['completed_calls']!=1000 or router['routed_calls']!=450:raise ValueError('R3 Full geometry/count mismatch')
    models=read(root/'configs/model_hashes_host9.json');prov=read(e/'r3_runtime_provenance.json')
    if not prov['core_matches'] or not all(prov['core_matches'].values()):raise ValueError('historical core mismatch')
    for name,item in prov['models'].items():
        if item['prior_full_sha256']!=models[name]['sha256']:raise ValueError('historical model mismatch')
    return {'passed':True,'new_GPU_warmup':False,'historical_warmup':read(e/'warmup_gate.json'),
            'scope':'historical same-geometry backend viability, not current timing or current pair equality'}
if __name__=='__main__':print(json.dumps(validate(Path(__file__).resolve().parents[1]),indent=2))
