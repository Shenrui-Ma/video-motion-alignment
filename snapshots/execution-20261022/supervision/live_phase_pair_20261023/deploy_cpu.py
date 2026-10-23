"""Stage frozen observer and CPU-check custom node schema. No service or GPU."""
from pathlib import Path
import json,hashlib,subprocess,shlex
D=Path(__file__).parent;E=D.parents[1];P=E/'innovation/signed_phase_calibration_20261023/replay_live_pair';R='/data/research-user/h3_inference_20261023/live_phase_pair_20261023';H='H3_HOST_RTX4090';sha=lambda b:hashlib.sha256(b).hexdigest()
rb=(P/'READY.json').read_bytes();assert sha(rb)=='7e562c75a3e89a1c7cda0274fd421f4ddff7d478b2cf40c0ffe3f2e22096ed0a';ready=json.loads(rb)
for n,h in ready['files_sha256'].items():assert sha((P/n).read_bytes())==h,n
files={'custom_nodes/H3LivePhase/'+n:(P/n).read_bytes() for n in ready['runtime_files']}
for m in ['native','global_weak']:
 files['graphs/'+m+'_graph.json']=(P/'plans'/(m+'_graph.json')).read_bytes();files['contracts/'+m+'_contract.json']=(P/'plans'/(m+'_contract.json')).read_bytes()
for n in ['trajectory_gate.py','live_pair_supervisor.py']:files['scripts/'+n]=(D/n).read_bytes()
files['SCIENCE_READY.json']=rb
files['jobs.json']=(D/'jobs.json').read_bytes()
code=r'''
from pathlib import Path
import json,hashlib,sys
r=Path(ROOT);files=json.load(sys.stdin);assert not (r/'STARTED.json').exists() and not (r/'jobs').exists()
for k,v in files.items():
 p=r/k;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(bytes.fromhex(v));assert hashlib.sha256(p.read_bytes()).hexdigest()==hashlib.sha256(bytes.fromhex(v)).hexdigest()
print(json.dumps({'staged':len(files)}))
'''.replace('ROOT',repr(R))
r=subprocess.run(['ssh',H,'python3 -c '+shlex.quote(code)],input=json.dumps({k:v.hex() for k,v in files.items()}),text=True,capture_output=True,timeout=60);r.check_returncode()
code=r'''
from pathlib import Path
import sys,importlib,json,torch
r=Path(ROOT);sys.path.insert(0,str(r/'custom_nodes'));sys.path.insert(0,str(r/'scripts'));importlib.import_module('int8_row_chunking');importlib.import_module('backend_dispatch_audit');maps={}
for name in ['H3Study','H3TrustedConditionCache','H3LivePhase']:maps.update(importlib.import_module(name).NODE_CLASS_MAPPINGS)
checked=[]
for method in ['native','global_weak']:
 g=json.loads((r/'graphs'/(method+'_graph.json')).read_text())
 for k,n in g.items():
  if n['class_type'] in maps:
   required=maps[n['class_type']].INPUT_TYPES()['required'];assert set(n['inputs'])==set(required),(method,k,set(n['inputs'])^set(required));checked.append([method,k,n['class_type']])
 importlib.import_module('H3LivePhase.nodes').validate_contract(json.loads((r/'contracts'/(method+'_contract.json')).read_text()))
assert not torch.cuda.is_initialized();print(json.dumps({'passed':True,'cuda_initialized':False,'checked':checked}))
'''.replace('ROOT',repr(R))
r=subprocess.run(['ssh',H,'CUDA_VISIBLE_DEVICES= PYTHONPATH=/data/research-user/h3_inference_20261023/runtime_deps /data/research-user/h3_inference_20261023/env/bin/python -'],input=code,text=True,capture_output=True,timeout=60);assert r.returncode==0,r.stderr
result=json.loads(r.stdout);(D/'DEPLOY_CPU_READY.json').write_text(json.dumps(result,indent=2)+'\n')
assets=json.loads((D/'STAGED_PREPARED.json').read_text())['files'];assets.update({k:sha(v) for k,v in files.items()})
(D/'DEPLOY_ASSETS.json').write_text(json.dumps(assets,indent=2)+'\n');print(result)
