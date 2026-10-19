import ast,datetime,hashlib,io,json,pathlib,shutil,tokenize
B=pathlib.Path('/Users/researcher/DevProjects');OLD=B/'h3-timing-auto-source51310-r40-20261017/analysis/postrun';ROOT=B/'h3-timing-auto-source28289-r44-20261017';R=ROOT/'analysis/postrun';PARENT=B/'h3-timing-source28289-native-r42-20261017';A=PARENT/'analysis/postrun/captured/batch'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
def save(p,d):p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
files=['consume.py','one_phase.py','contract.py','remote_consume.py','evaluate.py','verify_single.py','test_phase_dependencies.py','test_postrun.py']
for n in files:
 assert not (R/n).exists();shutil.copy2(OLD/n,R/n)
# Source changes restricted to exact identifier/string tokens, not JSON evidence rewrites.
edits=[]
def change_tokens(name,mapping):
 p=R/name;before=p.read_text();tokens=[];found=[]
 for token in tokenize.generate_tokens(io.StringIO(before).readline):
  v=token.string
  if token.type==tokenize.NAME and v in mapping:new=mapping[v]
  elif token.type==tokenize.STRING:
   try:literal=ast.literal_eval(v)
   except (ValueError,SyntaxError):literal=None
   new=repr(mapping[literal]) if isinstance(literal,str) and literal in mapping else v
  else:new=v
  if new!=v:found.append({'old':v,'new':new})
  tokens.append(token._replace(string=new))
 after=tokenize.untokenize(tokens);p.write_text(after);edits.append({'file':name,'parent_sha256':sha(OLD/name),'new_sha256':sha(p),'tokens':found})
