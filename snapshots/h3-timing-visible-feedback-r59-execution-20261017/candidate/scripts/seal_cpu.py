"""Seal this CPU candidate only; it never creates a deployment approval."""
import ast,hashlib,json,tarfile
from pathlib import Path
from preflight import ROOT,check

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 status=check()
 for folder in ('scripts','extensions','tests'):
  for p in (ROOT/folder).rglob('*.py'):ast.parse(p.read_text(),filename=str(p))
 dest=ROOT/'PREPARATION_MANIFEST.json'
 if dest.exists():raise FileExistsError('preserve prior candidate seal before a revision')
 files={}
 for p in sorted(ROOT.rglob('*')):
  if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc' or p.name in ('PREPARATION_MANIFEST.json','cpu_candidate_bundle.tar.gz'):continue
  rel=p.relative_to(ROOT).as_posix();files[rel]={'bytes':p.stat().st_size,'sha256':sha(p)}
 record={'schema':'r59-cpu-only-candidate-seal-v1','status':'CPU_PREPARED_GPU_PARENT_RUNTIME_PENDING','GPU_launch_authorized':False,'files':files,'preflight':status,'source_count':5,'arms':4,'parent_R57_actual_binding':'PENDING','scope':'CPU policy, scanner and transaction candidate. Actual Comfy/CUDA, generated quality, deployment service and consumption gates remain pending.'}
 dest.write_text(json.dumps(record,indent=2)+'\n')
 bundle=ROOT/'audit/cpu_candidate_bundle.tar.gz'
 with tarfile.open(bundle,'x:gz') as t:
  for rel in [*files,dest.name]:t.add(ROOT/rel,arcname=rel)
 result={'manifest_sha256':sha(dest),'files':len(files),'bundle_sha256':sha(bundle),'bundle_bytes':bundle.stat().st_size}
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
