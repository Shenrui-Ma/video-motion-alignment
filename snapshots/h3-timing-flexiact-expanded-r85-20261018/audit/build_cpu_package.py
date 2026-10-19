"""Build a dormant, fixed two-pair R85 package from existing reviewed components."""
from pathlib import Path
import copy, hashlib, json, math, shutil, sys
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent
P=BASE/'h3-timing-flexiact-official-six-r74-20261018'
A=BASE/'h3-timing-subject-edits-r83-20261018'
V=BASE/'h3-timing-flexiact-forced-r84-20261018/audit/watchdog_recovery_v2'
HOST=BASE/'h3-timing-local-edit-repair-r80-20261018'
REMOTE='/data5/researcher/h3_runs/timing_flexiact_expanded_r85_20261018'
PAIRS=('crouch__movie_man_5','rotate__game_girl_1')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def copyfile(src,dst):dst=Path(dst);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
assert not (ROOT/'deploy_manifest.json').exists()
protected=set(read(P/'configs/runtime_kernel_hashes.json'))
for folder in ('scripts','extensions','source_snapshot','tests','configs/parent_graphs','configs/R49_evidence'):
 for src in (P/folder).rglob('*'):
  if src.is_file() and '__pycache__' not in src.parts:copyfile(src,ROOT/src.relative_to(P))
for name in ('verify_pair.py','capture_checks.py'):copyfile(P/'analysis/postrun'/name,ROOT/'analysis/postrun'/name)
for folder in ('scripts','extensions','tests','analysis/postrun'):
 for path in (ROOT/folder).rglob('*.py'):
  if str(path.relative_to(ROOT)) not in protected:path.write_text(path.read_text().replace('r74','r85').replace('R74','R85'))
(ROOT/'scripts/r74_contract.py').rename(ROOT/'scripts/r85_contract.py')
# Reviewed lifecycle implementations; numerical modules stay byte-exact R74/R66.
for name in ('service.py','launch_remote.py','service_entry.py','supervise_service.py',
             'process_identity.py','start_controller.py','run_queue.py','job.py','resource_gate.py'):
 text=(A/'scripts'/name).read_text().replace('r83','r85').replace('R83','R85').replace('h3-timing-subject-edits-r85','h3-timing-flexiact-expanded-r85')
 (ROOT/'scripts'/name).write_text(text)
text=(V/'watchdog_v2.py').read_text().replace('r84_contract','r85_contract')
text=text.replace('ROOT=Path(__file__).resolve().parents[2]','ROOT=Path(__file__).resolve().parents[1]').replace('HERE=Path(__file__).resolve().parent',"HERE=ROOT/'audit/watchdog_runtime_v2'")
(ROOT/'scripts/lease_watchdog.py').write_text(text)
p=ROOT/'scripts/launch_remote.py';text=p.read_text();old="watchdog_command=['python3','-u',str(r/'scripts/lease_watchdog.py')]";new="watchdog_command=['python3','-u',str(r/'scripts/lease_watchdog.py'),'--expected-pid',str(owner['pid']),'--expected-start-ticks',str(owner['identity']['start_ticks'])]";assert old in text;text=text.replace(old,new);p.write_text(text)
text=(A/'audit/root_run_batch.py').read_text().replace('r83','r85').replace('R83','R85').replace("'30720'","'40960'").replace('seven pairs','two pairs').replace('seven-pair','two-pair').replace("completed,57600,","completed,43200,")
(ROOT/'audit/root_run_batch.py').write_text(text)
# Pinned benchmark and official H3 prompt guide.
selection=BASE/'h3-timing-architecture-r2-20261016/audit/flexiact_next_pairs_20261018/CANDIDATES.json'
copyfile(selection,ROOT/'design/CANDIDATES.json')
for name in ('P1_TEMPLATE.txt','official_ref-en.txt','actual_nodes_minimax_h3.py'):copyfile(P/'design'/name,ROOT/'design'/name)
for motion in ('crouch','rotate'):
 for suffix in ('crop.csv','val_image.csv'):
  name=f'flexiact_hf__benchmark__captions__human__{motion}__{suffix}'
  copyfile(P/'design/official_metadata'/name,ROOT/'design/official_metadata'/name)
