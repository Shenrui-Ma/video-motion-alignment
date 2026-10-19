"""Seal the reviewed administrative recovery; inputs retain their independent hashes."""
import argparse,hashlib,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);a=p.parse_args()
 from retry_inheritance import check
 from preflight import check as preflight
 inheritance=check(ROOT);preflight(ROOT,metadata_only=True)
 paths=[q for d in ('extensions','scripts','tests','configs','design') for q in (ROOT/d).rglob('*') if q.is_file() and '__pycache__' not in q.parts and q.suffix!='.pyc' and q.name not in ('admission.json','runtime_provenance.json','queue.json')]
 paths += [ROOT/n for n in ('PROTOCOL.json','FREEZE.json','README.txt','COMPARABILITY.txt')]
 # Preserve the old deploy manifest's immutable audit evidence without relabelling it.
 old=json.loads((ROOT/'configs/recovery/previous_deploy_manifest.json').read_text())
 paths += [ROOT/n for n in old['files'] if n.startswith('audit/')]
 paths=sorted(set(paths));value={'schema':'r50-administrative-recovery-retry2-v1','files':{str(q.relative_to(ROOT)):{'bytes':q.stat().st_size,'sha256':sha(q)} for q in paths},'scientific_protocol_sha256':sha(ROOT/'configs/protocol.json'),'previous_manifest_sha256':inheritance['base_manifest_sha256'],'execution_plan_sha256':sha(ROOT/'configs/recovery/execution_plan.json'),'GPU_launch_authorized_by_root_only':True,'mutable_administrative_files':['configs/admission.json','configs/runtime_provenance.json','configs/queue.json'],'new_runs':inheritance['new_runs'],'external_completed':['chest'],'planned_denominator':5}
 with a.manifest.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
 with tarfile.open(a.bundle,'x:gz') as tar:
  for q in paths:tar.add(q,arcname=str(q.relative_to(ROOT)))
  tar.add(a.manifest,arcname='deploy_manifest.json')
  for n in ('configs/admission.json','configs/queue.json'):tar.add(ROOT/n,arcname=n)
 print(json.dumps({'files':len(paths),'manifest_sha256':sha(a.manifest),'bundle_sha256':sha(a.bundle)}))
if __name__=='__main__':main()
