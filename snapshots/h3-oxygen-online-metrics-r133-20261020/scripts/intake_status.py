"""CPU history entry. Actual auto intake stays disabled until its contract exists."""
from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def walk(v):
 if isinstance(v,dict):
  if set(['file','sha256']).issubset(v):
   p=Path(v['file']);assert p.exists() and sha(p)==v['sha256'],'binding changed '+str(p)
  for x in v.values():walk(x)
 elif isinstance(v,list):
  for x in v:walk(x)
m=json.loads((R/'configs/HISTORICAL_INPUTS.json').read_text());walk(m)
assert m['evaluation_indices']==list(range(98))
print(json.dumps({'historical_bindings_valid':True,'actual_auto_intake_enabled':False,'reason':'Await decoder-only precheck and sealed actual auto contract from producer; no output implied.','required_roles':['source','native','fixed','auto'],'GPU_started':False}))
