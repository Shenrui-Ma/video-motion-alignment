from pathlib import Path
import json,hashlib,difflib
n=Path(__file__).resolve().parents[2];s=json.loads((n/'configs/recovery/inheritance.json').read_text());o=Path(s['base_local_root']);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not (n/'deploy_manifest.json').exists(),'producer already sealed'
patches=[]
for rel,row in s['administrative_changes'].items():
 row['after_sha256']=sha(n/rel)
 patches.extend(difflib.unified_diff((o/rel).read_text().splitlines(True),(n/rel).read_text().splitlines(True),fromfile='previous/'+rel,tofile='retry2/'+rel))
(n/'configs/recovery/inheritance.json').write_text(json.dumps(s,indent=2)+'\n');(n/'audit/recovery/ADMINISTRATIVE.patch').write_text(''.join(patches))
b=json.loads((n/'configs/observer_bindings.json').read_text())
for rel in b['local_files']:b['local_files'][rel]=sha(n/rel)
(n/'configs/observer_bindings.json').write_text(json.dumps(b,indent=2)+'\n')
