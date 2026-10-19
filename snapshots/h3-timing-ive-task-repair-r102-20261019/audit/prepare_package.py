from pathlib import Path
from fractions import Fraction as F
import json,hashlib,shutil,subprocess,copy,time
D=Path('/Users/researcher/DevProjects');R=Path(__file__).resolve().parents[1]
P=D/'h3-timing-ive-task-repair-r100-20261019';A=D/'h3-timing-ivebench-remaining-r69-20261018';B=D/'h3-timing-ivebench-heldout-r64-20261018'
REMOTE='/data5/researcher/h3_runs/timing_ive_task_repair_r102_20261019'
SPECS=[('short_0263',A,90,74),('short_0092',B,73,58),('short_0126',B,124,109)]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def cp(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
assert not(R/'deploy_manifest.json').exists(),'sealed package'
seal=read(P/'deploy_manifest.json');numeric=set(read(P/'configs/runtime_kernel_hashes.json'))
for rel in seal['files']:
 if not(rel.startswith(('scripts/','extensions/','source_snapshot/','tests/','analysis/postrun/')) or rel in ('audit/root_run_batch.py','audit/remote_cpu_validate.py')):continue
 dest=R/rel.replace('r100_contract.py','r102_contract.py');cp(P/rel,dest)
 if rel.endswith('.py') and not rel.startswith('source_snapshot/') and rel not in numeric:
  dest.write_text(dest.read_text().replace('r100','r102').replace('R100','R102').replace('short_0114','short_0263').replace('short_0392','short_0092'))
for rel in ['configs/parent_core_hashes.json','configs/expected_checkpoint_hashes.json','configs/R54_evidence/short_0210/captures.json','configs/parent_graphs/r63_template_native.json','design/OFFICIAL_REF_EN.txt']:cp(P/rel,R/rel)
for rel in ['deploy_manifest.json','configs/scientific_contract.json','configs/runtime.json','scripts/r100_contract.py','scripts/execution_gate.py','scripts/run_queue.py','analysis/postrun/verify_pair.py','audit/root_run_batch.py']:cp(P/rel,R/'source_snapshot/r100_parent'/rel)
for name,old in [('r69_parent',A),('r64_input_parent',B)]:cp(old/'configs/scientific_contract.json',R/'source_snapshot'/name/'configs/scientific_contract.json')
for d in ['inputs','input','output','temp','user','custom_nodes','processes','logs','configs/graphs','configs/prompts','audit/router','audit/x0']:(R/d).mkdir(parents=True,exist_ok=True)
# Preserve all four original input artifacts byte-for-byte; reconstruct the actual rational PTS plan.
rows=[];prepared=[]
for sid,old,total,valid in SPECS:
 for kind,ext in [('original','mp4'),('video','mp4'),('provenance','json'),('prompt','txt')]:cp(old/'inputs'/f'{sid}_{kind}.{ext}',R/'inputs'/f'{sid}_{kind}.{ext}')
 case=next(x for x in read(old/'configs/scientific_contract.json')['cases'] if x['source_id']==sid);prov=read(R/'inputs'/f'{sid}_provenance.json')
 raw=R/'inputs'/f'{sid}_original.mp4'
 probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_frames','-of','json',str(raw)],text=True));st=probe['streams'][0];pts=[F(x['best_effort_timestamp'])*F(st['time_base']) for x in probe['frames']];end=(int(st['start_pts'])+int(st['duration_ts']))*F(st['time_base'])
 row=dict(source_id=sid,pair_id=sid,official_task=case['original_task'],source=dict(file=str(old/'inputs'/f'{sid}_original.mp4'),sha256=sha(raw),frame_count=len(pts),fps_rational=st['avg_frame_rate'],time_base=st['time_base'],actual_pts_rational=list(map(str,pts)),actual_pts_s=[float(x) for x in pts]),clip=dict(start_frame=0,end_frame_inclusive=len(pts)-1,start_pts_rational=str(pts[0]),end_pts_rational_inclusive=str(pts[-1]),end_exclusive_rational=str(end),scope='full official short source'),input_protocol=dict(h3_frame_count=total,effective_frame_count=valid,input_to_original_frame=prov['input_to_original_frame']),edit_prompt=case['original_task']['edit_prompt'],input_parent=str(old))
 rows.append(row);prepared.append(dict(pair_id=sid,files={k:dict(file=f'inputs/{sid}_{k}.{ext}',sha256=sha(R/'inputs'/f'{sid}_{k}.{ext}'),bytes=(R/'inputs'/f'{sid}_{k}.{ext}').stat().st_size) for k,ext in [('original','mp4'),('video','mp4'),('provenance','json'),('prompt','txt')]},h3_frames=total,valid_frames=valid))
prompts={
'short_0263':'''subject_definitions:
<Video 1> is the source video for this local video edit, providing the original blue lounge chair, garden setting, camera framing, reading action and its timing.
<Subject 1> is the woman reclining in the blue lounge chair in <Video 1>, holding an open book. Her identity and age are the parts to change to a young girl; her seated placement and reading action are retained.
<Subject 2> is the blue fabric lounge chair, the open book, and the surrounding original outdoor plants, flowers and furnishings in <Video 1>.

summary:
[video editing] The target video is an edited version of <Video 1>. A young girl occupies the original woman's place in the blue lounge chair and continues reading the same book in the same garden.
Requested edit: Replace the woman with a young girl

retention_analysis:
<Subject 1> (appears in [Shot 1]): partially_preserved - replace the adult woman with a young girl. Preserve the original reclined sitting pose, body orientation, position in the chair, hand placement and contact with the open book, and the entire reading and page-handling action in its original order and timing. Adapt her body proportions to the young girl while keeping these interactions.
<Subject 2> (appears in [Shot 1]): fully_preserved - retain the blue lounge chair, open book, surrounding plants and flowers, furnishings, original layout and lighting.
<Video 1> (cut and pacing structure): fully_preserved - retain the original camera framing and movement, shot continuity, visible action phases, timing and duration.

detailed_description:
The target video retains the photographic garden appearance, natural outdoor lighting and camera composition of <Video 1>.
[Shot 1] A young girl reclines in the original blue fabric lounge chair in the same position and orientation as the woman in <Video 1>. She holds and reads the same open book. Her hands follow the original movements and maintain the same contact with its pages. The chair supports her throughout the shot, and the original plants, flowers and surrounding furnishings stay in place. The source reading action continues with its original timing and duration.

overall_soundscape:
No specific soundscape is requested.

non_diegetic_music:
No specific music is requested.
''',
'short_0092':'''subject_definitions:
<Video 1> is the source video for this local video edit, providing the original woman, room, filming camera, visible gestures and their timing.
<Subject 1> is the woman with two hair buns wearing a green hoodie and light striped trousers, seated in the original room in <Video 1>.
<Subject 2> is all visible plants in the room in <Video 1>, including the foliage, flowers and small potted plants in the foreground and background. These plants are the objects to remove.
<Subject 3> is the original room, window, desk, shelves, furnishings and the black filming camera on its tripod in <Video 1>.

summary:
[video editing] The target video is an edited version of <Video 1>. The same woman continues her original gestures in the same room, with the plants removed.
Requested edit: Remove the plants in the room

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - preserve the woman's identity, hair, green hoodie, trousers, seated position, expressions and complete visible hand and upper-body action sequence in its original order and timing.
<Subject 2> (appears in [Shot 1]): partially_preserved - remove every visible plant, including leaves, stems and flowers, from the foreground and background. Restore the local background surfaces behind them in the perspective, color and lighting of the original room.
<Subject 3> (appears in [Shot 1]): fully_preserved - preserve the original room layout, window, desk, shelves, furnishings, filming camera and tripod, and all non-plant objects.
<Video 1> (cut and pacing structure): fully_preserved - preserve the original camera framing and movement, shot continuity, gesture phases, timing and duration.

detailed_description:
The target video retains the photographic appearance, daylight and composition of <Video 1>.
[Shot 1] The same woman remains seated in her original place, smiling and performing the original wave and hand-to-chest movements with the same timing. The black filming camera and tripod remain in the foreground. The window, desk, shelves and other room objects keep their original positions. The foliage, flowers and small plants throughout the room have been removed; the revealed local surfaces fit the existing room. The complete original gesture sequence continues through the end of the shot.

overall_soundscape:
No specific soundscape is requested.

non_diegetic_music:
No specific music is requested.
''',
'short_0126':'''subject_definitions:
<Video 1> is the source video for this local video edit, providing the man, bed, bright bedroom, camera framing, upward stretch and its timing.
<Subject 1> is the short-haired man wearing a gray T-shirt and plaid shorts, sitting on the edge of the bed with his back toward the camera and facing the bright window in <Video 1>.
<Subject 2> is the original bed, white bedding, window and blinds, doorway, full-length mirror and remaining bedroom in <Video 1>.
<Subject 3> is a newly added cat sitting on the bed next to the man.

summary:
[video editing] The target video is an edited version of <Video 1>. A cat sits on the bed beside the man as he continues the original seated stretch in the same bedroom.
Requested edit: Add a cat on the bed next to the man

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - preserve the man's identity, hair, clothing, seated position at the bed edge, orientation toward the window and complete arm and torso stretch. His hands rise and extend overhead and his torso follows the original stretch, in the original order and timing.
<Subject 2> (appears in [Shot 1]): fully_preserved - retain the original bedroom layout, white bedding, bed shape, window and blinds, doorway, mirror, lighting and camera perspective. Add the cat within the visible bed area beside the man while retaining the surrounding scene.
<Subject 3> (appears in [Shot 1]): newly_added - place a naturally proportioned cat sitting on the bed beside the man, grounded on the bedding and consistently present in the shot. The man continues his original stretch independently.
<Video 1> (cut and pacing structure): fully_preserved - retain the original wide camera framing and movement, shot continuity, human action phases, timing and duration.

detailed_description:
The target video retains the photographic appearance, bright window light and camera composition of <Video 1>.
[Shot 1] Viewed from behind, the same man sits at the edge of the bed facing the window. He performs the original upward arm extension and torso stretch with the same timing. A cat sits on the visible bed space beside him. His original stretch continues while the cat remains beside him on the bedding. The white bedding, window and blinds, doorway and full-length mirror retain their original appearance and positions throughout the shot.

overall_soundscape:
No specific soundscape is requested.

non_diegetic_music:
No specific music is requested.
'''}
for sid,text in prompts.items():
 (R/'design'/f'{sid}_P1_candidate.txt').write_text(text);cp(R/'design'/f'{sid}_P1_candidate.txt',R/'configs/prompts'/f'{sid}.txt')
proposal=dict(schema='r102-basic-task-repair-proposal-v1',source_order=[x[0] for x in SPECS],status='CPU_PREPARED_ROOT_LAUNCH_PENDING',items=[dict(source_id=x['pair_id'],official_task=x['official_task'],source_sha256=x['source']['sha256'],prompt_sha256=sha(R/'configs/prompts'/(x['pair_id']+'.txt')),scope='complete official short source',prompt_origin='H3 official six-section local editing structure; original edit text and visible source facts') for x in rows],selection_scope='development repair of three known basic editing failures',no_innovation_claim=True,caption_adaptation={'short_0126':'Official target caption anthropomorphizes a stretching cat; original edit only asks to add a cat. Official caption retained verbatim in metadata. P1 preserves actual seated man stretch and adds a sitting cat; no new interaction is instructed.'})
put(R/'design/PROPOSAL.json',proposal);put(R/'design/INPUT_PLAN.json',dict(schema='r102-task-repair-input-plan-v1',pairs=rows,source_order=[x[0] for x in SPECS]));put(R/'design/EXECUTION_INPUT_PLAN.json',dict(schema='r102-execution-input-plan-v1',pairs=rows))
put(R/'configs/source_selection/SELECTED_3_MANIFEST.json',dict(schema='r102-task-repair-selection-v1',pairs=rows,scope='Three existing basic editing failures selected for repair; development subset',source_selection_before_current_generation=True,previous_failed_outcomes_retained=True))
origin=read(B/'configs/source_selection/SELECTED_4_MANIFEST.json')
put(R/'configs/source_selection/OFFICIAL_SOURCE_ORIGIN.json',dict(repository_commit=origin['official_repository_commit'],dataset_revision=origin['official_dataset_revision'],original_contracts={str(old/'configs/scientific_contract.json'):sha(old/'configs/scientific_contract.json') for old in (A,B)},sources=[dict(source_id=x['pair_id'],original_task=x['official_task'],original_source_sha256=x['source']['sha256'],input_parent=x['input_parent']) for x in rows]))
put(R/'configs/source_selection_hashes.json',{p.name:sha(p) for p in (R/'configs/source_selection').iterdir()});put(R/'PREPARED_INPUTS_MANIFEST.json',dict(schema='r102-byte-reused-inputs-v1',input_plan_sha256=sha(R/'design/INPUT_PLAN.json'),pairs=prepared));put(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()})
# Pure administrative/source-contract adaptations. Numeric files retain the parent's exact bytes.
f=R/'scripts/r102_contract.py';t=f.read_text().replace('Two source-selected P1 tasks','Three source-selected P1 tasks').replace("SOURCES=('short_0263', 'short_0092')","SOURCES=('short_0263', 'short_0092', 'short_0126')").replace("SOURCE_LENGTHS={'short_0263': (107, 105), 'short_0092': (73, 57)}","SOURCE_LENGTHS={'short_0263': (90, 74), 'short_0092': (73, 58), 'short_0126': (124, 109)}").replace("len(s['cases'])==4","len(s['cases'])==6").replace('fixed two paired','fixed three paired').replace('SELECTED_2_MANIFEST','SELECTED_3_MANIFEST');f.write_text(t)
f=R/'scripts/input_contract.py';t=f.read_text();start=t.index('SOURCES=');stop=t.index('\ndef sha',start);t=t[:start]+"SOURCES=('short_0263','short_0092','short_0126')\nLENGTHS=((90,74),(73,58),(124,109))\n"+t[stop:];f.write_text(t.replace('five selected source clips','three complete official short sources'))
f=R/'scripts/preflight.py';f.write_text(f.read_text().replace("'sources':2","'sources':3"))
f=R/'scripts/verify_input_timeline.py';f.write_text(f.read_text().replace('IVEBench source clip exploration','IVEBench complete short source task repair'))
# Inputs are inherited immutable assets; this package exposes only validation, never a stale source regeneration recipe.
(R/'scripts/prepare_inputs.py').write_text('"""R102 reuses original prepared MP4/provenance bytes; validate existing inputs."""\nfrom verify_input_timeline import main\nif __name__=="__main__":main()\n')
r=read(P/'configs/runtime.json');r.update(remote_root=REMOTE,port=8566,profile='host9_gpu0_r102_normal_reserve8',profile_scope='Three task repairs; fresh Native first, root basic-task acceptance before guide; first guided pair review.40GiB normal/reserve8 admission.');put(R/'configs/runtime.json',r);put(R/'configs/admission.json',dict(ready_for_launch=False,scope='own_user_video_jobs',permitted_compute_processes=[],existing_comfy_port=None))
s=read(P/'configs/scientific_contract.json');s.update(schema='r102-native-first-task-repair-v1',source_ids=[x[0] for x in SPECS],case_order=[],cases=[],purpose='Repair three failed basic edits with structured P1. Each actual Native requires root basic-task acceptance before any fixed guidance.',input_plan_sha256=sha(R/'design/EXECUTION_INPUT_PLAN.json'),root_input_plan_sha256=sha(R/'design/INPUT_PLAN.json'),root_proposal_sha256=sha(R/'design/PROPOSAL.json'),prepared_input_manifest_sha256=sha(R/'PREPARED_INPUTS_MANIFEST.json'),source_selection_sha256=sha(R/'configs/source_selection/SELECTED_3_MANIFEST.json'),prompt_sha256={x[0]:sha(R/'configs/prompts'/(x[0]+'.txt')) for x in SPECS})
s['screening'].update(schema='r102-native-screen-policy-v1',fixed_source_denominator=3,basic_task_acceptance_required_for_guide=True)
s['evaluation'].update(official='Selected complete official short sources for development task repair; not a full benchmark result.',fixed_case_denominator=3,adaptation='Original frame/PTS map retained; all padding excluded. Basic edits assessed before guided submission.',visibility_policy='0263 girl in chair reading;0092 remove plants and retain woman gestures;0126 addcat and retain seated stretch. Failed tasks remain Native-only.')
s['acceleration_axes']['cache']='Each source uses fresh .9 Native/forced shared actual conditions and raw AV noise; three independent caches.';s['acceleration_axes']['postprocessing']='R69/R64 original prepared files reused byte-exact; total/valid90/74,73/58,124/109; crop16,8,1280,720@24; no speed change.'
for row in rows:
 sid=row['pair_id'];pr=next(x for x in prepared if x['pair_id']==sid)
 for arm in ('native','forced'):
  run=f'r102_{sid}_seed2026101701_{arm}';s['case_order'].append(run);s['cases'].append(dict(run_id=run,source_id=sid,arm=arm,seed=2026101701,prompt_version='P1-local-v1',prompt=prompts[sid],prompt_sha256=s['prompt_sha256'][sid],parent_graph='configs/parent_graphs/r63_template_native.json',parent_graph_sha256=sha(R/'configs/parent_graphs/r63_template_native.json'),video=sid+'_video.mp4',provenance=sid+'_provenance.json',video_sha256=pr['files']['video']['sha256'],provenance_sha256=pr['files']['provenance']['sha256'],geometry=dict(width=1312,height=736,frames=pr['h3_frames'],fps=24),valid_frame_count=pr['valid_frames'],reference_video_count=1,reference_image_count=0,original_task=row['official_task'],evaluation_crop_xywh=[16,8,1280,720],clip=row['clip'],evaluation_scope='complete official short source subset; development basic task repair'))
