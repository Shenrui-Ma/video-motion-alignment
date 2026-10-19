from pathlib import Path
import hashlib,json,time
R=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not (R/'deploy_manifest.json').exists(),'sealed already'
files={}
for directory in ['scripts','extensions','tests','source_snapshot','design','configs','analysis/postrun']:
 for p in (R/directory).rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
  rel=str(p.relative_to(R))
  if rel in ['configs/admission.json','configs/queue.json']:continue
  files[rel]={'sha256':sha(p),'bytes':p.stat().st_size}
for rel in ['PREPARED_INPUTS_MANIFEST.json','audit/root_run_batch.py','audit/remote_cpu_validate.py','audit/INHERITED_BYTE_BINDINGS.json','audit/SCIENTIFIC_DIFF.json']:
 p=R/rel;files[rel]={'sha256':sha(p),'bytes':p.stat().st_size}
p=R/'deploy_manifest.json';p.write_text(json.dumps({'schema':'r100-producer-seal-v1','files':dict(sorted(files.items())),'mutable_root_owned':['configs/admission.json','audit/ROOT_SCREEN_APPROVAL.json','audit/decisions/*.json','audit/FIRST_GUIDED_REVIEW.json'],'created_unix':time.time()},indent=2)+'\n');print(len(files),sha(p))
