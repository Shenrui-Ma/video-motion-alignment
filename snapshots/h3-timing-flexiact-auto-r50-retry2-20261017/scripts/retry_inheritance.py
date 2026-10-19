"""Bind a fresh administrative recovery to the unchanged failed producer."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def require(ok,message):
 if not ok:raise ValueError(message)
def specification(root=ROOT):
 root=Path(root);spec=read(root/'configs/recovery/inheritance.json');base=Path(spec['base_local_root'])
 if not base.exists():base=Path(spec['base_remote_root'])
 manifest=read(root/'configs/recovery/previous_deploy_manifest.json')
 require(sha(base/'deploy_manifest.json')==sha(root/'configs/recovery/previous_deploy_manifest.json')==spec['base_deploy_manifest_sha256'],'previous producer seal differs')
 return spec,base,manifest
def inherited_file(root,rel,expected):
 spec,base,manifest=specification(root)
 # The older engineering certificate may bind the original pre-relocation graph.
 original=read(base/'configs/retry/inheritance.json');original_root=Path(original['base_local_root'])
 if not original_root.exists():original_root=Path(original['base_remote_root'])
 require(sha(original_root/rel)==expected,'original scientific file differs: '+rel)
 a=(Path(root)/rel).read_bytes();b=(original_root/rel).read_bytes()
 if rel.startswith('configs/graphs/'):
  a=a.replace(spec['retry_remote_root'].encode(),original['base_remote_root'].encode())
 require(a==b,'scientific bytes changed: '+rel)
def check(root=ROOT,inputs=True):
 root=Path(root);spec,base,manifest=specification(root);counts={'exact':0,'relocated':0,'administrative':0}
 for rel,row in manifest['files'].items():
  require(sha(base/rel)==row['sha256'],'sealed previous producer differs: '+rel)
  if rel=='configs/observer_bindings.json':
   old_bind,current=read(base/rel),read(root/rel)
   require({k:v for k,v in old_bind.items() if k!='local_files'}=={k:v for k,v in current.items() if k!='local_files'},'external observer bindings changed')
   require(set(old_bind['local_files']).issubset(current['local_files']),'old local binding omitted')
   for name,digest in current['local_files'].items():require(sha(root/name)==digest,'new local binding changed: '+name)
   counts['administrative']+=1
  elif rel in spec['administrative_changes']:
   require(sha(root/rel)==spec['administrative_changes'][rel]['after_sha256'],'reviewed administrative file changed: '+rel);counts['administrative']+=1
  elif rel in spec['relocated_files']:
   require((root/rel).read_text().replace(spec['retry_remote_root'],spec['base_remote_root'])==(base/rel).read_text(),'relocation exceeds paths: '+rel);counts['relocated']+=1
  else:
   require(sha(root/rel)==row['sha256'],'unapproved inherited file differs: '+rel);counts['exact']+=1
 require(sha(root/'configs/protocol.json')==sha(base/'configs/protocol.json')==spec['protocol_sha256'],'protocol must be byte exact')
 if inputs:
  for name,digest in read(root/'configs/input_hashes.json').items():require(sha(root/'inputs'/name)==digest,'input changed: '+name)
 from recovery_contract import plan
 p=plan(root)
 return {'status':'pass','base_manifest_sha256':spec['base_deploy_manifest_sha256'],'protocol_byte_exact':True,'counts':counts,'new_runs':p['new_runs'],'external_completed':['chest'],'planned_denominator':5}
if __name__=='__main__':print(json.dumps(check(),indent=2))
