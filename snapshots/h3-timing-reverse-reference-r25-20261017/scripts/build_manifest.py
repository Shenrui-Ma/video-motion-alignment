"""Seal two-arm lane; administrative admission/finalize are explicitly mutable."""
import argparse,json,tarfile
from pathlib import Path
from r25_contract import sha
from preflight import check

def build(root):
    root=Path(root);check(root)
    manifest=root/'deploy_manifest.json';bundle=root.parent/(root.name+'_runtime_bundle.tar.gz')
    if manifest.exists() or bundle.exists():raise FileExistsError('never overwrite an existing seal')
    files={'IMPLEMENTATION.txt':{'bytes':(root/'IMPLEMENTATION.txt').stat().st_size,'sha256':sha(root/'IMPLEMENTATION.txt')}}
    mutable={'configs/admission.json','configs/queue.json','configs/runtime_provenance.json'}
    for folder in ('scripts','extensions','tests','configs','inputs','parent_evidence'):
        for p in sorted((root/folder).rglob('*')):
            rel=p.relative_to(root).as_posix()
            if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc' or rel in mutable:continue
            files[rel]={'bytes':p.stat().st_size,'sha256':sha(p)}
    manifest.write_text(json.dumps({'files':files,'mutable_administration':['configs/admission.json','configs/queue.json'],
        'administration_rule':'exact live permitted PID identities/readiness and queue.finalize only; single frozen job cannot change',
        'scope':'seen development source, two fixed diagnostic arms; no success/novelty claim'},indent=2)+'\n')
    with tarfile.open(bundle,'w:gz') as tar:
        for rel in list(files)+['deploy_manifest.json','configs/admission.json','configs/queue.json']:tar.add(root/rel,arcname=rel)
    return {'manifest':str(manifest),'manifest_sha256':sha(manifest),'bundle':str(bundle),'bundle_sha256':sha(bundle),'files':len(files)}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();print(json.dumps(build(a.root),indent=2))
