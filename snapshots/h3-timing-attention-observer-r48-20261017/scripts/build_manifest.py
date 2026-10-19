"""Seal this independent diagnostic; never mutate historical evidence."""
import json,tarfile
from pathlib import Path
from r46_contract import ROOT,sha

def main():
    r=ROOT;paths=[]
    for directory in ['extensions','scripts','tests','configs','evidence']:
        paths.extend(p for p in (r/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'
                     and p.relative_to(r).as_posix() not in {'configs/admission.json','configs/runtime_provenance.json'})
    paths.extend(r/p for p in ['analysis/IMPLEMENTATION.txt','audit/DEPLOYMENT.txt','audit/RESOURCE_TEMPLATE.json','audit/REUSE_CURRENT.json','audit/RUNTIME_REUSE.diff'])
    files={str(p.relative_to(r)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(paths)}
    path=r/'deploy_manifest.json'
    if path.exists():raise FileExistsError('preserve prior seal; explicit version required')
    path.write_text(json.dumps({'schema':'r48-immutable-v1','files':files,'mutable_admin':['configs/admission.json','configs/runtime_provenance.json','audit/root_resource_approval.json'],
        'queue_finalize_change':'not permitted in this two-state diagnostic; use bounded hold or exact-owner service stop'},indent=2)+'\n')
    tar=r/'audit/runtime_bundle_v1.tar.gz'
    with tarfile.open(tar,'w:gz') as archive:
        for rel in files:archive.add(r/rel,arcname=rel)
        archive.add(path,arcname='deploy_manifest.json')
    print(json.dumps({'files':len(files),'manifest_sha256':sha(path),'bundle_sha256':sha(tar)}))
if __name__=='__main__':main()
