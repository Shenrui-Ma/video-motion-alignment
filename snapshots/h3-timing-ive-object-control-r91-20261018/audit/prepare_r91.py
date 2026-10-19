from pathlib import Path
from fractions import Fraction
import json,hashlib,shutil,subprocess,re
R=Path(__file__).resolve().parents[1];P=R.parent/'h3-timing-ive-action-clips-r88-20261018';REMOTE='/data5/researcher/h3_runs/timing_ive_object_control_r91_20261018'
SOURCES=('short_0114','long_0039');LENGTHS={'short_0114':(107,105),'long_0039':(158,144)}
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def cp(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
assert not(R/'deploy_manifest.json').exists()
proposal=read(R/'design/PROPOSAL.json');plan=read(R/'design/INPUT_PLAN.json');assert tuple(x['source_id'] for x in proposal['items'])==SOURCES
initial={str(p.relative_to(R)):sha(p) for p in R.glob('design/*') if p.is_file()};initial['README.txt']=sha(R/'README.txt');put(R/'audit/ROOT_DESIGN_BINDINGS.json',initial)
for name in initial:cp(R/name,R/'audit/root_design_original'/name)
protected=read(P/'configs/runtime_kernel_hashes.json');seal=read(P/'deploy_manifest.json');assert all(sha(P/p)==v['sha256'] for p,v in seal['files'].items())
for folder in ('scripts','extensions','source_snapshot'):
 shutil.copytree(P/folder,R/folder,ignore=shutil.ignore_patterns('__pycache__'))
for p in (P/'analysis/postrun').glob('*.py'):cp(p,R/'analysis/postrun'/p.name)
for n in ('parent_core_hashes.json','expected_checkpoint_hashes.json'):cp(P/'configs'/n,R/'configs'/n)
cp(P/'configs/graphs/r88_long_0047_seed2026101701_native.json',R/'configs/parent_graphs/r88_native_template.json')
for n in ('OFFICIAL_REF_EN.txt','NEXT_EVALUATION_RULES.txt'):cp(P/'design'/n,R/'design'/n)
for n in ('test_cuda_release.py','test_spawn_identity.py','test_watchdog_timers.py','test_http_wait.py','test_resource_peers.py','test_admission_resample.py','test_attempt_cleanup.py','test_native_generation.py','test_first_pair.py','test_pair_verifier.py'):
 cp(P/'tests'/n,R/'tests'/n)
cp(P/'audit/root_run_batch.py',R/'audit/root_run_batch.py')
for folder in ('scripts','extensions','tests','analysis/postrun'):
 for p in (R/folder).rglob('*.py'):
  if str(p.relative_to(R)) not in protected:p.write_text(p.read_text().replace('r88','r91').replace('R88','R91').replace('long_0047','short_0114'))
p=R/'audit/root_run_batch.py';p.write_text(p.read_text().replace('r88','r91').replace('R88','R91').replace('long_0047','short_0114').replace('five-pair','two-pair'))
(R/'scripts/r88_contract.py').rename(R/'scripts/r91_contract.py')
# Archived HTTP failure fixture remains only a regression input; adjust its imported registry name.
p=R/'source_snapshot/http_original/run_queue.py';p.write_text(p.read_text().replace('r87_contract','r91_contract').replace('r88_contract','r91_contract'))
rows=[]
for item,planned in zip(proposal['items'],plan['cases']):
 sid=item['source_id'];source=Path(item['source_path']);assert sha(source)==item['source_sha256']==planned['source_sha256']
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,time_base,start_pts,duration_ts:frame=best_effort_timestamp','-of','json',str(source)]));st=probe['streams'][0];pts=[Fraction(x['best_effort_timestamp'])*Fraction(st['time_base']) for x in probe['frames']]
 assert [str(x) for x in pts]==planned['original_pts_rational'];a,e=planned['clip_original_frame_interval_half_open'];b=e-1
 end=pts[e] if e<len(pts) else Fraction(st['start_pts']+st['duration_ts'])*Fraction(st['time_base']);start=pts[a];valid=-(-((end-start)*24).numerator//((end-start)*24).denominator);total=5+17*max(0,-(-(valid-5)//17))
 mapping=[min(range(a,e),key=lambda k:(abs(pts[k]-(start+Fraction(i,24))),k)) for i in range(valid)]+[b]*(total-valid)
 assert (total,valid)==LENGTHS[sid] and mapping==planned['input_to_original_frame'];assert [str(start),str(end)]==planned['physical_clip_interval_half_open']
 clip=dict(start_frame=a,end_frame_inclusive=b,original_frame_interval_half_open=[a,e],start_pts_rational=str(start),end_pts_rational_inclusive=str(pts[b]),end_exclusive_rational=str(end),relative_pts_rational=[str(x-start) for x in pts[a:e]],root_approved_source_only=True)
 src=dict(file=str(source),sha256=sha(source),frame_count=len(pts),fps_rational=st['avg_frame_rate'],time_base=st['time_base'],actual_pts_rational=[str(x) for x in pts],actual_pts_s=[float(x) for x in pts],width=st['width'],height=st['height'],official_url='https://huggingface.co/datasets/IVE-Bench/IVEBench/resolve/1e6cb655c0a537f6093edcf18e2607fb03e76734/videos/'+sid+'.mp4',official_lfs={'oid':sha(source),'status':'original frozen official source SHA inherited; URL provenance separately retained'})
 # Do not infer an unobserved dataset repository path; existing source package carries original provenance.
 src.pop('official_url')
 ip=dict(width=1312,height=736,fps=24,effective_frame_count=valid,h3_frame_count=total,input_to_original_frame=mapping,padding='last-frame hold to17k+5; excluded from evaluation',temporal_resample='nearest original rational PTS within half-open clip to clip_start+i/24; ties earlier; valid ceil(duration*24)',crop_xywh=[16,8,1280,720])
 rows.append(dict(source_id=sid,pair_id=sid,official_task=item['official_task'],source=src,clip=clip,input_protocol=ip,benchmark_scope=item['scope'],source_review=proposal['root_source_review'],**item['official_task']))
 cp(Path(item['prompt_file']),R/'configs/prompts'/(sid+'.txt'));assert sha(R/'configs/prompts'/(sid+'.txt'))==item['prompt_sha256']
put(R/'design/EXECUTION_INPUT_PLAN.json',dict(schema='r91-rational-input-plan-v1',root_plan_sha256=sha(R/'design/INPUT_PLAN.json'),root_proposal_sha256=sha(R/'design/PROPOSAL.json'),selected_order=list(SOURCES),pairs=rows))
put(R/'configs/source_selection/SELECTED_2_MANIFEST.json',dict(schema='r91-two-object-control-selection-v1',pairs=rows,original_design_sha256=initial,source_selection_before_current_generation=True,scope='short0114 full official clip; long0039 source-selected six-second exploration'))
put(R/'configs/runtime_kernel_hashes.json',{p:{'parent_file':str(P/p),'parent_sha256':sha(P/p),'current_sha256':sha(R/p),'byte_equal':sha(P/p)==sha(R/p)} for p in protected})
runtime=read(P/'configs/runtime.json');runtime.update(remote_root=REMOTE,gpu_uuid='GPU-REDACTED',port=8556,expected_gpu_index=3,profile='host9_gpu3_r91_normal_reserve8',profile_scope='Two object-edit P1 tasks with107/158frame shapes; fresh Native/forced same-host pairs. normal/reserve8 free40GiB, exact peers max2owncards. Actual P1 capacities pending; no automatic numerical fallback.');put(R/'configs/runtime.json',runtime)
put(R/'configs/admission.json',dict(ready_for_launch=False,scope='own_user_video_jobs',existing_comfy_port=None,permitted_compute_processes=[]))
p=R/'scripts/input_contract.py';s=p.read_text();a=s.index('SOURCES=');b=s.index('\ndef sha',a);s=s[:a]+f'SOURCES={SOURCES!r}\nLENGTHS={tuple(LENGTHS.values())!r}\n'+s[b:];p.write_text(s)
p=R/'scripts/r91_contract.py';s=p.read_text();s=re.sub(r'^SOURCES=.*$',f'SOURCES={SOURCES!r}',s,flags=re.M);s=re.sub(r'^SOURCE_LENGTHS=.*$',f'SOURCE_LENGTHS={LENGTHS!r}',s,flags=re.M);s=s.replace("len(s['cases'])==10","len(s['cases'])==4").replace('SELECTED_5_MANIFEST','SELECTED_2_MANIFEST').replace('fixed five','fixed two');p.write_text(s)
p=R/'scripts/prepare_inputs.py';s=p.read_text().replace("ROOT/'design/INPUT_PLAN.json'","ROOT/'design/EXECUTION_INPUT_PLAN.json'");s=re.sub(r"SELECTION_SHA = '[a-f0-9]+'","SELECTION_SHA = '"+sha(R/'design/EXECUTION_INPUT_PLAN.json')+"'",s);s=s.replace("['all', 'short_0114', 'long_0123', 'long_0167', 'long_0173', 'long_0174']",repr(['all']+list(SOURCES))).replace("['short_0114', 'long_0123', 'long_0167', 'long_0173', 'long_0174']",repr(list(SOURCES)));p.write_text(s)
p=R/'scripts/verify_input_timeline.py';p.write_text(p.read_text().replace("ROOT/'design/INPUT_PLAN.json'","ROOT/'design/EXECUTION_INPUT_PLAN.json'"))
p=R/'scripts/preflight.py';p.write_text(p.read_text().replace("'sources':5","'sources':2"))
for name in ('inputs','input','output','temp','user','logs','processes','custom_nodes','configs/graphs'):(R/name).mkdir(parents=True,exist_ok=True)
print({s:LENGTHS[s] for s in SOURCES})
