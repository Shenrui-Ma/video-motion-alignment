from pathlib import Path
from fractions import Fraction
import json,hashlib,shutil,subprocess,copy,sys
R=Path(__file__).resolve().parents[1];P=R.parent/'h3-timing-ivebench-subject-host9-r87-20261018';SRC=R.parent/'h3-timing-architecture-r2-20261016/audit/ive_action_candidate_expansion_20261018'
SOURCES=['long_0047','long_0123','long_0167','long_0173','long_0174'];WINDOWS=[(0,119),(45,224),(9,158),(105,248),(9,152)]
REMOTE='/data5/researcher/h3_runs/timing_ive_action_clips_r88_20261018'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def cp(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
assert not (R/'deploy_manifest.json').exists()
oldseal=read(P/'deploy_manifest.json');assert all(sha(P/p)==v['sha256'] for p,v in oldseal['files'].items())
protected=read(P/'configs/runtime_kernel_hashes.json')
for folder in ['scripts','extensions','tests','configs/parent_graphs','source_snapshot/r71','source_snapshot/r64','source_snapshot/http_original']:
 for p in (P/folder).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:cp(p,R/p.relative_to(P))
for p in (P/'analysis/postrun').glob('*.py'):cp(p,R/'analysis/postrun'/p.name)
cp(P/'source_snapshot/nodes_minimax_h3.py',R/'source_snapshot/nodes_minimax_h3.py')
for folder in ['scripts','extensions','tests','analysis/postrun']:
 for p in (R/folder).rglob('*.py'):
  if str(p.relative_to(R)) not in protected:p.write_text(p.read_text().replace('r87','r88').replace('R87','R88'))
(R/'scripts/r87_contract.py').rename(R/'scripts/r88_contract.py')
for n in ['parent_core_hashes.json','expected_checkpoint_hashes.json']:cp(P/'configs'/n,R/'configs'/n)
for n in ['OFFICIAL_REF_EN.txt','NEXT_EVALUATION_RULES.txt','P1_TEMPLATE.txt','P1_TEMPLATE_DRAFT.txt']:cp(P/'design'/n,R/'design'/n)
# A source animation remains animation. All remaining template text is the inherited P1 protocol.
for n in ['P1_TEMPLATE.txt','P1_TEMPLATE_DRAFT.txt']:
 p=R/'design'/n;p.write_text(p.read_text().replace('retains the photographic appearance, lighting and camera composition','retains the original visual style, lighting and camera composition'))
cp(SRC/'CANDIDATE_REVIEW.json',R/'configs/source_selection/SOURCE_REVIEW.json');cp(SRC/'ORIGIN_CROSSCHECK.json',R/'configs/source_selection/ORIGIN_CROSSCHECK.json')
review=read(SRC/'CANDIDATE_REVIEW.json');byid={x['source_id']:x for x in review['all_reviewed_rows']};pairs=[]
for sid,(a,b) in zip(SOURCES,WINDOWS):
 x=byid[sid];path=Path(x['source']['path']);assert sha(path)==x['source']['official_lfs']['oid']
 m=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,time_base:frame=best_effort_timestamp','-of','json',str(path)]));st=m['streams'][0];pts=[Fraction(z['best_effort_timestamp'])*Fraction(st['time_base']) for z in m['frames']];delta=pts[b]-pts[a];valid=-(-delta.numerator*24//delta.denominator)+1;total=5+17*max(0,-(-(valid-5)//17));subset=pts[a:b+1];mapping=[min(range(a,b+1),key=lambda k:(abs(pts[k]-(pts[a]+Fraction(i,24))),k)) for i in range(valid)];assert mapping[0]==a and mapping[-1]==b
 end_exclusive=pts[b+1] if b+1<len(pts) else pts[b]+(pts[b]-pts[b-1])
 task={k:v for k,v in x['official_task'].items() if k!='origin_mapping'}
 source={'file':str(path),'sha256':sha(path),'frame_count':len(pts),'fps_rational':st['avg_frame_rate'],'time_base':st['time_base'],'actual_pts_rational':[str(z) for z in pts],'actual_pts_s':[float(z) for z in pts],'width':st['width'],'height':st['height'],'official_lfs':x['source']['official_lfs'],'official_url':x['source']['url'],'origin_mapping':x['official_task']['origin_mapping']}
 clip={'start_frame':a,'end_frame_inclusive':b,'start_pts_rational':str(pts[a]),'end_pts_rational_inclusive':str(pts[b]),'end_exclusive_rational':str(end_exclusive),'relative_pts_rational':[str(z-pts[a]) for z in subset],'root_approved_source_only':True}
 ip={'width':1312,'height':736,'fps':24,'effective_frame_count':valid,'h3_frame_count':total,'input_to_original_frame':mapping+[b]*(total-valid),'padding':'last-frame hold to17k+5; excluded from evaluation','temporal_resample':'nearest original rational PTS within frozen clip bounds to clip_start+i/24; ties earlier; valid ceil((last-first)*24)+1','crop_xywh':[16,8,1280,720]}
 pairs.append({'source_id':sid,'official_task':task,'source':source,'clip':clip,'input_protocol':ip,'generated_h3_results_consulted':0,'source_review':x['review'],'benchmark_scope':'IVEBench source-clip exploration; not a full-official-clip benchmark score'})
sel={'schema':'r88-source-selected-five-clips-v1','official_revision':review['official_revision'],'selected_order':SOURCES,'selection_before_generation':True,'source_review_sha256':sha(SRC/'CANDIDATE_REVIEW.json'),'pairs':pairs};put(R/'configs/source_selection/SELECTED_5_MANIFEST.json',sel)
plan={'schema':'r88-rational-clip-input-plan-v1','source_selection_sha256':sha(R/'configs/source_selection/SELECTED_5_MANIFEST.json'),'selection_before_generation':True,'generated_h3_results_consulted':0,'selected_order':SOURCES,'pairs':[dict(pair_id=x['source_id'],**x['official_task'],source=x['source'],clip=x['clip'],input_protocol=x['input_protocol']) for x in pairs]};put(R/'design/INPUT_PLAN.json',plan)
# Exact scientific numerical inheritance and actual host profile.
put(R/'configs/runtime_kernel_hashes.json',{p:{'parent_file':str(P/p),'parent_sha256':sha(P/p),'current_sha256':sha(R/p),'byte_equal':sha(P/p)==sha(R/p)} for p in protected})
runtime=read(P/'configs/runtime.json');runtime.update(remote_root=REMOTE,port=8553,profile='host9_gpu0_r88_normal_reserve8',profile_scope='Five source-selected IVEBench action clips; ten fresh host9 Native/fixed runs. Same R87 math;40GiB main startup gate,normal reserve8. Actual capacity107/158frames pending for this prompt set; no automatic numerical fallback.')
put(R/'configs/runtime.json',runtime);put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[],'note':'Root fresh exact peer/resource admission; at most2 own GPUcards. Local preparation only; passive deployment pending root instruction.'})
cp(P/'audit/root_run_batch.py',R/'audit/root_run_batch.py');p=R/'audit/root_run_batch.py';p.write_text(p.read_text().replace('r87','r88').replace('R87','R88').replace('short_0131','long_0047'))
lengths={x['source_id']:(x['input_protocol']['h3_frame_count'],x['input_protocol']['effective_frame_count']) for x in pairs}
p=R/'scripts/r88_contract.py';t=p.read_text();t=t.replace("SOURCES=('short_0131', 'short_0268', 'short_0343', 'short_0274', 'short_0085', 'short_0358', 'short_0178')",'SOURCES='+repr(tuple(SOURCES)));t=t.replace("SOURCE_LENGTHS={'short_0131': (56, 43), 'short_0268': (107, 97), 'short_0343': (73, 61), 'short_0274': (73, 72), 'short_0085': (73, 66), 'short_0358': (107, 105), 'short_0178': (124, 121)}",'SOURCE_LENGTHS='+repr(lengths));t=t.replace("len(s['cases'])==14","len(s['cases'])==10").replace('SELECTED_7_MANIFEST','SELECTED_5_MANIFEST').replace('seven','five').replace('Seven','Five');p.write_text(t)
p=R/'scripts/input_contract.py';t=p.read_text();start=t.index('SOURCES=');end=t.index('\ndef sha',start);t=t[:start]+'SOURCES='+repr(tuple(SOURCES))+'\nLENGTHS='+repr(tuple(lengths.values()))+'\n'+t[end:];t=t.replace('seven selected full official clips','five selected source clips');p.write_text(t)
p=R/'scripts/execution_gate.py';p.write_text(p.read_text().replace('short_0131','long_0047'))
p=R/'scripts/preflight.py';p.write_text(p.read_text().replace("'sources':7","'sources':5"))
p=R/'scripts/prepare_inputs.py';t=p.read_text().replace('9555b254019a7156828f67a04c252d7c0baa31bf1cececdde5fbfe0ec885dc9e',sha(R/'design/INPUT_PLAN.json')).replace("['all', 'short_0131', 'short_0268', 'short_0343', 'short_0274', 'short_0085', 'short_0358', 'short_0178']",repr(['all']+SOURCES)).replace("['short_0131', 'short_0268', 'short_0343', 'short_0274', 'short_0085', 'short_0358', 'short_0178']",repr(SOURCES));t=t.replace('five source-selected full official inputs','five source-selected official clips').replace("original_pts=row['source']['actual_pts_s'],input_to_original_frame=mapping,","original_pts=row['source']['actual_pts_s'],original_pts_rational=row['source']['actual_pts_rational'],clip=row['clip'],input_to_original_frame=mapping,");p.write_text(t)
for folder in ['inputs','configs/graphs','configs/prompts','processes','logs','input','output','temp','user','custom_nodes']:(R/folder).mkdir(parents=True,exist_ok=True)
put(R/'audit/INITIAL_PREPARATION.json',{'parent_root':str(P),'parent_seal_sha256':sha(P/'deploy_manifest.json'),'source_review':str(SRC),'sources':SOURCES,'lengths':lengths,'local_only':True,'GPU_started':False,'passive_deployed':False,'protected_numeric_files':list(protected)})
print(json.dumps(lengths))
