"""Derive one CPU-only prompt repair from sealed R104. No remote/CUDA actions."""
from pathlib import Path
import copy,hashlib,json,re,shutil,sys
R=Path(__file__).resolve().parents[1];P=R.parent/'h3-timing-flexiact-remaining-repair-r104-20261019'
K='human2animal_1__game_man_4';REMOTE='/home/researcher/h3_runs/timing_flexiact_h2a1_game4_repair_r116_20261019';VERSION='P2-source-view-final-extension-r116-v1'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def cp(p,q):q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
assert not (R/'deploy_manifest.json').exists()
seal=read(P/'deploy_manifest.json');numeric=read(P/'configs/runtime_kernel_hashes.json')
for rel,row in seal['files'].items():
 assert sha(P/rel)==row['sha256'],rel
 if rel.startswith(('scripts/','extensions/','tests/','analysis/postrun/','source_snapshot/')) or rel=='audit/root_run_batch.py':
  dst=R/rel.replace('r104_contract.py','r116_contract.py');cp(P/rel,dst)
  if rel.endswith('.py') and rel not in numeric and not rel.startswith('source_snapshot/'):
   dst.write_text(dst.read_text().replace('r104','r116').replace('R104','R116').replace('P1-explicit-reference-roles-r116-v1',VERSION))
for rel in ('configs/parent_core_hashes.json','configs/expected_checkpoint_hashes.json','configs/storage_policy.json','configs/predecessor.json','configs/parent_graphs/r66_native_template.json','configs/R54_evidence/short_0210/captures.json','design/OFFICIAL_REF_EN.txt','audit/check_cpu_imports.py','audit/remote_cpu_validate.py'):
 cp(P/rel,R/rel)
for rel in ('deploy_manifest.json','configs/scientific_contract.json','configs/runtime.json','design/PAIR_DEFINITIONS.json','audit/root_run_batch.py','scripts/execution_gate.py'):
 cp(P/rel,R/'source_snapshot/r104'/rel)
old=read(R.parent/'h3-flexiact-character-repair-metrics-r98-20261019/configs/contract.json')
put(R/'source_snapshot/r98/contract.json',old)
prompt=old['prompt']
edits=[
 ('<Video 1> supplies the continuous shot structure, body orientation, motion order and physical timing for the target sequence.', '<Video 1> supplies the fixed side-facing camera view, subject scale, visible body framing, motion order and physical timing for the target sequence. <Picture 1> supplies identity, clothing, equipment, anime drawing style and the plain white environment.'),
 ('The complete visible body follows the reference action within the frame.', 'Keep the side-facing camera direction and subject scale of <Video 1>. Preserve the body regions visible in the source at each time, including its visible head and hands, within the same frame boundaries. Follow the source framing throughout the motion.'),
 ('As the reference motion continues, the character rounds his back and lowers his head. Follow the remaining visible movement through the end of <Video 1>, retaining the source sequence\'s pace, direction and range.', 'As the reference motion continues, the elbows remain extended while the head lowers and the upper back rounds upward. The visible hands and knee support remain on the floor as shown in <Video 1>. Continue this straight-arm, rounded-back and lowered-head phase through the final source frame, retaining the source sequence\'s pace, direction and range.')]
for before,after in edits:
 assert prompt.count(before)==1,before
 prompt=prompt.replace(before,after)
