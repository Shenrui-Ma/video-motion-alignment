"""Record completed decoder-only reachability; never enables actual-auto intake."""
from pathlib import Path
import json,hashlib,time
R=Path(__file__).resolve().parents[1];P=R.parent/'h3-timing-oxygen-online-r133-20261020/precheck/audit/actual_precheck';h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda n:json.loads((P/n).read_text())
result=read('RESULT.json');review=read('ROOT_FIRST_ON_REVIEW.json');release=read('FINAL_RELEASE_VERIFIED.json');decisions=[read(f'step{i:03d}/DECISION.json')for i in [0,1]]
assert result['status']=='complete' and result['parent_run']=='r113_short_0252_seed2026101703_native' and result['seed']==2026101703 and result['first_ON_index']==1
assert not decisions[0]['active'] and decisions[0]['reason']=='awaiting_persistence' and decisions[1]['active']
assert review['scientific_preflight_passed'] and review['formal_H3_submission_requires_sealed_package_review']
for n,s in review['bindings'].items():assert h(P/n)==s,(n,'root review binding mismatch')
assert release['passed'] and release['fresh_task_cuda_absent'] and release['result_sha256']==h(P/'RESULT.json')
for row in [release['coordinator']]+release['children']:assert row['process_absent'] and row['CUDA_absent']
names=['RESULT.json','ROOT_FIRST_ON_REVIEW.json','FINAL_RELEASE_VERIFIED.json','CHILDREN_RELEASED.json','FIRST_ON_PERSON_SELECTION.json','FIRST_ON_CONTACT.jpg','step000/DECISION.json','step001/DECISION.json']
out={'schema':'r133-decoder-only-precheck-binding-v1','created_unix':time.time(),'historical_freeze':{'file':str(R/'HISTORY_FREEZE.json'),'sha256':h(R/'HISTORY_FREEZE.json')},'evidence':{n:{'file':str(P/n),'sha256':h(P/n)}for n in names},'summary':{'cached_run':result['parent_run'],'zero_based_steps_reviewed':[0,1],'first_ON_index':1,'first_physical_window':review['physical_window'],'observed_lag_frames':review['observed_lag_frames'],'controller_parameters_unchanged':review['fixed_controller_parameters_unchanged'],'precheck_exact_release':True},'scope':'Reachability on two cached Native predictions with actual decode/CPU pose. No extra guided prediction, Euler update or auto output was produced by this precheck.','actual_auto_intake_enabled':False,'formal_auto_contract_status':'AWAITING_FINAL_SEAL'}
p=R/'configs/PRECHECK_BINDING.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
freeze={'schema':'r133-precheck-binding-freeze-v1','files':{str(p.relative_to(R)):h(p),str(Path(__file__).relative_to(R)):h(Path(__file__))},'historical_freeze_unchanged':h(R/'HISTORY_FREEZE.json')}
f=R/'PRECHECK_BINDING_FREEZE.json';f.write_text(json.dumps(freeze,indent=2)+'\n');print(json.dumps({'passed':True,'binding':str(p),'binding_sha256':h(p),'freeze_sha256':h(f),'actual_auto_intake_enabled':False}))