change_tokens('one_phase.py',{'another R40 phase driver':'another R44 phase driver'})
change_tokens('verify_single.py',{'r40_contract':'r44_contract','source51310 development-screened same-corpus transfer':'source28289 Elon Musk normal-preservation after known Native result'})
change_tokens('evaluate.py',{'development-screened source51310 from previously examined nighttime court corpus; Native+Auto only, no independent unseen-scene or architecture novelty claim':'source28289 Elon Musk normal-preservation after Native screening; automatic result not known at protocol freeze; no algorithm or thresholds changed; Native+Auto only'})
run='r44_source28289_seed2026101701_auto';native='r42_source_28289_seed2026101701_native';remote='/data5/researcher/h3_runs/timing_auto_source28289_r44_20261017';parentremote='/data5/researcher/h3_runs/timing_source28289_native_r42_20261017'
(R/'parents').mkdir()
pose=A/'final'/native/'pose'/(native+'_00001_.pose.json');job=A/'logs'/(native+'_job.json')
for src,dest in [(pose,R/'parents/native.pose.json'),(job,R/'parents/native_job.json')]:shutil.copy2(src,dest);assert sha(src)==sha(dest)
sp=read(ROOT/'configs/source.pose.json');np=read(pose);assert sp['provenance']==np['provenance']
future={'status':'NOT_PLANNED_NOT_GENERATED_NOT_EVALUATED','not_current_comparator':True,'role':'no manual result is included; any future arm requires a separate authorized version with actual input, condition, noise, video, pose and provenance binding; retain this Native+Auto report','success_scope':'normal protection; record unnecessary ON and any degradation without requiring automatic to outperform a manually chosen control'}
p=read(OLD/'PROTOCOL.json');p.update(schema='r44-phase-bounded-postrun-v1',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),root_local=str(ROOT),root_remote=remote,project=44,producer_manifest_sha256=sha(ROOT/'deploy_manifest.json'),producer_protocol_sha256=sha(ROOT/'configs/protocol.json'),producer_manifest_original=str(ROOT/'deploy_manifest.json'))
c=p['cases'][0];c.update(run_id=run,source_id='28289',parent_root=parentremote,parent_run=native,window_scope='R42 producer-predeclared five physical intervals, retained for normal-preservation assessment; never controller input; overlapping tail intervals are not independent')
p['parents']={'native':{'pose':'parents/native.pose.json','pose_sha256':sha(pose),'video':np['video']['path'],'video_sha256':np['video']['sha256'],'seed':2026101701,'job':'parents/native_job.json','job_sha256':sha(job),'NFE':20}}
p['source_pose_sha256']=sha(ROOT/'configs/source.pose.json');p['online_priority_roots']=[remote,'/data5/researcher/h3_runs/timing_auto_source51310_r40_20261017']
p['limits']=['Native output was examined before Auto: normal-preservation development case, not delay-repair success evidence','overlapping fullscan and tail windows are descriptors, not independent samples','R42 actual20 Native endpoints available through first intervention inclusive; Full and all future historical Native are permanently N/A after firstON','R42 actual Qwen embedding and8 clean entities/noise are archived; historical full processed/postaugmentation tree and raw packed preforward inputs absent','pose alone cannot certify shape, identity, hand amplitude or ghosting','all-OFF AV equality and measured141RGB equality remain separate; RGB=false retained without inventing its cause','no manual result planned/generated/included']
p['revision']='R44 case migration from frozen R40 bounded consumer; same numeric evaluation and phase dependency/inventory gates; actual R42 parent and normal-protection role.'
p['future_manual_reference']=future;p['case_role']=read(ROOT/'configs/CASE_ROLE_ADDENDUM.json')
plan=read(OLD/'OUTCOME_REVIEW_PLAN.json');plan.update(schema='r44-frozen-outcome-plan-v1',producer_protocol_sha256=p['producer_protocol_sha256'],case_scope='New-source normal protection after actual R42 Native result; Auto not generated at freeze.',future_manual_reference=future)
plan['questions']=['How many extra Full predictions and ON episodes occur on this normal Native case?','Are final timing, common-support pose errors and visual quality preserved?','If allOFF, do finalAV and141RGB each independently match the actual Native output?']
plan['user_presentation_labels'].pop('future_manual_not_present',None)
save(R/'OUTCOME_REVIEW_PLAN.json',plan);p['outcome_plan_sha256']=sha(R/'OUTCOME_REVIEW_PLAN.json');save(R/'PROTOCOL.json',p)
e={'source_pose':{'producer_file':'configs/source.pose.json','sha256':p['source_pose_sha256']},'Native_pose':{'remote_source':parentremote+'/analysis/postrun/captured/batch/final/'+native+'/pose/'+pose.name,'local':'parents/native.pose.json','sha256':sha(pose)},'parent_archive_closure':{k:sha(ROOT/'configs'/k) for k in ['parent_run_gate.json','parent_runtime_gate.json','parent_final_cpu_complete.json','parent_final_derived_files.json','parent_final_download.json','parent_file_inventory.json','parent_captures.json','parent_conditioning.json','parent_noise.json']},'copy_policy':'exact bytes only; scoped Python tokens and structured protocol fields; no global JSON text replacement','source_Native_pose_provenance_exact':True,'normal_role_addendum_sha256':sha(ROOT/'configs/CASE_ROLE_ADDENDUM.json')}
save(R/'EVIDENCE_BINDING.json',e)
b=read(OLD/'BINDING.template.json');b.update(schema='r44-root-bound-postrun-v1',remote_root=remote,protocol_sha256=sha(R/'PROTOCOL.json'),producer_manifest_sha256=p['producer_manifest_sha256']);save(R/'BINDING.template.json',b)
# BINDING.json deliberately absent until root binds the real service generation.
save(R/'audit/PREPARATION_DELTA.json',{'parent_postrun_freeze_sha256':sha(OLD/'FREEZE.json'),'parent_postrun':str(OLD),'code_edits':edits,'raw_copies':{n:sha(R/n) for n in files if n not in {e['file'] for e in edits}},'parent_entities':{str(src):sha(src) for src in [pose,job]}})
print(json.dumps({'postrun':str(R),'protocol_sha256':sha(R/'PROTOCOL.json'),'native_pose_sha256':sha(pose),'source_provenance_exact':True,'files':files}))
