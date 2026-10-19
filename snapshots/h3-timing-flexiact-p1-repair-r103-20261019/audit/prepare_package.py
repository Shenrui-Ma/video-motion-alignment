"""Prepare a new CPU-only Native-first Flex repair package from frozen parents."""
from pathlib import Path
import copy, hashlib, json, shutil
from PIL import Image

R=Path(__file__).resolve().parents[1];D=R.parent
P=D/'h3-timing-ive-native-screen-r96-20261018'
F=D/'h3-timing-flexiact-expanded-r85-20261018'
Q=D/'h3-flexiact-p1-repair-design-r103-20261019'
REMOTE='/data4/researcher/h3_runs/timing_flexiact_p1_repair_r103_20261019'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def cp(p,q):q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
assert not (R/'deploy_manifest.json').exists()
numeric=read(P/'configs/runtime_kernel_hashes.json')
skip_tests={'test_inputs.py','test_clip_timebase.py','test_registered_pairs.py','test_host_migration.py','test_r96_inheritance.py','test_pair_verifier.py'}
for rel in read(P/'deploy_manifest.json')['files']:
    if not (rel.startswith(('scripts/','extensions/','tests/','analysis/postrun/')) or rel=='audit/root_run_batch.py'):continue
    if rel.startswith('tests/') and Path(rel).name in skip_tests:continue
    if Path(rel).name in ('prepare_inputs.py','input_contract.py','verify_input_timeline.py'):continue
    dst=R/rel.replace('r96_contract.py','r103_contract.py');cp(P/rel,dst)
    if rel.endswith('.py') and rel not in numeric:
        dst.write_text(dst.read_text().replace('r96','r103').replace('R96','R103').replace('long_0047','human2animal_2__game_man_4').replace('long_0123','chest__game_girl_1'))
for rel in ('configs/parent_core_hashes.json','configs/expected_checkpoint_hashes.json','configs/storage_policy.json','configs/cgroup_policy.json'):
    cp(P/rel,R/rel)
for n in ('EVIDENCE.json','ACCEPTANCE.json','PREPARATION_VERIFIED.json','README.txt','R98_SUCCESSFUL_P1_REFERENCE.txt'):
    cp(Q/n,R/'design'/n)
e=read(Q/'EVIDENCE.json')
cp(Path(e['official_format']['snapshot']['file']),R/'design/OFFICIAL_REF_EN.txt')
for rel in ('deploy_manifest.json','configs/runtime.json','scripts/execution_gate.py','scripts/run_queue.py','audit/root_run_batch.py','analysis/postrun/verify_pair.py'):
    cp(P/rel,R/'source_snapshot/r96_parent'/rel)
for rel in ('deploy_manifest.json','analysis/postrun/verify_pair.py','scripts/r85_contract.py'):
    cp(F/rel,R/'source_snapshot/r85_parent'/rel)
for folder in ('inputs','input','output','temp','user','custom_nodes','processes','logs','configs/graphs','configs/prompts','configs/parent_graphs','configs/source_selection','configs/R54_evidence','audit/router','audit/x0'):
    (R/folder).mkdir(parents=True,exist_ok=True)
