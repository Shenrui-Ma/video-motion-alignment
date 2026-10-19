"""Seal immutable lane files. Administrative queue/admission remain separately logged."""
import argparse,json,tarfile
from pathlib import Path
from r26_contract import sha
from preflight import check

def build(root):
 root=Path(root);check(root)
 dest=root/'deploy_manifest.json'
 if dest.exists():raise FileExistsError('existing seal must be preserved')
 files={}
 for folder in ('scripts','extensions','tests','configs','inputs'):
  for p in sorted((root/folder).rglob('*')):
   rel=p.relative_to(root).as_posix()
   if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc' or rel in ('configs/admission.json','configs/queue.json','configs/runtime_provenance.json'):continue
   files[rel]={'bytes':p.stat().st_size,'sha256':sha(p)}
 dest.write_text(json.dumps({'files':files,'mutable_administration':['configs/admission.json','configs/queue.json'],'administration_rule':'only live exact PID permits and finalize; three initial source jobs and graph registries immutable; new cases require separate reviewed revision','scope':'source assets included in seal; no output/results'},indent=2)+'\n')
 tar=root.parent/(root.name+'_runtime_bundle_v2.tar.gz')
 if tar.exists():raise FileExistsError('bundle exists')
 with tarfile.open(tar,'w:gz') as f:
  for rel in list(files)+['deploy_manifest.json','configs/admission.json','configs/queue.json']:f.add(root/rel,arcname=rel)
 return {'manifest':str(dest),'manifest_sha256':sha(dest),'bundle':str(tar),'bundle_sha256':sha(tar),'files':len(files)}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();print(json.dumps(build(a.root),indent=2))
