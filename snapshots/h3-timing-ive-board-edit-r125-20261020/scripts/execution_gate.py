"""Root decisions for Native-first screening; all scientific graphs stay registered."""
import argparse,hashlib,json,os,time,uuid
from pathlib import Path
from r125_contract import ROOT,read,sha,registry,require,SOURCES

def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,path)

def exclusive(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
 try:
  tmp.write_text(json.dumps(value,indent=2)+'\n');os.link(tmp,path)
 finally:
  if tmp.exists():tmp.unlink()

def stable_gate_hash(value):
 return hashlib.sha256(json.dumps({k:v for k,v in value.items() if k!='created_unix'},sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def persist_gate(path,value):
 if Path(path).exists():
  previous=read(path);require(stable_gate_hash(previous)==stable_gate_hash(value),'existing gate evidence changed; preserve original');return previous
 exclusive(path,value);return value

def approval(root=ROOT):
 root=Path(root);a=read(root/'audit/ROOT_SCREEN_APPROVAL.json');runtime=read(root/'configs/runtime.json');_,order=registry(root)
 require(a.get('schema')=='r125-native-screen-approval-v1' and a.get('root_approved') is True,'root screening approval pending')
 require(a['runtime_profile_sha256']==sha(root/'configs/runtime.json') and a['main_gpu_uuid']==runtime['gpu_uuid'],'runtime/device changed')
 require(a['registered_runs']==order and a['required_free_bytes']>=40*1024**3 and a['reserve_vram_gib']==8,'registered scope or headroom changed')
 return a

def owner_binding(root):
 owner=read(Path(root)/'processes/service.json');return {'pid':owner['pid'],'identity':owner['identity']}

def native_binding(root,source):
 root=Path(root);require(source in SOURCES,'unknown source');file=root/'analysis/postrun'/source/'NATIVE_RUNTIME_GATE.json';gate=read(file)
 run='r125_'+source+'_seed2026101701_native'
 require(gate.get('schema')=='r125-native-runtime-gate-v1' and gate.get('passed') is True and gate['source_id']==source and set(gate['runs'])=={'native'},'actual Native gate incomplete')
 require(gate['runtime_profile_sha256']==sha(root/'configs/runtime.json') and gate['service_owner']==owner_binding(root),'Native owner/runtime differs')
 require(gate['runs']['native']['run_id']==run and gate['runs']['native']['NFE']==20 and gate['runs']['native']['routed_blocks']==0,'Native execution scope differs')
 artifacts=gate['runs']['native']['binding_artifacts']
 for rel,digest in artifacts.items():
  path=Path(rel);require(not path.is_absolute() and '..' not in path.parts,'unsafe evidence path');require(sha(root/path)==digest,'Native evidence changed: '+rel)
 video=gate['runs']['native']['video'];path=Path(video['file']);require(path.is_relative_to(root/'output') and sha(path)==video['sha256'],'Native output changed')
 return {'source_id':source,'native_run':run,'native_gate_sha256':sha(file),'runtime_profile_sha256':gate['runtime_profile_sha256'],'service_owner':gate['service_owner'],'video_sha256':video['sha256'],'binding_artifacts':artifacts}

def decision(root,source):
 root=Path(root);file=root/'audit/decisions'/(source+'.json')
 if not file.exists():return None
 value=read(file);require(value.get('schema')=='r125-root-native-decision-v1' and value.get('root_reviewed') is True and value['choice'] in ('guide','skip'),'invalid root decision')
 require(value['binding']==native_binding(root,source),'decision bound to different actual Native evidence')
 require(isinstance(value.get('reason'),str) and bool(value['reason'].strip()),'decision reason required');return value

def ledger(root=ROOT):
 root=Path(root);file=root/'audit/SCREEN_LEDGER.json';value=read(file) if file.exists() else {'schema':'r125-screen-ledger-v1','rows':[]};rows=value['rows']
 require(value['schema']=='r125-screen-ledger-v1' and len(rows)<=len(SOURCES),'invalid screen ledger')
 for i,row in enumerate(rows):
  source=SOURCES[i];require(row['source_id']==source,'terminal source order changed');d=decision(root,source);require(d is not None and row['decision_sha256']==sha(root/'audit/decisions'/(source+'.json')),'terminal decision differs')
  require(row['native_gate_sha256']==d['binding']['native_gate_sha256'],'terminal Native differs')
  if d['choice']=='skip':
   require(row['status']=='native_only' and row['forced_run'] is None and row['pair_gate_sha256'] is None,'skip fabricated forced result')
   run='r125_'+source+'_seed2026101701_forced'
   require(not (root/'logs'/(run+'_job.json')).exists() and not (root/'analysis/postrun'/source/'PAIR_RUNTIME_GATE.json').exists(),'skip has forced submission or pair gate')
  else:
   gatefile=root/'analysis/postrun'/source/'PAIR_RUNTIME_GATE.json';g=read(gatefile)
   require(row['status']=='paired' and row['forced_run']=='r125_'+source+'_seed2026101701_forced' and g['passed'] is True and g['source_id']==source and set(g['runs'])=={'native','forced'} and g['service_owner']==owner_binding(root) and row['pair_gate_sha256']==sha(gatefile),'paired terminal evidence differs')
 return value

def first_guided(root=ROOT):
 return next((r for r in ledger(root)['rows'] if r['status']=='paired'),None)

def first_guided_reviewed(root=ROOT):
 root=Path(root);first=first_guided(root)
 if first is None:return True
 file=root/'audit/FIRST_GUIDED_REVIEW.json'
 if not file.exists():return False
 v=read(file)
 require(v.get('schema')=='r125-first-guided-review-v1' and v.get('root_reviewed') is True and v['source_id']==first['source_id'] and v['pair_gate_sha256']==first['pair_gate_sha256'] and v['service_owner']==owner_binding(root) and v['runtime_profile_sha256']==sha(root/'configs/runtime.json'),'first guided review differs')
 return True

def admitted_job(run,root=ROOT):
 root=Path(root);approval(root);jobs,_=registry(root);require(run in jobs,'unregistered run');rows=ledger(root)['rows'];i=len(rows)
 if i>=len(SOURCES) or jobs[run]['source_id']!=SOURCES[i] or not first_guided_reviewed(root):return False
 if jobs[run]['arm']=='native':return True
 d=decision(root,SOURCES[i]);return d is not None and d['choice']=='guide'

def finish_source(root,source):
 root=Path(root);value=ledger(root);require(len(value['rows'])<len(SOURCES) and SOURCES[len(value['rows'])]==source,'terminal source out of order');d=decision(root,source);require(d is not None,'decision missing')
 paired=d['choice']=='guide';gate=root/'analysis/postrun'/source/'PAIR_RUNTIME_GATE.json'
 row={'source_id':source,'status':'paired' if paired else 'native_only','native_run':d['binding']['native_run'],'forced_run':'r125_'+source+'_seed2026101701_forced' if paired else None,'native_gate_sha256':d['binding']['native_gate_sha256'],'pair_gate_sha256':sha(gate) if paired else None,'decision_sha256':sha(root/'audit/decisions'/(source+'.json')),'reason':d['reason'],'created_unix':time.time()}
 # Validate the candidate without replacing the old ledger until all referenced facts pass.
 if paired:
  g=read(gate);require(g['passed'] is True and g['source_id']==source and g['service_owner']==owner_binding(root),'guided pair failed')
 else:
  require(not (root/'logs'/('r125_'+source+'_seed2026101701_forced_job.json')).exists() and not gate.exists(),'skip after forced execution refused')
 value['rows'].append(row);atomic(root/'audit/SCREEN_LEDGER.json',value);ledger(root);return row

def write_decision(root,source,choice,reason):
 root=Path(root);approval(root);rows=ledger(root)['rows'];require(len(rows)<len(SOURCES) and source==SOURCES[len(rows)],'only current Native can be reviewed');require(first_guided_reviewed(root),'first guided review pending');require(choice in ('guide','skip') and bool(reason.strip()),'choice/reason required')
 value={'schema':'r125-root-native-decision-v1','root_reviewed':True,'choice':choice,'reason':reason,'binding':native_binding(root,source),'created_unix':time.time()};exclusive(root/'audit/decisions'/(source+'.json'),value);return value

def write_first_review(root):
 root=Path(root);approval(root);first=first_guided(root);require(first is not None,'no actual guided pair exists');value={'schema':'r125-first-guided-review-v1','root_reviewed':True,'source_id':first['source_id'],'pair_gate_sha256':first['pair_gate_sha256'],'service_owner':owner_binding(root),'runtime_profile_sha256':sha(root/'configs/runtime.json'),'created_unix':time.time()};exclusive(root/'audit/FIRST_GUIDED_REVIEW.json',value);return value

def seal(root=ROOT):
 root=Path(root);require(not(root/'processes/service.json').exists(),'service registry exists; producer seal locked');paths=[]
 for folder in ('scripts','extensions','configs/graphs','configs/parent_graphs','configs/R54_evidence','configs/source_selection','configs/prompts','design','analysis/postrun','tests','source_snapshot'):
  paths.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
 paths.extend(root/'configs'/n for n in ('runtime.json','scientific_contract.json','input_hashes.json','runtime_kernel_hashes.json','parent_core_hashes.json','source_selection_hashes.json','expected_checkpoint_hashes.json','storage_policy.json'))
 paths.extend((root/'PREPARED_INPUTS_MANIFEST.json',root/'audit/root_run_batch.py',root/'audit/INHERITED_BYTE_BINDINGS.json',root/'audit/ROOT_DESIGN_BINDINGS.json'))
 value={'schema':'r125-producer-seal-v1','files':{str(p.relative_to(root)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(paths)},'mutable_root_owned':['configs/admission.json','audit/ROOT_SCREEN_APPROVAL.json','audit/decisions/*.json','audit/FIRST_GUIDED_REVIEW.json'],'created_unix':time.time()};atomic(root/'deploy_manifest.json',value);return value

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['seal','approve-screen','decide','review-first-guided']);p.add_argument('--root-admitted',action='store_true');p.add_argument('--root-reviewed',action='store_true');p.add_argument('--source',choices=SOURCES);p.add_argument('--choice',choices=['guide','skip']);p.add_argument('--reason');p.add_argument('--free-mib',type=int,default=40960);a=p.parse_args()
 if a.action=='seal':v=seal()
 else:
  require(ROOT==Path(read(ROOT/'configs/runtime.json')['remote_root']),'actual remote root required')
  if a.action=='approve-screen':
   require(a.root_admitted and a.free_mib>=40960,'root hardware admission >=40GiB required');_,order=registry();v={'schema':'r125-native-screen-approval-v1','root_approved':True,'runtime_profile_sha256':sha(ROOT/'configs/runtime.json'),'main_gpu_uuid':read(ROOT/'configs/runtime.json')['gpu_uuid'],'registered_runs':order,'required_free_bytes':a.free_mib*1024**2,'reserve_vram_gib':8,'created_unix':time.time()};exclusive(ROOT/'audit/ROOT_SCREEN_APPROVAL.json',v)
  else:
   require(a.root_reviewed,'root actual quality review required');import service;service.assert_owned(read(ROOT/'processes/service.json'))
   if a.action=='decide':require(a.source and a.choice and a.reason,'source/choice/reason required');v=write_decision(ROOT,a.source,a.choice,a.reason)
   else:v=write_first_review(ROOT)
 print(json.dumps({'action':a.action,'files':len(v.get('files',{})),'source_id':v.get('source_id'),'choice':v.get('choice')},indent=2))
if __name__=='__main__':main()
