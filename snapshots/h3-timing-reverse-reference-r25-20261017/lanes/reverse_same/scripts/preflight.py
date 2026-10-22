"""Static contract only; no GPU/service launch authority."""
import argparse
import json
from pathlib import Path
from r25_contract import ROOT, read, sha, registry, validate_job

def check(root=ROOT,live=False):
    root=Path(root);s=read(root/'configs/scientific_contract.json')
    if (s['seed']!=2026101311 or s['arms']!=['reverse_block','reverse_same'] or
        s['event_window_inclusive']!=[50,65] or s['step_interval_half_open']!=[6,15] or
        s['block_interval_half_open']!=[0,50] or s['NFE_per_job']!=20):raise ValueError('frozen scientific contract changed')
    jobs,order=registry(root)
    for run in order:validate_job(run,root)
    for rel,digest in read(root/'configs/reused_helpers.json').items():
        if sha(root/rel)!=digest:raise ValueError('byte-reused helper changed: '+rel)
    for rel,row in read(root/'configs/parent_evidence.json').items():
        if sha(root/rel)!=row['sha256']:raise ValueError('parent evidence changed')
    g=read(root/'configs/parent_graph.json');hist=read(root/'parent_evidence/full_6to14_history.json')
    if hist['status']!={'status_str':'success','completed':True,'messages':hist['status']['messages']} or hist['prompt'][2]!=g:
        raise ValueError('actual successful parent graph mismatch')
    a=read(root/'configs/admission.json')
    if live and not a.get('ready_for_launch'):raise ValueError('root live resource/R24 handoff required')
    seal=root/'deploy_manifest.json'
    if seal.exists():
        for rel,row in read(seal)['files'].items():
            if sha(root/rel)!=row['sha256']:raise ValueError('sealed file changed: '+rel)
    return {'passed':True,'jobs':order,'planned_NFE':20,'scope':'static only; actual005/native/backend/operator checks still required'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--live',action='store_true');a=p.parse_args();print(json.dumps(check(a.root,a.live),indent=2))
