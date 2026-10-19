"""Seal only executable/config evidence; no outputs, weights or tensor copies."""
import argparse,hashlib,json,tarfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--bundle',required=True);a=p.parse_args()
paths=[]
for sub in ('extensions','scripts','tests','configs'):
 for f in (R/sub).rglob('*'):
  if f.is_file() and '__pycache__' not in str(f) and f.name not in ('admission.json','runtime_provenance.json'):paths.append(f)
files={str(f.relative_to(R)):{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(paths)}
manifest={'schema':'r21-immutable-deploy-v1','files':files,'scientific_protocol_sha256':'0968e50ce2f2ea0a6f6a53ee9147216e69fe3e69d809a2ca2a9e1a328539481b','resource_revision':'configs/resource_revision_v2.json','mutable_administrative_files':['configs/admission.json','configs/runtime_provenance.json'],'GPU_launch_authorized_by_root_only':True}
out=Path(a.manifest);out.parent.mkdir(parents=True,exist_ok=True)
with out.open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
with tarfile.open(a.bundle,'x:gz') as archive:
 for f in sorted(paths):archive.add(f,arcname=str(f.relative_to(R)))
 archive.add(out,arcname='deploy_manifest_v1.json')
print(json.dumps({'files':len(files),'manifest_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'bundle_sha256':hashlib.sha256(Path(a.bundle).read_bytes()).hexdigest()}))