(R/'design/NEXT_EVALUATION_RULES.txt').write_text('逐条检查原任务：0263年轻女孩须坐在原蓝色斜躺椅中持书阅读，0092室内可见植物须移除且女人/摄像机/原手势保留，0126猫须在原床上男人旁且背向镜头坐姿上伸保留。root完整有效帧审阅基础编辑成功才选择guide；基础编辑失败记录具体原因并skip。原指令与旧失败均留存。首个实际guided配对后再次审阅。当前是旧任务修复和已有固定时序引导对照，不声明新方法。\n')
s['evaluation']['rules_sha256']=sha(R/'design/NEXT_EVALUATION_RULES.txt');put(R/'configs/scientific_contract.json',s);put(R/'configs/queue.json',dict(jobs=s['case_order'],finalize=True))
import sys;sys.path.insert(0,str(R/'scripts'));import r102_contract as co
for case in s['cases']:put(R/'configs/graphs'/(case['run_id']+'.json'),co.expected_graph(R,case))
k=read(P/'configs/runtime_kernel_hashes.json')
for rel,v in k.items():v.update(parent_file=str(P/rel),parent_sha256=sha(P/rel),current_sha256=sha(R/rel),byte_equal=sha(P/rel)==sha(R/rel));assert v['byte_equal']
put(R/'configs/runtime_kernel_hashes.json',k)
budget=read(P/'configs/storage_policy.json');frames=sum(2*x[2] for x in SPECS);gib=1.7*frames/180;budget.update(schema='r102-storage-budget-v1',registered_frames_total=frames,expected_total_frames=frames,expected_new_runs=6,estimated_output_gib=gib,estimated_output_bytes=int(gib*2**30));put(R/'configs/storage_policy.json',budget)
put(R/'audit/INHERITED_BYTE_BINDINGS.json',dict(parent_r100_seal_sha256=sha(P/'deploy_manifest.json'),six_numerical_files=k,inputs=read(R/'configs/input_hashes.json'),original_input_parents={sid:str(old) for sid,old,_,_ in SPECS}))
diff=read(P/'audit/SCIENTIFIC_DIFF.json');diff.update(created_unix=time.time(),purpose='三条基础编辑修复；先验收普通编辑，再由root选择固定时序引导',source_changes={row['pair_id']:dict(input_parent=row['input_parent'],original_and_prepared_bytes_exact=True,total_frames=row['input_protocol']['h3_frame_count'],valid_frames=row['input_protocol']['effective_frame_count'],original_fps=row['source']['fps_rational'],source_scope=row['clip']['scope'],P1_change='New full six-section instruction bundle grounded in actual source; official edit verbatim') for row in rows},routing_boundary={sid:co.routing_layout({'source_id':sid}) for sid,_,_,_ in SPECS},numerical_bytes=k)
diff['administration'].update(parent='R100 Native-first/root basic-task review/guide-or-skip/first-guided-review',port=8566,GPU_launch='root only after R100 exact release and current own-peer/resource validation')
diff['interpretation']='New .9 task-repair executions retain original .41 input assets and seed, but runtime/prompt both differ from historical failures. Historical comparison cannot isolate prompt causality; matched new Native/forced uses one runtime.'
put(R/'audit/SCIENTIFIC_DIFF.json',diff)
cp(P/'audit/seal_package.py',R/'audit/seal_package.py');f=R/'audit/seal_package.py';f.write_text(f.read_text().replace('r100','r102'))
print(json.dumps({'root':str(R),'runs':co.registry()[1],'frames':[(x[0],x[2],x[3]) for x in SPECS],'input_bytes':sum(p.stat().st_size for p in (R/'inputs').iterdir())},indent=2))
