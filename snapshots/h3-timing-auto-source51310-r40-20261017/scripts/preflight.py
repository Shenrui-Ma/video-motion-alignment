"""Read-only frozen protocol/core and case graph checks; no GPU imports."""
import argparse,json
from pathlib import Path
from observer_import import t,ROOT
from r40_contract import validate_job

def check(root=ROOT,metadata_only=False):
    root=Path(root);t.bindings();t.admission_document(approved=not metadata_only)
    p=t.read_json(root/'configs/protocol.json');names=[c['run_id'] for c in p['cases']]
    queue=t.read_json(root/'configs/queue.json')
    t.require(set(queue)=={'jobs','finalize'} and queue['jobs']==names and type(queue['finalize']) is bool,'queue changed')
    rows=[validate_job(name,root,inputs=not metadata_only) for name in names]
    from parent_binding import check as check_parent
    parent_binding=check_parent(root,remote=not metadata_only)
    if not metadata_only:
        from prelaunch_gates import check as check_gpu_evidence
        gpu_gates=check_gpu_evidence(root)
        b=t.bindings(external=True)
        for rel,sha in t.read_json(root/'configs/parent_core_hashes.json').items():t.require(t.sha(Path(b['comfy'])/rel)==sha,'actual core differs: '+rel)
        manifest=t.read_json(root/'deploy_manifest.json')
        for rel,row in manifest['files'].items():t.require(t.sha(root/rel)==row['sha256'],'sealed runtime differs: '+rel)
    return {'pass':True,'cases':rows,'expected_NFE_per_case':[20,39],'updates':20,'current_native_observations':20,'parent_binding':parent_binding,'GPU_bridges':'not_checked_metadata_only' if metadata_only else gpu_gates}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default=str(ROOT));p.add_argument('--metadata-only',action='store_true');a=p.parse_args();print(json.dumps(check(a.root,a.metadata_only),indent=2))
