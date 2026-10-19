"""No GPU work: immutable checks; root supplies actual resource approval."""
import argparse,json
from pathlib import Path
from r46_contract import ROOT,read,sha,require,registry,validate_job,identity_schema


def check(root=ROOT,live=False):
    root=Path(root);p=read(root/'configs/SCIENCE_PROTOCOL.json');rt=read(root/'configs/runtime.json')
    require(rt=={'remote_root':'/data5/researcher/h3_runs/timing_attention_observer_r46_20261017',
                'gpu_uuid':'GPU-REDACTED','port':8508},'resource location changed')
    require(p['total_DiT_NFE']==2 and p['per_state_DiT_NFE']==1 and
            all(p[k]==0 for k in ['Euler_updates','ordinary_callbacks','VAE_calls','Qwen_calls']), 'two terminal Native states only')
    require(p['source_binding_sha256']==sha(root/'configs/sources.json') and p['index']==4 and
            p['block']==25 and p['heads']==[0,14,28,42] and p['time_bins']==42, 'frozen probe changed')
    _,order=registry(root)
    for name in order:validate_job(name,root)
    manifest=root/'deploy_manifest.json'
    if manifest.exists():
        for rel,row in read(manifest)['files'].items():
            require((root/rel).stat().st_size==row['bytes'] and sha(root/rel)==row['sha256'],'sealed file changed '+rel)
    if live:
        require(str(root)==rt['remote_root'],'formal root required')
        a=read(root/'configs/admission.json'); require(a.get('ready_for_launch') is True,'root admission pending')
        for row in a['permitted_compute_processes']:identity_schema(row['identity'],external=True)
        resource=read(root/'audit/root_resource_approval.json')
        require(resource.get('approved') is True and resource.get('protocol_sha256')==sha(root/'configs/SCIENCE_PROTOCOL.json') and
                resource.get('gpu_uuid')==rt['gpu_uuid'],'root resource certificate missing or wrong scope')
        # Recompute actual archived PT SHA before any model load. No model invocation.
        for label,s in read(root/'configs/sources.json').items():
            parent=Path(s['source_root'])
            for rel,row in s['files'].items():
                q=parent/rel
                require(q.resolve().is_relative_to(parent.resolve()) and not q.is_symlink() and
                        q.stat().st_size==row['bytes'] and sha(q)==row['sha256'], 'actual source tensor changed '+label+':'+rel)
    return {'passed':True,'jobs':order,'DiT_NFE':2,'Euler_updates':0,'VAE_Qwen_calls':0,'actual_GPU_endpoint_pending':True}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--live',action='store_true');a=p.parse_args();print(json.dumps(check(a.root,a.live),indent=2))
