"""Prepare a CPU seal; a deployment seal additionally requires fresh root admission."""
import argparse,json,tarfile
from pathlib import Path
from r57_contract import ROOT,read,sha
from preflight import check

def build(root=ROOT,formal=False):
 root=Path(root);result=check(root,live=formal)
 dest=root/('deploy_manifest.json' if formal else 'PREPARATION_MANIFEST.json')
 if dest.exists():raise FileExistsError('preserve the prior seal before creating a new revision')
 excluded={'configs/admission.json','configs/queue.json','configs/runtime_provenance.json'};files={}
 for folder in ('scripts','extensions','tests','configs','design'):
  for p in sorted((root/folder).rglob('*')):
   rel=p.relative_to(root).as_posix()
   if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc' or rel in excluded:continue
   files[rel]={'bytes':p.stat().st_size,'sha256':sha(p)}
 for rel in ['README.txt','COMPARABILITY.txt','audit/CPU_EVIDENCE.json','audit/GRAPH_FIELD_DIFF.json','audit/INITIAL_RUNTIME_INHERITANCE.json','audit/RESOURCE_FEASIBILITY.json','audit/PROMPT_TOKEN_COUNTS.json','audit/CPU_TESTS.log','audit/INPUT_AUDIO_VIDEO_PROBE.json','audit/tokenize_prompts_cpu.py','audit/tokenize_prompts_cpu.stderr.log','audit/PRODUCER_DIFF.json']:
  p=root/rel;files[rel]={'bytes':p.stat().st_size,'sha256':sha(p)}
 record={'schema':'r57-native-P1-producer-v1','status':'ROOT_APPROVED_DEPLOYMENT' if formal else 'CPU_PREPARATION_GPU_PENDING','files':files,'external_inputs':read(root/'configs/input_bindings.json'),'mutable_administration':sorted(excluded),'scope':'Fixed five Native P1 cases; P0 actual archive preserved. CPU seal establishes bytes and controls, not GPU execution/capacity/quality.','preflight':result}
 dest.write_text(json.dumps(record,indent=2)+'\n')
 bundle=root/'audit'/('runtime_bundle_v1.tar.gz' if formal else 'cpu_preparation_bundle_v1.tar.gz')
 with tarfile.open(bundle,'x:gz') as t:
  for rel in list(files)+[dest.name,'configs/admission.json','configs/queue.json']:t.add(root/rel,arcname=rel)
 return {'manifest':str(dest),'manifest_sha256':sha(dest),'bundle':str(bundle),'bundle_sha256':sha(bundle),'files':len(files),'GPU_launch_authorized':formal}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--formal',action='store_true');a=p.parse_args();print(json.dumps(build(a.root,a.formal),indent=2))
