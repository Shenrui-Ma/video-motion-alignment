from pathlib import Path
from fractions import Fraction as F
import json,hashlib,shutil,subprocess,copy,time
D=Path('/Users/researcher/DevProjects');R=Path(__file__).resolve().parents[1];P=D/'h3-timing-ive-native-screen-r92-20261018';B=D/'h3-timing-ive-object-control-r91-20261018';C=D/'h3-timing-ivebench-heldout-r64-20261018'
REMOTE='/data5/researcher/h3_runs/timing_ive_task_repair_r100_20261019'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def cp(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
assert not (R/'deploy_manifest.json').exists(),'builder cannot alter sealed package'
# Copy only sealed source code; old executions and claims are not inherited.
m=read(P/'deploy_manifest.json');numeric=set(read(P/'configs/runtime_kernel_hashes.json'))
for rel in m['files']:
 if not (rel.startswith(('scripts/','extensions/','source_snapshot/','tests/','analysis/postrun/')) or rel=='audit/root_run_batch.py'):continue
 if rel.startswith('tests/') and Path(rel).name in {'test_inputs.py','test_clip_timebase.py','test_registered_pairs.py','test_host_migration.py'}:continue
 target=R/rel.replace('r92_contract.py','r100_contract.py');cp(P/rel,target)
 if rel.endswith('.py') and not rel.startswith('source_snapshot/') and rel not in numeric:
  text=target.read_text().replace('r92','r100').replace('R92','R100').replace('long_0047','short_0114').replace('long_0123','short_0392');target.write_text(text)
for rel in ['configs/parent_core_hashes.json','configs/expected_checkpoint_hashes.json','configs/storage_policy.json','configs/R54_evidence/short_0210/captures.json','configs/parent_graphs/r63_template_native.json','design/OFFICIAL_REF_EN.txt']:
 cp(P/rel,R/rel)
for rel in ['deploy_manifest.json','configs/runtime.json','scripts/execution_gate.py','scripts/run_queue.py','analysis/postrun/verify_pair.py','audit/root_run_batch.py']:
 cp(P/rel,R/'source_snapshot/r92_parent'/rel)
for rel in ['deploy_manifest.json','configs/scientific_contract.json','configs/graphs/r91_short_0114_seed2026101701_native.json','configs/graphs/r91_short_0114_seed2026101701_forced.json','design/short_0114_P1_candidate.txt']:
 cp(B/rel,R/'source_snapshot/r91_parent'/rel)
for rel in ['configs/scientific_contract.json','configs/source_selection/SELECTED_4_MANIFEST.json']:
 cp(C/rel,R/'source_snapshot/r64_parent'/rel)
for directory in ['inputs','input','output','temp','user','custom_nodes','processes','logs','configs/graphs','configs/prompts','audit/router','audit/x0']:(R/directory).mkdir(parents=True,exist_ok=True)
rows=[copy.deepcopy(read(B/'design/EXECUTION_INPUT_PLAN.json')['pairs'][0])]
sid='short_0392';prov=read(C/'inputs'/f'{sid}_provenance.json');old=next(x for x in read(C/'configs/scientific_contract.json')['cases'] if x['source_id']==sid)
probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_frames','-of','json',str(C/'inputs'/f'{sid}_original.mp4')],text=True));st=probe['streams'][0];pts=[F(x['best_effort_timestamp'])*F(st['time_base']) for x in probe['frames']];end=(int(st['start_pts'])+int(st['duration_ts']))*F(st['time_base'])
row=dict(source_id=sid,pair_id=sid,official_task=old['original_task'],source=dict(file=str(C/'inputs'/f'{sid}_original.mp4'),sha256=sha(C/'inputs'/f'{sid}_original.mp4'),frame_count=len(pts),fps_rational=st['avg_frame_rate'],time_base=st['time_base'],actual_pts_rational=list(map(str,pts)),actual_pts_s=[float(x) for x in pts]),clip=dict(start_frame=0,end_frame_inclusive=len(pts)-1,start_pts_rational=str(pts[0]),end_pts_rational_inclusive=str(pts[-1]),end_exclusive_rational=str(end),scope='full official short source'),input_protocol=dict(h3_frame_count=73,effective_frame_count=57,input_to_original_frame=prov['input_to_original_frame']),edit_prompt=old['original_task']['edit_prompt'])
rows.append(row)
# Original, prepared video and provenance are copied byte for byte. No cross-host float tensor expectation.
prepared=[]
for row in rows:
 sid=row['pair_id'];parent=B if sid=='short_0114' else C
 for kind,ext in [('original','mp4'),('video','mp4'),('provenance','json'),('prompt','txt')]:cp(parent/'inputs'/f'{sid}_{kind}.{ext}',R/'inputs'/f'{sid}_{kind}.{ext}')
 prepared.append(dict(pair_id=sid,files={k:dict(file=f'inputs/{sid}_{k}.{ext}',sha256=sha(R/'inputs'/f'{sid}_{k}.{ext}'),bytes=(R/'inputs'/f'{sid}_{k}.{ext}').stat().st_size) for k,ext in [('original','mp4'),('video','mp4'),('provenance','json'),('prompt','txt')]},h3_frames=row['input_protocol']['h3_frame_count'],valid_frames=row['input_protocol']['effective_frame_count']))
cp(B/'design/short_0114_P1_candidate.txt',R/'design/short_0114_P1_candidate.txt')
prompt='''subject_definitions:
<Video 1> is the source video for this local video edit, providing the original camera framing, visible action sequence, pacing and duration.
<Subject 1> is the woman with long dark hair wearing a white suit in <Video 1>. Her face, hair, clothing, position and hand gestures are retained.
<Subject 2> is the original wood-paneled room in <Video 1>, including the pale carved fireplace and mantel directly behind the woman. The fireplace and its projecting carved surround are the region to remove.
Source context: A woman in a white suit is standing in front of an ornate fireplace, gesturing with her hands as if she is explaining something.

summary:
[video editing] The target video is an edited version of <Video 1>. The woman continues the original gestures in the same room, with the ornate fireplace removed.
Requested edit: Remove the ornate fireplace

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - preserve the woman's identity, hair, white suit, body position, expressions and complete hand-gesture sequence, including their original timing.
<Subject 2> (appears in [Shot 1]): partially_preserved - remove the entire ornate fireplace, its pale carved mantel shelf and carved supporting surround behind the woman. Fill that local region with a continuous plain wall consistent with the surrounding room's color, perspective and lighting. Retain the rest of the original room and its composition.
<Video 1> (cut and pacing structure): fully_preserved - preserve the original camera framing and movement, shot continuity, action order, timing and duration.

 detailed_description:
The target video retains the photographic appearance, warm indoor lighting and camera composition of <Video 1>.
[Shot 1] The same woman in a white suit stands in the same place, moving her hands and speaking with the same expressions as in <Video 1>. Behind her is a continuous plain section of the original room's wall where the ornate fireplace used to be. The carved fireplace, projecting mantel shelf and supporting columns are absent throughout the shot. Her foreground silhouette and gestures remain clear against the repaired background.
The complete visible action sequence and all its phases follow <Video 1> in their original order and timing.

overall_soundscape:
No specific soundscape is requested.

non_diegetic_music:
No specific music is requested.
'''.replace('\n detailed_description:','\ndetailed_description:')
(R/'design/short_0392_P1_candidate.txt').write_text(prompt)
for row in rows:cp(R/'design'/(row['pair_id']+'_P1_candidate.txt'),R/'configs/prompts'/(row['pair_id']+'.txt'))
proposal={'status':'CPU_PREPARED_TASK_REPAIR_ROOT_REVIEW_PENDING','items':[dict(source_id=r['pair_id'],official_task=r['official_task'],source_sha256=r['source']['sha256'],prompt_sha256=sha(R/'configs/prompts'/(r['pair_id']+'.txt')),scope='full official short source',prompt_origin='R91 exact P1 bytes' if r['pair_id']=='short_0114' else 'new H3 six-section P1 based on original source and official removal task') for r in rows],'no_innovation_claim':True}
put(R/'design/PROPOSAL.json',proposal);put(R/'design/INPUT_PLAN.json',{'schema':'r100-task-repair-input-plan-v1','pairs':rows,'source_order':[r['pair_id'] for r in rows]})
put(R/'design/EXECUTION_INPUT_PLAN.json',{'schema':'r100-execution-input-plan-v1','pairs':rows})
put(R/'configs/source_selection/SELECTED_2_MANIFEST.json',{'schema':'r100-task-repair-selection-v1','pairs':rows,'scope':'Two user-reported failed basic editing tasks; selected after observing prior P0 failures, not held-out selection','source_selection_before_current_generation':True,'previous_failed_outcomes_retained':True})
put(R/'configs/source_selection/OFFICIAL_SOURCE_ORIGIN.json',{'repository_commit':read(C/'configs/source_selection/SELECTED_4_MANIFEST.json')['official_repository_commit'],'dataset_revision':read(C/'configs/source_selection/SELECTED_4_MANIFEST.json')['official_dataset_revision'],'parent_selection_sha256':sha(C/'configs/source_selection/SELECTED_4_MANIFEST.json'),'sources':[x for x in read(C/'configs/source_selection/SELECTED_4_MANIFEST.json')['pairs'] if x['pair_id'] in ('short_0114','short_0392')]})
put(R/'configs/source_selection_hashes.json',{p.name:sha(p) for p in (R/'configs/source_selection').iterdir()})
put(R/'PREPARED_INPUTS_MANIFEST.json',{'schema':'r100-byte-reused-inputs-v1','input_plan_sha256':sha(R/'design/INPUT_PLAN.json'),'pairs':prepared})
put(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()})
# Contract combines R91 strict per-source prompts/inputs with R92 Native-first administrative admission.
contract=(B/'scripts/r91_contract.py').read_text().replace('r91','r100').replace('R91','R100').replace("'long_0039'","'short_0392'").replace("'short_0392': (158, 144)","'short_0392': (73, 57)")
(R/'scripts/r100_contract.py').write_text(contract)
runtime=read(P/'configs/runtime.json');runtime.update(remote_root=REMOTE,port=8564,profile='host9_gpu0_r100_normal_reserve8',profile_scope='Two task repairs; Native first then root task acceptance guide/skip; first actual guided pair review; 40GiB normal/reserve8 admission.')
put(R/'configs/runtime.json',runtime);put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','permitted_compute_processes':[],'existing_comfy_port':None})
s=read(P/'configs/scientific_contract.json');s.update(schema='r100-native-first-task-repair-v1',source_ids=['short_0114','short_0392'],case_order=[],cases=[],purpose='Repair two failed basic edits with structured P1; root accepts each actual Native before any matched guided job. No architecture claim.',input_plan_sha256=sha(R/'design/EXECUTION_INPUT_PLAN.json'),root_input_plan_sha256=sha(R/'design/INPUT_PLAN.json'),root_proposal_sha256=sha(R/'design/PROPOSAL.json'),prepared_input_manifest_sha256=sha(R/'PREPARED_INPUTS_MANIFEST.json'),source_selection_sha256=sha(R/'configs/source_selection/SELECTED_2_MANIFEST.json'),prompt_sha256={r['pair_id']:sha(R/'configs/prompts'/(r['pair_id']+'.txt')) for r in rows})
for k in ['prompt_template_sha256','prompt_fields_sha256']:s.pop(k,None)
s['screening']['schema']='r100-native-screen-policy-v1';s['screening']['fixed_source_denominator']=2
s['evaluation'].update(fixed_case_denominator=2,adaptation='Complete official short sources; original frame/PTS map retained, padding excluded; source-specific basic edit acceptance precedes any guide.',visibility_policy='0114 ball/player interactions;0392 hand gestures with local background removal. Preserve failures and skips.')
s['acceleration_axes']['cache']='Same-source Native/forced share actual .9 conditions and raw AV noise; two independent caches.';s['acceleration_axes']['postprocessing']='Original R91 0114 input107/105 and R64 0392 input73/57 reused exact; crop16,8,1280,720@24; no speed change.'
for row in rows:
 sid=row['pair_id'];pr=next(x for x in prepared if x['pair_id']==sid)
 for arm in ['native','forced']:
  run=f'r100_{sid}_seed2026101701_{arm}';s['case_order'].append(run);s['cases'].append(dict(run_id=run,source_id=sid,arm=arm,seed=2026101701,prompt_version='P1-local-v1',prompt=(R/'configs/prompts'/(sid+'.txt')).read_text(),prompt_sha256=s['prompt_sha256'][sid],parent_graph='configs/parent_graphs/r63_template_native.json',parent_graph_sha256=sha(R/'configs/parent_graphs/r63_template_native.json'),video=sid+'_video.mp4',provenance=sid+'_provenance.json',video_sha256=pr['files']['video']['sha256'],provenance_sha256=pr['files']['provenance']['sha256'],geometry=dict(width=1312,height=736,frames=row['input_protocol']['h3_frame_count'],fps=24),valid_frame_count=row['input_protocol']['effective_frame_count'],reference_video_count=1,reference_image_count=0,original_task=row['official_task'],evaluation_crop_xywh=[16,8,1280,720],clip=row['clip'],evaluation_scope='official short source subset; basic task repair'))
