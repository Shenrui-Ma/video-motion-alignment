"""Seal an independent same-seed R50 retry with reviewed resource lifecycle changes."""
import argparse,hashlib,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);a=p.parse_args()
 from retry_inheritance import check
 from preflight import check as preflight
 inheritance=check(ROOT);preflight(ROOT,metadata_only=True)
 paths=[ROOT/n for n in ('PROTOCOL.json','FREEZE.json','README.txt','COMPARABILITY.txt','audit/revisions/producer_v1/deploy_manifest.json','audit/revisions/producer_v1/sealed_producer.tar.gz','audit/revisions/producer_v1/PRESERVATION.json','audit/ENGINEERING_REVISION_v2_CPU_CHECK.json','audit/EXACT_COMPONENT_REUSE.json','audit/RETRY_V4_METADATA_PREFLIGHT.json','audit/RETRY_V4_TESTS.log','audit/RETRY_V4_CPU_CHECK.json')]
 for folder in ('extensions','scripts','tests','configs','design'):
  paths.extend(q for q in (ROOT/folder).rglob('*') if q.is_file() and '__pycache__' not in q.parts and q.suffix!='.pyc' and q.name not in ('admission.json','runtime_provenance.json','queue.json'))
 paths=sorted(set(paths));value={'schema':'r50-independent-resource-retry-deploy-v1','files':{str(q.relative_to(ROOT)):{'bytes':q.stat().st_size,'sha256':sha(q)} for q in paths},'scientific_protocol_sha256':sha(ROOT/'configs/protocol.json'),'engineering_revision_sha256':sha(ROOT/'configs/engineering_revision_v2.json'),'retry_inheritance_sha256':sha(ROOT/'configs/retry/inheritance.json'),'base_deploy_manifest_sha256':inheritance['base_manifest_sha256'],'GPU_launch_authorized_by_root_only':True,'mutable_administrative_files':['configs/admission.json','configs/runtime_provenance.json','configs/queue.json'],'input_files_separate_bundle':True,'GPU_resource_and_decoder_gates':'ROOT_PENDING'}
 with a.manifest.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
 with tarfile.open(a.bundle,'x:gz') as tar:
  for q in paths:tar.add(q,arcname=str(q.relative_to(ROOT)))
  tar.add(a.manifest,arcname='deploy_manifest.json')
  for n in ('configs/admission.json','configs/queue.json'):tar.add(ROOT/n,arcname=n)
 print(json.dumps({'files':len(paths),'manifest_sha256':sha(a.manifest),'bundle_sha256':sha(a.bundle)}))
if __name__=='__main__':main()
