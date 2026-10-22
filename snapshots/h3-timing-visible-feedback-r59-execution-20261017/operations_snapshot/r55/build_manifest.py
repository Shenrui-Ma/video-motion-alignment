"""Seal actual R55 producer after root policy choice and completed R54/source90 binding."""
import argparse,hashlib,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def engineering_files(root=ROOT):
 root=Path(root);paths=[]
 for folder in ('audit/engineering_resource_robustness_v3_20261017','audit/engineering_resource_robustness_v4_20261017'):
  directory=root/folder
  if not directory.is_dir():raise ValueError('engineering evidence directory absent: '+folder)
  paths.extend(p for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and 'test_tmp' not in p.parts)
 for rel in ('audit/gpu_dynamic_union_gate.json','audit/known_endpoint_90_gate.json','audit/resource_admission.json'):
  path=root/rel
  if not path.is_file():raise ValueError('actual GPU gate required before final seal: '+rel)
  paths.append(path)
 return paths
def validate_final_profiles(root=ROOT):
 from observer_import import t
 import service
 decoder=t.decoder_memory_profile();main=service.main_memory_profile()
 gate=Path(root)/'audit/known_endpoint_90_gate.json'
 if decoder['evidence_sha256']!=sha(gate):raise ValueError('measured decoder profile must bind actual full90 gate')
 return {'decoder_profile_sha256':decoder['profile_sha256'],'main_profile_sha256':main['profile_sha256']}
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);a=p.parse_args()
 from preflight import check
 check(ROOT,metadata_only=True)
 profiles=validate_final_profiles(ROOT)
 if a.manifest.exists() or a.bundle.exists():raise FileExistsError('seal destination already exists')
 excluded={'configs/admission.json','configs/runtime_provenance.json','configs/queue.json'};files={}
 for folder in ('scripts','extensions','tests','configs','inputs'):
  for path in sorted((ROOT/folder).rglob('*')):
   rel=path.relative_to(ROOT).as_posix()
   if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc' and rel not in excluded:files[rel]={'bytes':path.stat().st_size,'sha256':sha(path)}
 for rel in ('PROTOCOL.json','FREEZE.json','README_PRODUCTION.txt','README_COMPONENTS.txt','audit/CPU_EVIDENCE_v2.json'):
  path=ROOT/rel;files[rel]={'bytes':path.stat().st_size,'sha256':sha(path)}
 for path in engineering_files(ROOT):
  files[path.relative_to(ROOT).as_posix()]={'bytes':path.stat().st_size,'sha256':sha(path)}
 manifest={'schema':'r55-immutable-five-task-deploy-v1','files':files,'scientific_protocol_sha256':sha(ROOT/'configs/protocol.json'),'policy_selection_sha256':sha(ROOT/'configs/POLICY_SELECTION.json'),'measured_memory_profiles':profiles,'GPU_launch_authorized_by_root_only':True,'mutable_administrative_files':sorted(excluded),'input_files_separate_bundle':True}
 with a.manifest.open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
 with tarfile.open(a.bundle,'x:gz') as tar:
  for rel in files:
   if not rel.startswith('inputs/'):tar.add(ROOT/rel,arcname=rel)
  tar.add(a.manifest,arcname='deploy_manifest.json')
  for rel in ('configs/admission.json','configs/queue.json'):tar.add(ROOT/rel,arcname=rel)
 print(json.dumps({'files':len(files),'manifest_sha256':sha(a.manifest),'bundle_sha256':sha(a.bundle)}))
if __name__=='__main__':main()
