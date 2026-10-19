"""Seal final five-case producer after actual parent binding; root owns GPU gates."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args()
    from observer_import import t
    from parent_binding import check
    closure=t.require_parent_closure(ROOT)
    t.require(closure.get('final_archive_ready') is True,'actual five parent archive closure required')
    check(ROOT,remote=False);t.bindings()
    paths=[ROOT/name for name in ('PROTOCOL.json','FREEZE.json','README.txt','COMPARABILITY.txt',
           'audit/revisions/producer_v1/deploy_manifest.json','audit/revisions/producer_v1/sealed_producer.tar.gz',
           'audit/revisions/producer_v1/PRESERVATION.json','audit/ENGINEERING_REVISION_v2_CPU_CHECK.json')]
    for folder in ('extensions','scripts','tests','configs','design'):
        paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts
                     and p.suffix!='.pyc' and p.name not in ('admission.json','runtime_provenance.json','queue.json'))
    files={str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(set(paths))}
    manifest={'schema':'r50-immutable-five-case-deploy-v2-split-decoder','files':files,
              'scientific_protocol_sha256':sha(ROOT/'configs/protocol.json'),
              'engineering_revision_sha256':sha(ROOT/'configs/engineering_revision_v2.json'),
              'previous_deploy_manifest_sha256':sha(ROOT/'audit/revisions/producer_v1/deploy_manifest.json'),
              'GPU_launch_authorized_by_root_only':True,
              'mutable_administrative_files':['configs/admission.json','configs/runtime_provenance.json','configs/queue.json'],
              'input_files_separate_bundle':True,
              'component_checkpoint_v2_sha256':sha(ROOT/'audit/COMPONENT_CHECKPOINT_v2.json')}
    with args.manifest.open('x') as out:json.dump(manifest,out,indent=2);out.write('\n')
    with tarfile.open(args.bundle,'x:gz') as tar:
        for path in sorted(set(paths)):tar.add(path,arcname=str(path.relative_to(ROOT)))
        tar.add(args.manifest,arcname='deploy_manifest.json')
        for name in ('configs/admission.json','configs/queue.json'):tar.add(ROOT/name,arcname=name)
    print(json.dumps({'files':len(files),'manifest_sha256':sha(args.manifest),'bundle_sha256':sha(args.bundle)}))

if __name__=='__main__':main()
