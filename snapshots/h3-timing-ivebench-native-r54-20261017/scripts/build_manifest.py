"""Seal all scientific/runtime bytes. Inputs are hash-bound but prepared from five fixed original IVEBench tasks."""
import argparse,json,tarfile
from pathlib import Path
from r54_contract import sha
from preflight import check

def build(root):
 root=Path(root);check(root);dest=root/'deploy_manifest.json'
 if json.loads((root/'configs/runtime.json').read_text())['status']!='READY':raise ValueError('actual host profile must be verified before seal')
 if dest.exists():raise FileExistsError('existing seal must be retained')
 excluded={'configs/admission.json','configs/queue.json','configs/runtime_provenance.json'};files={}
 for folder in ('scripts','extensions','tests','configs','inputs','design'):
  for p in sorted((root/folder).rglob('*')):
   rel=p.relative_to(root).as_posix()
   if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc' or rel in excluded:continue
   files[rel]={'bytes':p.stat().st_size,'sha256':sha(p)}
 files['INPUTS_READY.json']={'bytes':(root/'INPUTS_READY.json').stat().st_size,'sha256':sha(root/'INPUTS_READY.json')}
 for rel in ('README.txt','COMPARABILITY.txt','audit/CPU_EVIDENCE.json','audit/HOST41_MODEL_CORE_CHECK.json','audit/root_host41_probe.json'):
  files[rel]={'bytes':(root/rel).stat().st_size,'sha256':sha(root/rel)}
 dest.write_text(json.dumps({'files':files,'mutable_administration':sorted(excluded),'administration_rule':'only exact peer PIDs/ready flag, queue.finalize boolean and actual runtime provenance; fixed5jobs immutable','inputs_in_tar':False,'input_source':'five prepared IVEBench source videos/provenance plus original instructions and source files; exact inputs SHA required before launch'},indent=2)+'\n')
 tar=root/'audit/runtime_bundle_v1.tar.gz'
 with tarfile.open(tar,'x:gz') as f:
  for rel in [r for r in files if not r.startswith('inputs/')]+['deploy_manifest.json','configs/admission.json','configs/queue.json']:f.add(root/rel,arcname=rel)
 return {'manifest':str(dest),'manifest_sha256':sha(dest),'bundle':str(tar),'bundle_sha256':sha(tar),'immutable_count':len(files),'input_files':[r for r in files if r.startswith('inputs/')],'tar_source_count':len(files)-len([r for r in files if r.startswith('inputs/')])+3}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();print(json.dumps(build(a.root),indent=2))
