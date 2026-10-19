from pathlib import Path
from fractions import Fraction
import shutil,json,hashlib,math,ast
R=Path(__file__).resolve().parents[1];P=Path('/Users/researcher/DevProjects/h3-timing-ivebench-expanded-r73-20261018');S=Path('/Users/researcher/DevProjects/h3-ivebench-subject-candidates-r82-20261018');A=Path('/Users/researcher/DevProjects/h3-timing-local-edit-repair-r80-20261018');H=Path('/Users/researcher/DevProjects/h3-timing-local-edit-protocol-r78-20261018')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
for folder in ['scripts','extensions','tests','source_snapshot','analysis/postrun']:
 shutil.copytree(P/folder,R/folder,ignore=shutil.ignore_patterns('__pycache__'),dirs_exist_ok=True)
for folder in ['configs/parent_graphs','configs/R54_evidence']:
 shutil.copytree(P/folder,R/folder,dirs_exist_ok=True)
for folder in ['configs/graphs','configs/prompts','configs/source_selection','design','inputs']:(R/folder).mkdir(parents=True,exist_ok=True)
for name in ['parent_core_hashes.json','runtime_kernel_hashes.json','expected_checkpoint_hashes.json','storage_policy.json']:shutil.copy2(P/'configs'/name,R/'configs'/name)
# Only administrative lifecycle files inherit the subsequently reviewed fixes.
for name in ['service.py','launch_remote.py','supervise_service.py','process_identity.py','service_entry.py']:
 shutil.copy2(A/'scripts'/name,R/'scripts'/name)
for p in R.rglob('*.py'):
 if 'source_snapshot' in p.parts or p.name=='bootstrap.py':continue
 s=p.read_text().replace('r73','r83').replace('R73','R83').replace('r80','r83').replace('R80','R83').replace('h3-timing-ivebench-expanded-r83-20261018','h3-timing-subject-edits-r83-20261018').replace('h3-timing-local-edit-repair-r83-20261018','h3-timing-subject-edits-r83-20261018')
 p.write_text(s)
(R/'scripts/r73_contract.py').rename(R/'scripts/r83_contract.py')
ids=['short_0131','short_0268','short_0343','short_0274','short_0085','short_0358','short_0178']
source={x['source_id']:x for x in read(S/'audit/SOURCE_REVIEW.json')['rows']};pairs=[];plans=[];lengths=[]
for sid in ids:
 x=source[sid];t=x['timebase'];fps=Fraction(t['fps_rational']);pts=[str(Fraction(i)/fps) for i in range(t['decoded_frames'])];valid=round(Fraction(t['decoded_frames']*24)/fps);T=math.ceil((valid-5)/17)*17+5
 mapping=[min(range(len(pts)),key=lambda k:(abs(Fraction(pts[k])-Fraction(i,24)),k)) for i in range(valid)];assert mapping[-1]==t['decoded_frames']-1
 protocol={'width':1312,'height':736,'fps':24,'effective_frame_count':valid,'h3_frame_count':T,'input_to_original_frame':mapping+[mapping[-1]]*(T-valid),'padding':'last-frame hold to17k+5; excluded from evaluation','temporal_resample':'nearest actual CFR rational PTS, ties earlier','crop_xywh':[16,8,1280,720]}
 src={'file':x['source_file'],'sha256':x['source_sha256'],'frame_count':t['decoded_frames'],'actual_pts_s':t['actual_pts_s'],'actual_pts_rational':pts,'fps_rational':t['fps_rational'],'width':t['width'],'height':t['height']}
 task=x['official_task'];pairs.append({'source_id':sid,'official_task':task,'source':src,'input_protocol':protocol,'generated_h3_results_consulted':0,'known_development':x['known_development'],'source_review':{'phases':x['visible_phases'],'limitations':x['limitations']}})
 plans.append(dict(pair_id=sid,**task,source=src,input_protocol=protocol));lengths.append((T,valid))
sel={'schema':'r83-source-selected-seven-v1','official_revision':read(S/'metadata/REVIEW_PLAN.json')['official_dataset_revision'],'selected_order':ids,'selection_before_generation':True,'source_review_sha256':sha(S/'audit/SOURCE_REVIEW.json'),'pairs':pairs}
put(R/'configs/source_selection/SELECTED_7_MANIFEST.json',sel)
put(R/'configs/source_selection_hashes.json',{'SELECTED_7_MANIFEST.json':sha(R/'configs/source_selection/SELECTED_7_MANIFEST.json')})
plan={'schema':'r83-source-input-plan-v1','source_selection_sha256':sha(R/'configs/source_selection/SELECTED_7_MANIFEST.json'),'selection_before_generation':True,'generated_h3_results_consulted':0,'selected_order':ids,'pairs':plans};put(R/'design/INPUT_PLAN.json',plan)
for name in ['scripts/r83_contract.py','scripts/input_contract.py']:
 p=R/name;s=p.read_text();s=s.replace("SOURCES=('short_0252','short_0344','short_0065','short_0135','short_0035')",'SOURCES='+repr(tuple(ids)))
 if 'SOURCE_LENGTHS=' in s:
  start=s.index('SOURCE_LENGTHS=');end=s.index('\n',start);s=s[:start]+'SOURCE_LENGTHS='+repr(dict(zip(ids,lengths)))+s[end:]
 if 'LENGTHS=' in s and name.endswith('input_contract.py'):
  start=s.index('LENGTHS=');end=s.index('\n',start);s=s[:start]+'LENGTHS='+repr(tuple(lengths))+s[end:]
 s=s.replace('SELECTED_5_MANIFEST','SELECTED_7_MANIFEST').replace("len(s['cases'])==10","len(s['cases'])==14").replace('fixed five','fixed seven').replace('Five source','Seven source').replace('five selected','seven selected')
 p.write_text(s)
p=R/'scripts/prepare_inputs.py';s=p.read_text();s=s.replace("SELECTION_SHA = '251953fabad53cdd79979de008478220398e04197babda9c74531ef96f6b4eb9'",'SELECTION_SHA = '+repr(sha(R/'design/INPUT_PLAN.json'))).replace("['all','short_0252','short_0344','short_0065','short_0135','short_0035']",repr(['all']+ids)).replace("['short_0252','short_0344','short_0065','short_0135','short_0035']",repr(ids));p.write_text(s)
runtime=read(H/'configs/runtime.json');runtime.update(remote_root='/data3/researcher/h3_runs/timing_subject_edits_r83_20261018',port=8549,status='CPU_PREPARATION_ROOT_LAUNCH_PENDING',profile='host41_gpu6_r83_normal_reserve8',profile_scope='Same host41 core and numerical runtime as R78; full source physical duration. Root actual GPU/free/peer admission pending.');put(R/'configs/runtime.json',runtime)
put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
put(R/'configs/queue.json',{'jobs':[f'r83_{sid}_seed2026101701_{a}' for sid in ids for a in ['native','forced']],'finalize':True})
shutil.copy2(H/'design/OFFICIAL_REF_EN.txt',R/'design/OFFICIAL_REF_EN.txt');shutil.copy2(Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/audit/task_fidelity_review_20261018/NEXT_EVALUATION_RULES.txt'),R/'design/NEXT_EVALUATION_RULES.txt')
put(R/'audit/PREPARATION_SCOPE.json',{'ids':ids,'lengths_total_valid':lengths,'gpu_started':False,'write_ownership':str(R),'numeric_parent':str(P),'administrative_parent':str(A),'runtime_parent':str(H),'host':runtime,'root_only_gpu':True})
print(list(zip(ids,lengths)))
