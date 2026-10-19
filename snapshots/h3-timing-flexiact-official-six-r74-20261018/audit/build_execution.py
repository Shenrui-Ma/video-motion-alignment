"""Prepare the isolated R74 execution skeleton; never launch a process or GPU."""
from pathlib import Path
import json,hashlib,shutil,copy
R=Path(__file__).resolve().parents[1];P=Path('/Users/researcher/DevProjects/h3-timing-flexiact-expanded-r66-20261018');P72=Path('/Users/researcher/DevProjects/h3-timing-flexiact-prompt-pair-r72-20261018')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
assert not(R/'deploy_manifest.json').exists()
# Copy only dormant producer code and fixtures, never live mutable state.
for folder in ['scripts','extensions','source_snapshot/r63','configs/R49_evidence']:
 for p in (P/folder).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:
   dest=R/p.relative_to(P);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
for name in ['verify_pair.py','capture_checks.py']:
 dest=R/'analysis/postrun'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(P/'analysis/postrun'/name,dest)
# Six scientific numerical modules must remain byte exact to R66.
kernels=json.loads((P/'configs/runtime_kernel_hashes.json').read_text());protected=set(kernels)
for folder in ['scripts','extensions','analysis/postrun']:
 for p in (R/folder).rglob('*.py'):
  if str(p.relative_to(R)) not in protected:p.write_text(p.read_text().replace('r66','r74').replace('R66','R74').replace('h3-timing-flexiact-expanded-r74','h3-timing-flexiact-official-six-r74'))
(R/'scripts/r66_contract.py').unlink()
# No host reconfiguration after freeze; runtime chosen here from reviewed .41 parent.
(R/'scripts/prepare_host.py').unlink()
for name in ['parent_core_hashes.json','expected_checkpoint_hashes.json']:
 src=P72/'configs'/name
 if src.exists():shutil.copy2(src,R/'configs'/name)
parent=R/'configs/parent_graphs/r66_fitness_native_template.json';parent.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(P72/'configs/parent_graphs/r66_fitness_native_template.json',parent)
runtime=json.loads((P72/'configs/runtime.json').read_text());runtime.update(status='PENDING_ROOT_CAPACITY',remote_root='/data3/researcher/h3_runs/timing_flexiact_official_six_r74_20261018',gpu_uuid='GPU-REDACTED',expected_gpu_index=7,port=8542,profile='host41_gpu7_normal_reserve8',profile_scope='R72 reviewed .41 core/runtime; GPU7 is occupied by R69 until root exact release. R74 capacity and actual launch remain pending.')
put(R/'configs/runtime.json',runtime);put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','max_own_cards':2,'permitted_compute_processes':[],'note':'Root must verify R69 exact release, selected UUID/health/free memory and register any other own GPU peer before launch.'})
for folder in ['processes','logs','input','output','temp','user','custom_nodes']:(R/folder).mkdir(exist_ok=True)
put(R/'configs/runtime_kernel_hashes.json',{k:{'parent_file':str(P/k),'parent_sha256':sha(P/k),'current_sha256':sha(R/k),'byte_equal':sha(P/k)==sha(R/k)} for k in kernels})
# Keep the real R66 capture and tensor verifier; adapt only prompt/version and directory identity.
p=R/'analysis/postrun/verify_pair.py';text=p.read_text().replace("'prompt_version':'R49_original'","'prompt_version':'P1'");p.write_text(text)
# Freeze prompts, definitions, tests, source evidence as well as producer code.
p=R/'scripts/execution_gate.py';text=p.read_text().replace("'configs/source_selection','analysis/postrun'","'design','configs/prompts','tests','analysis/postrun'").replace("'source_selection_hashes.json'","'source_selection_hashes.json','prompt_ancestry.json','expected_checkpoint_hashes.json'");text=text.replace('20*1024**3','40*1024**3').replace('default=20480','default=40960').replace('a.free_mib>=20480','a.free_mib>=40960').replace('>=20GiB','>=40GiB');p.write_text(text)
p=R/'scripts/preflight.py';text=p.read_text().replace("'pairs':8,'distinct_motion_sources':5,'new_motion_sources':3","'pairs':6,'distinct_motion_sources':3,'new_motion_sources':0");p.write_text(text)
# Scientific registry: original inputs, shared P1 conditions and noise for each pair.
defs=json.loads((R/'design/PAIR_DEFINITIONS.json').read_text())['pairs'];cases=[]
for p in defs:
 for arm in ['native','forced']:
  case={'source_id':p['pair_key'],'pair_key':p['pair_key'],'motion_source_id':p['motion_source_id'],'original_pair_id':p['original_pair_id'],'group':p['group'],'source_is_new_motion_content':False,'parent_graph':str(parent.relative_to(R)),'parent_graph_sha256':sha(parent),'graph_template_only':True,'video':p['source']['video'],'portrait':p['portrait'],'provenance':p['source']['provenance'],'seed':2026101701,'run_id':f"r74_{p['pair_key']}_seed2026101701_{arm}",'identity':p['identity'],'prompt':p['prompt'],'prompt_file':p['prompt_file'],'prompt_sha256':p['prompt_sha256'],'video_sha256':p['source']['video_sha256'],'portrait_sha256':p['portrait_sha256'],'provenance_sha256':p['source']['provenance_sha256'],'arm':arm,'prompt_version':'P1','geometry':{'width':1152,'height':768,'frames':158,'fps':24},'valid_frame_count':147,'evaluation_indices':list(range(0,147,3)),'evaluation_crop_xywh':[0,0,1152,768],'reference_image_expected':p['reference_image_expected']};cases.append(case)
s=json.loads((P/'configs/scientific_contract.json').read_text());s.update(schema='r74-flexiact-official-six-p1-fixed-route-v1',case_order=[c['run_id'] for c in cases],cases=cases,source_ids=[p['pair_key'] for p in defs],pair_keys=[p['pair_key'] for p in defs],prompt_version='P1',source_selection='design/PAIR_DEFINITIONS.json',scope_note='Six remaining fixed official CSV pairs, all retained, P1 Native versus same P1 fixed mass-preserving route; three unique known motion sources. R72 two prompt-comparison pairs excluded.')
# Avoid inherited textual counts and file references.
for k in list(s):
 if k not in ['schema','new_method_claim','seeds','arms','case_order','cases','source_ids','pair_keys','geometry','NFE_per_job','callback_count','online_observer','router','prompt_version','source_selection','scope_note']:del s[k]
put(R/'configs/scientific_contract.json',s);put(R/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
put(R/'configs/source_selection_hashes.json',{str(p.relative_to(R)):sha(p) for p in sorted((R/'design').rglob('*')) if p.is_file()})
print('skeleton prepared; contract and graphs next')