put(R/'configs/scientific_contract.json',s);put(R/'configs/queue.json',dict(jobs=s['case_order'],finalize=True))
import sys;sys.path.insert(0,str(R/'scripts'));import r100_contract as co
for case in s['cases']:put(R/'configs/graphs'/(case['run_id']+'.json'),co.expected_graph(R,case))
# General source helpers and timeline stay the same arithmetic.
p=R/'scripts/input_contract.py';t=p.read_text();start=t.index('SOURCES=');stop=t.index('\ndef sha',start);t=t[:start]+"SOURCES=('short_0114','short_0392')\nLENGTHS=((107,105),(73,57))\n"+t[stop:];p.write_text(t)
p=R/'scripts/preflight.py';p.write_text(p.read_text().replace("'sources':5","'sources':2"))
p=R/'scripts/prepare_inputs.py';t=p.read_text();t=t.replace("SELECTION_SHA = 'd34bafca1be57f5e853eeda7960400b07b8194018d5e86744f6c3ad94c1e71f7'",'SELECTION_SHA = '+repr(sha(R/'design/INPUT_PLAN.json')));t=t.replace("['all', 'short_0114', 'short_0392', 'long_0167', 'long_0173', 'long_0174']","['all','short_0114','short_0392']").replace("['short_0114', 'short_0392', 'long_0167', 'long_0173', 'long_0174']","['short_0114','short_0392']");p.write_text(t)
# Numerical source files retain original bytes; wrapper names only change import.
k=read(P/'configs/runtime_kernel_hashes.json')
for rel,row in k.items():row.update(parent_file=str(P/rel),parent_sha256=sha(P/rel),current_sha256=sha(R/rel),byte_equal=sha(P/rel)==sha(R/rel));assert row['byte_equal']
put(R/'configs/runtime_kernel_hashes.json',k)
(R/'design/NEXT_EVALUATION_RULES.txt').write_text('先检查0114霓虹球是否完成且原运球保留，0392壁炉整体是否移除且人物/手势保留。root实际Native审阅后决定guide/skip；基础编辑失败保存并skip，不自动引导。完整有效帧与正式MF均保留，首次实际引导后再次审阅。该批检验提示表达适配与既有固定干预，不作新方法声明。\n')
s['evaluation']['rules_sha256']=sha(R/'design/NEXT_EVALUATION_RULES.txt');put(R/'configs/scientific_contract.json',s)
cp(P/'audit/remote_cpu_validate.py',R/'audit/remote_cpu_validate.py')
put(R/'audit/INHERITED_BYTE_BINDINGS.json',dict(parent_r92_seal_sha256=sha(P/'deploy_manifest.json'),parent_r91_seal_sha256=sha(B/'deploy_manifest.json'),parent_r64_scientific_contract_sha256=sha(C/'configs/scientific_contract.json'),six_numerical_files=k,inputs=read(R/'configs/input_hashes.json'),prompt_0114_exact=sha(R/'configs/prompts/short_0114.txt')==sha(B/'design/short_0114_P1_candidate.txt')))
print('Created',R,co.registry()[1])