(R/'configs/prompts').mkdir(parents=True,exist_ok=True);(R/'configs/prompts'/f'{K}.txt').write_text(prompt)
defs=read(P/'design/PAIR_DEFINITIONS.json')['pairs'];motion=copy.deepcopy(defs[1]);identity=defs[0]
for key in ('identity','portrait','portrait_sha256','reference_image_expected'):motion[key]=copy.deepcopy(identity[key])
motion.update(pair_key=K,original_pair_id='official-assets/human2animal_1/game_man_4',group='official_assets_crosspair',official_pair_exact=False,prompt=prompt,prompt_file=f'configs/prompts/{K}.txt',prompt_sha256=sha(R/'configs/prompts'/f'{K}.txt'),prompt_version=VERSION,historical_failure={'producer':'R98/R101','consumer_contract_sha256':sha(R/'source_snapshot/r98/contract.json')})
motion['environment_requirement_provenance'].update(target_scene_observed='plain white backdrop from Picture 1',scope='Retained custom human crosspair task; official validation of human2animal_1 uses animal targets.')
for n in (motion['source']['original'],motion['source']['video'],motion['source']['provenance'],motion['portrait']):cp(P/'inputs'/n,R/'inputs'/n)
e={'schema':'r116-evidence-v1','items':[{'case_id':K,'source_id':'human2animal_1','target_id':'game_man_4','candidate_prompt':{'file':str(R/'configs/prompts'/f'{K}.txt'),'sha256':motion['prompt_sha256']},'parent_r98_prompt_sha256':hashlib.sha256(old['prompt'].encode()).hexdigest(),'prompt_changes':[{'before':a,'after':b} for a,b in edits],'source_original_sha256':motion['source']['original_sha256'],'target_sha256':motion['portrait_sha256'],'parent_r104_source_and_motion_prompt':str(P/'configs/prompts/human2animal_1__movie_man_11.txt')}],'new_source':False,'new_architecture':False}
put(R/'design/EVIDENCE.json',e)
accept={'schema':'r116-native-review-policy-v1','items':[{'case_id':K,'identity':'Recognizable short black hair, green cloak, brown jacket and harness; white scene.','motion':'Source low elbow flexion, subsequent arm extension/chest raise, then lowered head and upward rounded back with elbows remaining extended.','framing':'Preserve source side-facing view and body parts visible in source; source knees/lower legs already meet the left border, so no added full-body demand.','end_support':'Final source frame visibly shows both hands on floor and knee support near the left border; unseen feet/contact must not be inferred.','review_frames':147,'native_gate':'If basic identity, action sequence and comparable source framing pass, run same-config fixed guidance even when Native timing is already close. Task failure is retained and guide is skipped; partial cases require explicit root adjudication.','guided_review':'All147frames identity/action/timing; preserve neutral or degraded results.'}]}
put(R/'design/ACCEPTANCE.json',accept)
put(R/'design/SOURCE_EVENT_PLAN.json',{'source_sha256':motion['source']['original_sha256'],'original49_fps':8,'prepared24fps_valid147_mapping':'floor(i/3)','source_only_evidence':'Previously reviewed all49 original frames; final source column rechecked at prepared144-146 for R116.','phases_display_frames':{'low_elbow_flexion':[42,59],'chest_head_raise':[66,107],'head_lowers':[108,128],'straight_arm_back_rounding':[132,146]},'precision':'Coarse phase-presence brackets; original sampling precision0.125s, not exact arrivals.','contact_final':'Both hand contacts visible. Knee support near left border visible. Far lower leg/feet outside source framing.','recorded_before_any_r116_output':True})
put(R/'design/PAIR_DEFINITIONS.json',{'schema':'r116-one-task-repair-definitions-v1','pairs':[motion],'design_evidence_sha256':sha(R/'design/EVIDENCE.json'),'acceptance_sha256':sha(R/'design/ACCEPTANCE.json')})
put(R/'configs/prompt_ancestry.json',{'pair_definitions_sha256':sha(R/'design/PAIR_DEFINITIONS.json'),'official_guide_sha256':sha(R/'design/OFFICIAL_REF_EN.txt'),'proposal_parent':str(P),'new_method_claim':False})
put(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()})
put(R/'configs/source_selection/SELECTED_1_MANIFEST.json',{'pairs':[motion],'selection':'User-requested repair of an existing failed source/target crosspair; no held-out claim.'})
put(R/'configs/source_selection_hashes.json',{p.name:sha(p) for p in (R/'configs/source_selection').iterdir()})
put(R/'PREPARED_INPUTS_MANIFEST.json',{'pairs':[{'pair_id':K,'original':motion['source'],'portrait':motion['portrait'],'portrait_sha256':motion['portrait_sha256'],'valid_frames':147,'total_frames':158,'fps':24,'evaluation_indices':list(range(0,147,3))}]})
runtime=read(P/'configs/runtime.json');runtime.update(remote_root=REMOTE,port=8576,profile='host9_gpu3_r116_normal_reserve8',profile_scope='One existing Flex source/target repair with source-view and final arm-extension prompt; Native task acceptance then same-config fixed guidance. GPU launch requires root resource dispatch.');put(R/'configs/runtime.json',runtime)
put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
put(R/'configs/predecessor.json',{'schema':'r116-actual-screen-predecessor-v1','required':[{'key':'r104','remote_root':read(P/'configs/runtime.json')['remote_root'],'producer_seal_sha256':sha(P/'deploy_manifest.json'),'runtime_sha256':sha(P/'configs/runtime.json'),'kind':'screen','required_sources':[x['pair_key'] for x in defs]}],'attempt_names':'Root supplies actual completed R104 attempt, plus fresh resource admission.'})
s=read(P/'configs/scientific_contract.json');template=copy.deepcopy(s['cases'][2]);s.update(schema='r116-one-flex-task-repair-v1',source_ids=[K],pair_keys=[K],motion_source_ids=['human2animal_1'],cases=[],case_order=[],purpose=accept['items'][0]['native_gate'],prompt_version=VERSION,prepared_input_manifest_sha256=sha(R/'PREPARED_INPUTS_MANIFEST.json'),pair_definitions_sha256=sha(R/'design/PAIR_DEFINITIONS.json'))
s['screening'].update(fixed_source_denominator=1);s['evaluation'].update(fixed_case_denominator=1,rules_sha256=sha(R/'design/ACCEPTANCE.json'),scope='Existing official-asset custom crosspair. Full147 frames; both arms measured on original49@8fps.');s['continuous'].update(max_service_seconds=18000,job_timeout_seconds=10800)
for arm in ('native','forced'):
 c=copy.deepcopy(template)
 for key in ('pair_key','motion_source_id','original_pair_id','group','identity','portrait','portrait_sha256','reference_image_expected','prompt','prompt_file','prompt_sha256','prompt_version','source_is_new_motion_content'):c[key]=copy.deepcopy(motion[key])
 c.update(source_id=K,run_id=f'r116_{K}_seed2026101701_{arm}',arm=arm);s['cases'].append(c);s['case_order'].append(c['run_id'])
