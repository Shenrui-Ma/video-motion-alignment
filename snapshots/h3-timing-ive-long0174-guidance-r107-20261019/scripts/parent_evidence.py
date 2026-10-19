"""Immutable historical parent evidence and strict pre-DiT condition equality."""
import copy,hashlib,json
from pathlib import Path
from r107_contract import ROOT,read,sha,require,SOURCES

def canonical_parent_gate(value):return hashlib.sha256(json.dumps({k:v for k,v in value.items() if k!='created_unix'},sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def compare_parent_gate(current,frozen):return current.get('passed') is True and frozen.get('passed') is True and canonical_parent_gate(current)==canonical_parent_gate(frozen)
def comparable_conditions(current,previous):
 a=copy.deepcopy(current);a['run_id']=previous['run_id']
 for key in ('source_run_id','source_manifest','source_manifest_sha256'):a['pair_snapshot'][key]=previous['pair_snapshot'][key]
 return a==previous

def validate_parent_condition(current,source,root=ROOT):
 root=Path(root);require(source in SOURCES,'unknown parent source');previous=read(root/'design'/source/'PARENT_CONDITIONING.json')
 require(comparable_conditions(current,previous),'current clean conditions differ from actual parent Native before DiT; matched comparison not admitted')
 return {'passed':True,'source_id':source,'parent_condition_sha256':read(root/'configs/parent_bindings.json')[source]['condition_manifest']['sha256'],'current_run':current['run_id'],'stage':'before_DiT','comparison':'all scientific fields exact; only run and source-manifest provenance renamed'}

def verify_parent(root=ROOT,source=None,include_snapshots=True):
 root=Path(root);allb=read(root/'configs/parent_bindings.json');results={}
 for src in ([source] if source else SOURCES):
  b=allb[src];prior=Path(b['producer_remote']);frozen=read(root/'design'/src/'PARENT_ACTUAL_GATE.json');gp=prior/b['original_gate_relative'];gate=read(gp)
  require(compare_parent_gate(gate,frozen),'actual parent gate changed beyond created_unix: '+src)
  files=[]
  for rel,digest in b['parent_record_hashes'].items():
   p=prior/rel;require(p.is_file() and not p.is_symlink() and sha(p)==digest,'actual parent record changed: '+rel);files.append({'file':str(p),'sha256':digest})
  noise=Path(b['noise']['cache_file']);require(sha(noise)==b['noise']['current_file']['sha256'],'actual parent noise changed')
  if include_snapshots:
   for item in b['first_six_predictions']:
    p=Path(item['file']);require(p.resolve().is_relative_to(prior.resolve()) and p.is_file() and not p.is_symlink() and p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],'actual parent x0 prefix changed')
   for item in b['condition_tensors']:
    p=Path(item['file']);require(p.resolve().is_relative_to(prior.resolve()) and p.is_file() and not p.is_symlink() and sha(p)==item['gate_file_sha256'],'actual parent condition blob changed')
  arm='p1' if src=='short_0210' else 'native';v=gate['runs'][arm]['video'];require(sha(Path(v['file']))==v['sha256']==b['native_video']['sha256'],'actual parent output changed')
  results[src]={'passed':True,'parent_run':b['run_id'],'files':files,'current_gate_raw_sha256':sha(gp),'frozen_gate_raw_sha256':b['gate']['sha256'],'gate_canonical_sha256':canonical_parent_gate(gate),'ignored_gate_field':'top-level created_unix only','large_files_verified':include_snapshots}
 return results
