"""Seal only executable/config evidence; no outputs, weights or tensor copies."""
import argparse,hashlib,json,tarfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--bundle',required=True);a=p.parse_args()
paths=[]
for sub in ('extensions','scripts','tests','configs'):
 for f in (R/sub).rglob('*'):
  if f.is_file() and '__pycache__' not in str(f) and f.name not in ('admission.json','runtime_provenance.json','queue.json'):paths.append(f)
files={str(f.relative_to(R)):{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(paths)}
manifest={'schema':'r28-immutable-deploy-v1','files':files,'scientific_protocol_sha256':hashlib.sha256((R/'configs/protocol.json').read_bytes()).hexdigest(),'resource_revision':'frozen protocol resources','mutable_administrative_files':['configs/admission.json','configs/runtime_provenance.json','configs/queue.json'],'GPU_launch_authorized_by_root_only':True}
out=Path(a.manifest);out.parent.mkdir(parents=True,exist_ok=True)
with out.open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
with tarfile.open(a.bundle,'x:gz') as archive:
 for f in sorted(paths):archive.add(f,arcname=str(f.relative_to(R)))
 archive.add(out,arcname='deploy_manifest.json')
 archive.add(R/'configs/admission.json',arcname='configs/admission.json')
 archive.add(R/'configs/queue.json',arcname='configs/queue.json')
print(json.dumps({'files':len(files),'manifest_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'bundle_sha256':hashlib.sha256(Path(a.bundle).read_bytes()).hexdigest()}))