put(R/'configs/scientific_contract.json',s);put(R/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
for rel,row in numeric.items():row.update(parent_file=str(P/rel),parent_sha256=sha(P/rel),current_sha256=sha(R/rel),byte_equal=sha(P/rel)==sha(R/rel));assert row['byte_equal']
put(R/'configs/runtime_kernel_hashes.json',numeric)
put(R/'audit/INHERITED_BYTE_BINDINGS.json',{'parent_r104_seal_sha256':sha(P/'deploy_manifest.json'),'six_numerical_files':numeric,'inputs':read(R/'configs/input_hashes.json')})
p=R/'scripts/r116_contract.py';t=p.read_text();t=re.sub(r'SOURCES=PAIR_KEYS=.*',f'SOURCES=PAIR_KEYS=({K!r},)',t,count=1).replace("len(s['cases'])==6","len(s['cases'])==2").replace('Three original Flex tasks','One existing Flex task').replace('three task order','one task order').replace('three paired registry','one paired registry');p.write_text(t)
p=R/'scripts/preflight.py';p.write_text(p.read_text().replace("'sources':3","'sources':1"))
p=R/'tests/test_repair_contract.py';t=p.read_text().replace('len(order),6','len(order),2');t=re.sub(r'self.assertEqual\(c.SOURCES,\(.*\)\)',f'self.assertEqual(c.SOURCES,({K!r},))',t);p.write_text(t)
p=R/'tests/test_pair_verifier.py';p.write_text(p.read_text().replace("self.source='fitness__game_man_4'",f'self.source={K!r}'))
for folder in ('input','output','temp','user','custom_nodes','processes','logs','audit/router','audit/x0'):(R/folder).mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(R/'scripts'));import r116_contract as c
for row in s['cases']:put(R/'configs/graphs'/(row['run_id']+'.json'),c.expected_graph(R,row))
put(R/'audit/PREPARE_RECEIPT.json',{'parent':str(P),'parent_seal_sha256':sha(P/'deploy_manifest.json'),'source_ids':[K],'jobs':s['case_order'],'local_only':True,'gpu_started':False,'port':8576,'port_status':'Check target listener before CPU deployment and launch.','cost_estimate_minutes':120})
print('Prepared',R,'jobs',len(s['cases']))
