"""Bind actual historical fixed output; ignore only regenerated gate creation time."""
import copy,hashlib,json
from pathlib import Path
from r97_contract import ROOT,read,sha,require

def canonical_parent_gate(value):
 return hashlib.sha256(json.dumps({k:v for k,v in value.items() if k!='created_unix'},sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def compare_parent_gate(current,frozen):
 return current.get('passed') is True and frozen.get('passed') is True and canonical_parent_gate(current)==canonical_parent_gate(frozen)
def comparable_conditions(current,previous):
 # Rename only known run/source-manifest provenance. Every scientific field remains exact.
 a=copy.deepcopy(current);a['run_id']=previous['run_id']
 for key in ('source_run_id','source_manifest','source_manifest_sha256'):
  a['pair_snapshot'][key]=previous['pair_snapshot'][key]
 return a==previous

def verify_parent(root=ROOT,include_snapshots=True):
 root=Path(root);b=read(root/'configs/parent_bindings.json');prior=Path(b['parent_root']);frozen=read(root/'design/R89_ACTUAL/PAIR_RUNTIME_GATE.json')
 gatepath=prior/b['parent_gate_relative'];gate=read(gatepath)
 require(compare_parent_gate(gate,frozen),'parent gate changed beyond top-level created_unix')
 files=[]
 for rel,digest in b['parent_records'].items():
  actual={'forced_graph.json':'configs/graphs/'+b['parent_run']+'.json','native_graph.json':'configs/graphs/'+b['parent_native_run']+'.json'}.get(rel,rel)
  path=prior/actual;require(path.is_file() and not path.is_symlink() and sha(path)==digest,'actual parent record changed: '+actual)
  files.append({'file':str(path),'sha256':digest})
 require(sha(prior/'audit/router'/(b['parent_run']+'.json'))==b['parent_router_sha256'],'actual parent router changed')
 require(sha(prior/b['noise_cache_relative'])==b['noise_cache_sha256'],'actual parent noise changed')
 if include_snapshots:
  for record in b['parent_snapshots_prefix']:
   path=Path(record['file']);require(path.resolve().is_relative_to(prior.resolve()) and path.is_file() and not path.is_symlink() and path.stat().st_size==record['bytes'] and sha(path)==record['sha256'],'actual parent prediction snapshot changed')
 require(len(b['parent_snapshots_prefix'])==15,'parent prefix must contain15 actual predictions')
 return {'passed':True,'files':files,'frozen_gate_raw_sha256':b['parent_gate_sha256'],'current_gate_raw_sha256':sha(gatepath),'gate_canonical_sha256':canonical_parent_gate(gate),'ignored_gate_field':'top-level created_unix only','prefix_file_hashes_verified':15 if include_snapshots else 0}