parent_graph=D/'h3-timing-flexiact-expanded-r66-20261018/configs/graphs/r66_human2animal_2__game_man_4_seed2026101701_native.json'
cp(parent_graph,R/'configs/parent_graphs/r66_native_template.json')
defs=[]
for item in e['items']:
    key=item['case_id'];motion='human2animal_2' if key.startswith('human') else 'chest'
    source=Path(item['source']['file']);portrait=Path(item['target_image']['file']);prov=Path(item['provenance']['file']);original=source.parent/f'source_{motion}_original.mp4'
    for p in (source,portrait,prov,original):cp(p,R/'inputs'/p.name)
    cp(Path(item['candidate_prompt']['file']),R/'configs/prompts'/(key+'.txt'))
    cp(Path(item['old_graph']['file']),R/'source_snapshot/old_tasks'/(key+'_graph.json'))
    cp(Path(item['old_contract']['file']),R/'source_snapshot/old_tasks'/(key+'_contract.json'))
    width,height=Image.open(portrait).size
    scale=min(1.,(1152*768/(width*height))**.5)
    w,h=[round(n*scale/32)*32 for n in (width,height)]
    image={'original_width_height':[width,height],'expected_native_ref_image_size_match_width_height':[w,h],'expected_clean_reference_latent_shape':[1,24,1,h//16,w//16],'expected_DiT_visual_patch_tokens':h//32*(w//32),'formula':'pinned native ref_image_size=match: min(1,sqrt(canvas_area/image_area)); each axis round32; actual inference verified by gate'}
    v=read(prov);assert v['input_to_original']==[i//3 for i in range(147)]+[48]*11
    p={'pair_key':key,'motion_source_id':motion,'original_pair_id':item.get('official_pair',{}).get('stable_id','extension/human2animal_2/game_man_4'),'group':item['original_pair_scope'],'identity':'benchmark/target_images/human/'+('game_man_4.jpg' if motion=='human2animal_2' else 'game_girl_1.webp'),'source':{'original':original.name,'original_sha256':sha(original),'video':source.name,'video_sha256':sha(source),'provenance':prov.name,'provenance_sha256':sha(prov)},'portrait':portrait.name,'portrait_sha256':sha(portrait),'reference_image_expected':image,'prompt_file':'configs/prompts/'+key+'.txt','prompt_sha256':sha(R/'configs/prompts'/(key+'.txt')),'prompt':(R/'configs/prompts'/(key+'.txt')).read_text(),'prompt_version':'P1-reference-v1','historical_failure':item['old_graph'],'source_is_new_motion_content':False}
    defs.append(p)
put(R/'design/PAIR_DEFINITIONS.json',{'schema':'r103-two-task-repair-definitions-v1','pairs':defs,'design_evidence_sha256':sha(R/'design/EVIDENCE.json'),'acceptance_sha256':sha(R/'design/ACCEPTANCE.json')})
put(R/'configs/prompt_ancestry.json',{'pair_definitions_sha256':sha(R/'design/PAIR_DEFINITIONS.json'),'official_guide_sha256':sha(R/'design/OFFICIAL_REF_EN.txt'),'proposal_parent':str(Q),'new_method_claim':False})
put(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()})
put(R/'configs/source_selection/SELECTED_2_MANIFEST.json',{'pairs':defs,'selection':'Previously failed original inputs retained; no sample replacement or held-out claim.'})
put(R/'configs/source_selection_hashes.json',{p.name:sha(p) for p in (R/'configs/source_selection').iterdir()})
put(R/'PREPARED_INPUTS_MANIFEST.json',{'pairs':[{'pair_id':p['pair_key'],'original':p['source'],'portrait':p['portrait'],'portrait_sha256':p['portrait_sha256'],'valid_frames':147,'total_frames':158,'fps':24,'evaluation_indices':list(range(0,147,3))} for p in defs]})
runtime=read(P/'configs/runtime.json');runtime.update(remote_root=REMOTE,port=8567,profile='host41_gpu2_r103_normal_reserve8',profile_scope='Two unchanged Flex source/portrait P1 repairs. Native task acceptance precedes guide; same fresh host41 service and actual conditions/noise per pair. Run only after R96 exact full release.')
put(R/'configs/runtime.json',runtime)
put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
cg=read(R/'configs/cgroup_policy.json');cg['schema']='r103-first-load-cgroup-policy-v1';put(R/'configs/cgroup_policy.json',cg)
s=read(P/'configs/scientific_contract.json');s.update(schema='r103-flex-p1-native-first-repair-v1',source_ids=[p['pair_key'] for p in defs],pair_keys=[p['pair_key'] for p in defs],motion_source_ids=[p['motion_source_id'] for p in defs],cases=[],case_order=[],geometry={'width':1152,'height':768,'frames':158,'fps':24},purpose='Repair two previously failed character transfers using the same original image and video; root accepts actual Native before known fixed guidance. No architecture claim.',condition_scope='Eight actual image/video/Qwen/position condition blobs; shared same-source cache and raw AV noise; actual prefix0..5 AV x0 exact.',input_reference_images=1,prompt_version='P1-reference-v1')
for k in ('prompt_template_sha256','input_plan_sha256','prepared_input_manifest_sha256','source_selection_sha256','prompt_fields_sha256'):s.pop(k,None)
s['prepared_input_manifest_sha256']=sha(R/'PREPARED_INPUTS_MANIFEST.json');s['pair_definitions_sha256']=sha(R/'design/PAIR_DEFINITIONS.json')
s['screening'].update(schema='r103-native-screen-policy-v1',fixed_source_denominator=2)
s['continuous'].update(max_service_seconds=43200,job_timeout_seconds=14400)
s['evaluation']=read(F/'configs/scientific_contract.json')['evaluation'];s['evaluation'].update(fixed_case_denominator=2,full_benchmark_reproduction=False,rules_sha256=sha(R/'design/ACCEPTANCE.json'),scope='One original CSV pair and one official-assets crosspair; both previously used motions.')
s['acceleration_axes'].update(cache='Independent pair caches; same pair Native/forced share exact actual8conditions and raw AV noise.',postprocessing='Original49frames@8fps triplicated to147@24 and11tailpad frames; unchanged bytes; evaluate0,3,...144. Fullvalid147frames retained.',runtime='R96 exact .41 core/dependencies/model profile and six byte-identical numerical modules; both arms fresh in R103.')
for p in defs:
    for arm in ('native','forced'):
        run='r103_'+p['pair_key']+'_seed2026101701_'+arm
        c={k:copy.deepcopy(p[k]) for k in ('pair_key','motion_source_id','original_pair_id','group','identity','portrait','portrait_sha256','reference_image_expected','prompt','prompt_file','prompt_sha256','prompt_version','source_is_new_motion_content')}
        c.update(source_id=p['pair_key'],run_id=run,arm=arm,seed=2026101701,geometry=s['geometry'],valid_frame_count=147,reference_image_count=1,reference_video_count=1,evaluation_indices=list(range(0,147,3)),evaluation_crop_xywh=[0,0,1152,768],parent_graph='configs/parent_graphs/r66_native_template.json',parent_graph_sha256=sha(R/'configs/parent_graphs/r66_native_template.json'))
        c.update({k:p['source'][k] for k in ('video','video_sha256','provenance','provenance_sha256')});s['cases'].append(c);s['case_order'].append(run)
put(R/'configs/scientific_contract.json',s);put(R/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
for rel,row in numeric.items():
    row.update(parent_file=str(P/rel),parent_sha256=sha(P/rel),current_sha256=sha(R/rel),byte_equal=sha(P/rel)==sha(R/rel));assert row['byte_equal']
put(R/'configs/runtime_kernel_hashes.json',numeric)
put(R/'audit/INHERITED_BYTE_BINDINGS.json',{'parent_r96_seal_sha256':sha(P/'deploy_manifest.json'),'parent_r85_seal_sha256':sha(F/'deploy_manifest.json'),'proposal_sha256':sha(Q/'PREPARATION_VERIFIED.json'),'six_numerical_files':numeric,'inputs':read(R/'configs/input_hashes.json')})
# Use the native-screen administrative modules unchanged except their package IDs.
# The following custom contract and verifier are installed separately before sealing.
print('Prepared source scaffolding',R,len(s['cases']))