candidates={x['pair_key']:x for x in read(selection)['candidates']}
chosen={'schema':'r85-two-prespecified-official-pairs-v1','candidates_sha256':sha(selection),'pairs':[{'source':candidates[k]['source_id'],'target':candidates[k]['target'],'pair_key':k} for k in PAIRS],'decision':'Root selected both before R85 generation; fresh same-host P1 Native/forced; retain every outcome.'}
put(ROOT/'design/SELECTED_PAIRS.json',chosen)
old_defs=read(P/'design/PAIR_DEFINITIONS.json')['pairs'];defs=[]
for key in PAIRS:
 c=candidates[key];motion=c['source_id']
 donor=next(x for x in old_defs if x['pair_key']==key) if key==PAIRS[0] else next(x for x in old_defs if x['pair_key']=='rotate__game_man_4')
 d=copy.deepcopy(donor)
 for name in d['source'].values():
  if isinstance(name,str) and (P/'inputs'/name).exists():copyfile(P/'inputs'/name,ROOT/'inputs'/name)
 target=Path(c['target']);assert sha(target)==c['target_sha256'];portrait='target_'+target.name;copyfile(target,ROOT/'inputs'/portrait)
 d.update(pair_key=key,candidate_id=key,original_pair_id=key,identity='benchmark/target_images/human/'+target.name,portrait=portrait,portrait_sha256=sha(target),official_csv_row_zero_based=c['official_row_zero_based'],official_target_caption=c['official_target_caption'],target_pair_previously_generated_at_selection=(key==PAIRS[1]))
 if key==PAIRS[1]:
  d['target_asset']={'path':str(target),'sha256':sha(target),'bytes':target.stat().st_size,'dataset_path':d['identity'],'dataset_revision':read(selection)['official_revision'],'pinned_url':'https://huggingface.co/datasets/shiyi0408/FlexiAct/resolve/'+read(selection)['official_revision']+'/'+d['identity']}
  d['p1_fields']['target_identity']='the woman with short dark hair wearing dark metallic armor'
  d['original_metadata_flag']=None;d['caption_review']=['Original target caption describes upper-body rotation. The portrait shows only the upper body; full-body appearance is generated. Prior R49 uses a different P0 prompt and is historical context only.']
  with Image.open(target) as image:w,h=image.size
  scale=min(1.,math.sqrt(1152*768/(w*h)));tw=max(32,round(w*scale/32)*32);th=max(32,round(h*scale/32)*32)
  d['reference_image_expected']={'original_width_height':[w,h],'expected_native_ref_image_size_match_width_height':[tw,th],'expected_clean_reference_latent_shape':[1,24,1,th//16,tw//16],'expected_DiT_visual_patch_tokens':th//32*(tw//32),'formula':'native nodes_minimax_h3.py:301-311; scale=min(1,sqrt(1152*768/(w*h))), axes rounded32; original portrait bytes'}
 d['prompt_file']='configs/prompts/'+key+'.txt';d['prompt']=(ROOT/'design/P1_TEMPLATE.txt').read_text().format(**d['p1_fields'])
 path=ROOT/d['prompt_file'];path.parent.mkdir(parents=True,exist_ok=True);path.write_text(d['prompt']);d['prompt_sha256']=sha(path)
 assert d['source']['original_sha256']==c['source_sha256'];defs.append(d)
put(ROOT/'design/PAIR_DEFINITIONS.json',{'schema':'r85-two-official-flex-pairs-v1','selection_sha256':sha(ROOT/'design/SELECTED_PAIRS.json'),'selection_manifest':'design/SELECTED_PAIRS.json','official_revision':read(selection)['official_revision'],'prompt_policy':'R74/R72 P1 reference generation: Picture1 identity and scene, Video1 complete motion/timing. Exact same prompt within each pair.','pairs':defs})
put(ROOT/'design/EXPECTED_SHAPES.json',{d['pair_key']:d['reference_image_expected'] for d in defs})
ancestry=read(P/'configs/prompt_ancestry.json');ancestry.update(parent='R74/R72 P1; crouch prompt byte-exact R74, rotate new target descriptor',pair_definitions_sha256=sha(ROOT/'design/PAIR_DEFINITIONS.json'));put(ROOT/'configs/prompt_ancestry.json',ancestry)
runtime=read(HOST/'configs/runtime.json');runtime.update(status='CPU_PREPARED_ROOT_LAUNCH_PENDING',remote_root=REMOTE,port=8550,uid=1016,profile='host9_gpu0_r85_normal_reserve8',profile_scope='Two prespecified official Flex identity pairs, fresh P1 Native then same-service fixed route. Capacity requires actual 40GiB free at root launch; foreign coexistence allowed, own GPU cap2.')
put(ROOT/'configs/runtime.json',runtime)
put(ROOT/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[],'note':'Root resolves exact live R73 peer generation before launch/GO; permits foreign users with sufficient selected-device memory; at most two owned cards.'})
for name in ('parent_core_hashes.json','expected_checkpoint_hashes.json'):copyfile(HOST/'configs'/name,ROOT/'configs'/name)
put(ROOT/'configs/runtime_kernel_hashes.json',{k:{'parent_file':str(P/k),'parent_sha256':sha(P/k),'current_sha256':sha(ROOT/k),'byte_equal':sha(P/k)==sha(ROOT/k)} for k in protected})
cases=[];parent='configs/parent_graphs/r66_fitness_native_template.json'
for d in defs:
 for arm in ('native','forced'):
  case=copy.deepcopy(next(c for c in read(P/'configs/scientific_contract.json')['cases'] if c['motion_source_id']==d['motion_source_id'] and c['arm']==arm))
  case.update(source_id=d['pair_key'],pair_key=d['pair_key'],motion_source_id=d['motion_source_id'],original_pair_id=d['original_pair_id'],run_id='r85_'+d['pair_key']+'_seed2026101701_'+arm,identity=d['identity'],video=d['source']['video'],portrait=d['portrait'],provenance=d['source']['provenance'],prompt=d['prompt'],prompt_file=d['prompt_file'],prompt_sha256=d['prompt_sha256'],video_sha256=d['source']['video_sha256'],portrait_sha256=d['portrait_sha256'],provenance_sha256=d['source']['provenance_sha256'],reference_image_expected=d['reference_image_expected'])
  cases.append(case)
s=read(P/'configs/scientific_contract.json');s.update(schema='r85-flexiact-two-p1-fixed-route-v1',case_order=[c['run_id'] for c in cases],cases=cases,source_ids=list(PAIRS),pair_keys=list(PAIRS),motion_source_ids=['crouch','rotate'],scope_note='Two preselected official pairs; two known motion sources; fresh same-host P1 Native and fixed route, all outcomes retained.',selection_scope={'official_csv_pairs':2,'total_pairs':2,'distinct_motion_sources':2,'source_event_selection':False,'generated_output_selection':False})
put(ROOT/'configs/scientific_contract.json',s);put(ROOT/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
put(ROOT/'configs/storage_policy.json',{'schema':'r85-storage-budget-v1','prior_observation':'R74 planning estimate scaled from12 to4 jobs','registered_frames_total':632,'estimated_output_bytes':5872126655,'startup_required_free_bytes':20*1024**3,'estimate_status':'planning estimate; actual cache size varies','large_tensors':'retain remote only; download necessary videos/JSON'})
# Fixed registry changes only identity, declared pair count and task names.
p=ROOT/'scripts/r85_contract.py';text=p.read_text();start=text.index('PAIR_KEYS=');end=text.index('\n',start);text=text[:start]+"PAIR_KEYS=('crouch__movie_man_5','rotate__game_girl_1')"+text[end:];text=text.replace('FIXED_8_CANDIDATES.json','SELECTED_PAIRS.json').replace('len(s[\'cases\'])==12',"len(s['cases'])==4").replace('six','two').replace('Six','Two');p.write_text(text)
p=ROOT/'scripts/preflight.py';text=p.read_text().replace("'pairs':6,'distinct_motion_sources':3","'pairs':2,'distinct_motion_sources':2");p.write_text(text)
p=ROOT/'scripts/execution_gate.py';text=p.read_text().replace("paths.extend(root/'configs'/n", "paths.append(root/'audit/root_run_batch.py')\n paths.extend(root/'configs'/n");p.write_text(text)
sys.path.insert(0,str(ROOT/'scripts'));import r85_contract as contract
for case in cases:put(ROOT/'configs/graphs'/(case['run_id']+'.json'),contract.expected_graph(ROOT,case))
put(ROOT/'configs/input_hashes.json',{p.name:sha(p) for p in sorted((ROOT/'inputs').iterdir()) if p.is_file()})
put(ROOT/'configs/source_selection_hashes.json',{str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'design').rglob('*')) if p.is_file()})
# Adapt the existing pair-specific test expectations; mathematical and failure tests retained.
p=ROOT/'tests/test_official_six.py';text=p.read_text().replace('FIXED_8_CANDIDATES.json','SELECTED_PAIRS.json').replace('len(c.definitions()),6','len(c.definitions()),2').replace("len({p['motion_source_id'] for p in c.definitions()}),3","len({p['motion_source_id'] for p in c.definitions()}),2").replace('len(set(condition)),6','len(set(condition)),2').replace('len(set(noise)),6','len(set(noise)),2').replace("['chest','crouch','rotate']","['crouch','rotate']").replace('chest__game_man_5','crouch__movie_man_5').replace("(7,'GPU-REDACTED',8542)","(0,'GPU-REDACTED',8550)")
p.write_text(text)
for directory in ('processes','logs','input','output','temp','user','custom_nodes'):(ROOT/directory).mkdir(exist_ok=True)
put(ROOT/'audit/BUILD_RECEIPT.json',{'source_producer':str(P),'administration_source':str(A),'watchdog_source':str(V/'watchdog_v2.py'),'pairs':list(PAIRS),'scientific_kernels_unchanged':all(v['byte_equal'] for v in read(ROOT/'configs/runtime_kernel_hashes.json').values()),'GPU_started':False})
print('R85 dormant package built')
