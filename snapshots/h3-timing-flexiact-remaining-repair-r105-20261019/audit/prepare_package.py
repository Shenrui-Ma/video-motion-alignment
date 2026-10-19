"""Build the new local CPU package only; no service or CUDA action."""
from pathlib import Path
import copy,hashlib,json,shutil
from PIL import Image
R=Path(__file__).resolve().parents[1];D=R.parent;ID='r105'
P=D/'h3-timing-flexiact-p1-repair-r103-20261019';O=D/'h3-timing-ive-task-repair-r102-20261019';Q=D/'h3-flexiact-remaining-repair-design-r104-20261019'
KEYS=['human2animal_2__movie_man_11','crouch__movie_man_4','human2animal_3__game_man_4']
REMOTE='/home/researcher/h3_runs/timing_flexiact_remaining_repair_r105_20261019';GPU=0;UUID='GPU-REDACTED';PORT=8569
VERSION='P1-explicit-reference-roles-r105-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def cp(p,q):q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
assert not (R/'deploy_manifest.json').exists()
numeric=read(P/'configs/runtime_kernel_hashes.json')
for rel in read(P/'deploy_manifest.json')['files']:
 if not(rel.startswith(('scripts/','extensions/','tests/','analysis/postrun/')) or rel=='audit/root_run_batch.py'):continue
 if Path(rel).name in ('cgroup_memory.py','test_cgroup_memory.py','predecessor.py'):continue
 dst=R/rel.replace('r103_contract.py',ID+'_contract.py');cp(P/rel,dst)
 if rel.endswith('.py') and rel not in numeric:
  text=dst.read_text().replace('r103',ID).replace('R103',ID.upper()).replace('human2animal_2__game_man_4',KEYS[0]).replace('chest__game_girl_1',KEYS[1]).replace('P1-reference-v1',VERSION)
  dst.write_text(text)
for rel in ('scripts/service.py','scripts/run_queue.py','audit/root_run_batch.py'):
 cp(O/rel,R/rel);(R/rel).write_text((R/rel).read_text().replace('r102',ID).replace('R102',ID.upper()))
for rel in ('configs/parent_core_hashes.json','configs/expected_checkpoint_hashes.json','configs/storage_policy.json'):
 cp(O/rel,R/rel)
for rel in ('audit/check_cpu_imports.py','audit/remote_cpu_validate.py'):cp(P/rel,R/rel)
for parent,label in ((P,'r103'),(O,'r102')):
 for rel in ('deploy_manifest.json','configs/runtime.json','scripts/execution_gate.py','scripts/run_queue.py','audit/root_run_batch.py','analysis/postrun/verify_pair.py'):
  cp(parent/rel,R/'source_snapshot'/label/rel)
for rel in ('source_snapshot/r59/sealed_r3_core.py','source_snapshot/http_original/run_queue.py','configs/R54_evidence/short_0210/captures.json'):
 cp(P/rel,R/rel)
all_e=read(Q/'EVIDENCE.json');e=copy.deepcopy(all_e);lookup={x['case_id']:x for x in e['items']};e['items']=[lookup[k] for k in KEYS];e['producer_scope']=ID
put(R/'design/EVIDENCE.json',e);cp(Q/'EVIDENCE.json',R/'design/ORIGINAL_SIX_EVIDENCE.json')
a=read(Q/'ACCEPTANCE.json');a['items']=[next(x for x in a['items'] if x['case_id']==k) for k in KEYS];put(R/'design/ACCEPTANCE.json',a)
for n in ('PREPARATION_VERIFIED.json','FINAL_PREPARATION.json','SOURCE_TARGET_REVIEW.json','README.txt','PROPOSED_ORDER.json'):cp(Q/n,R/'design'/n)
cp(Q/'metadata/official_ref-en.md',R/'design/OFFICIAL_REF_EN.txt')
for folder in ('inputs','input','output','temp','user','custom_nodes','processes','logs','configs/graphs','configs/prompts','configs/parent_graphs','configs/source_selection','configs/R54_evidence','audit/router','audit/x0'):(R/folder).mkdir(parents=True,exist_ok=True)
cp(P/'configs/parent_graphs/r66_native_template.json',R/'configs/parent_graphs/r66_native_template.json')
defs=[]
for item in e['items']:
 key=item['case_id'];motion=item['source_id'];source=Path(item['source_prepared']['file']);portrait=Path(item['target_image']['file']);prov=Path(item['provenance']['file']);original=Path(item['source_original']['file'])
 for field in ('source_prepared','target_image','provenance','source_original','candidate_prompt','previous_graph','previous_contract'):
  rec=item[field];assert sha(Path(rec['file']))==rec['sha256'],field
 for p in (source,portrait,prov,original):cp(p,R/'inputs'/p.name)
 cp(Path(item['candidate_prompt']['file']),R/'configs/prompts'/(key+'.txt'))
 cp(Path(item['previous_prompt']['file']),R/'design/previous_prompts'/(key+'.txt'))
 cp(Path(item['previous_graph']['file']),R/'source_snapshot/old_tasks'/(key+'_graph.json'))
 cp(Path(item['previous_contract']['file']),R/'source_snapshot/old_tasks'/(key+'_contract.json'))
 width,height=Image.open(portrait).size;scale=min(1.,(1152*768/(width*height))**.5);w,h=[round(n*scale/32)*32 for n in (width,height)]
 image={'original_width_height':[width,height],'expected_native_ref_image_size_match_width_height':[w,h],'expected_clean_reference_latent_shape':[1,24,1,h//16,w//16],'expected_DiT_visual_patch_tokens':h//32*(w//32),'formula':'pinned native ref_image_size=match: min(1,sqrt(canvas_area/image_area)); each axis round32; actual inference verified by gate'}
 v=read(prov);assert v['input_to_original']==[i//3 for i in range(147)]+[48]*11
 p={'pair_key':key,'motion_source_id':motion,'original_pair_id':'official-assets/'+motion+'/'+item['target_id'],'group':'original_official_pair' if item['official_pair_exact'] else 'official_assets_crosspair','identity':item['previous_case']['identity'],'source':{'original':original.name,'original_sha256':sha(original),'video':source.name,'video_sha256':sha(source),'provenance':prov.name,'provenance_sha256':sha(prov)},'portrait':portrait.name,'portrait_sha256':sha(portrait),'reference_image_expected':image,'prompt_file':'configs/prompts/'+key+'.txt','prompt_sha256':sha(R/'configs/prompts'/(key+'.txt')),'prompt':(R/'configs/prompts'/(key+'.txt')).read_text(),'prompt_version':VERSION,'historical_failure':item['previous_graph'],'source_is_new_motion_content':False,'official_pair_exact':item['official_pair_exact'],'environment_requirement_provenance':item['environment_requirement_provenance']}
 defs.append(p)
put(R/'design/PAIR_DEFINITIONS.json',{'schema':ID+'-three-task-repair-definitions-v1','pairs':defs,'design_evidence_sha256':sha(R/'design/EVIDENCE.json'),'acceptance_sha256':sha(R/'design/ACCEPTANCE.json')})
put(R/'configs/prompt_ancestry.json',{'pair_definitions_sha256':sha(R/'design/PAIR_DEFINITIONS.json'),'official_guide_sha256':sha(R/'design/OFFICIAL_REF_EN.txt'),'proposal_parent':str(Q),'new_method_claim':False})
put(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()})
put(R/'configs/source_selection/SELECTED_3_MANIFEST.json',{'pairs':defs,'selection':'All three prespecified previously failed tasks; original inputs retained, no new-source or held-out claim.'})
put(R/'configs/source_selection_hashes.json',{p.name:sha(p) for p in (R/'configs/source_selection').iterdir()})
put(R/'PREPARED_INPUTS_MANIFEST.json',{'pairs':[{'pair_id':p['pair_key'],'original':p['source'],'portrait':p['portrait'],'portrait_sha256':p['portrait_sha256'],'valid_frames':147,'total_frames':158,'fps':24,'evaluation_indices':list(range(0,147,3))} for p in defs]})
runtime=read(O/'configs/runtime.json');runtime.update(remote_root=REMOTE,expected_gpu_index=GPU,gpu_uuid=UUID,port=PORT,profile='host9_gpu'+str(GPU)+'_'+ID+'_normal_reserve8',profile_scope='Three original Flex reference-image tasks repaired with frozen six-part prompts. Both arms freshly generated on host9; Native root task acceptance precedes known fixed guidance. Historical failures may use other hosts and are not paired controls.')
put(R/'configs/runtime.json',runtime)
put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
s=read(P/'configs/scientific_contract.json');s.update(schema=ID+'-flex-p1-native-first-repair-v1',source_ids=KEYS,pair_keys=KEYS,motion_source_ids=[p['motion_source_id'] for p in defs],cases=[],case_order=[],purpose='Repair three prior character transfers with the original source and portrait; root accepts each fresh Native before optional matched known fixed guidance.',prompt_version=VERSION)
s['prepared_input_manifest_sha256']=sha(R/'PREPARED_INPUTS_MANIFEST.json');s['pair_definitions_sha256']=sha(R/'design/PAIR_DEFINITIONS.json')
s['screening'].update(schema=ID+'-native-screen-policy-v1',fixed_source_denominator=3)
s['continuous'].update(max_service_seconds=100800,job_timeout_seconds=14400)
s['evaluation'].update(fixed_case_denominator=3,rules_sha256=sha(R/'design/ACCEPTANCE.json'),scope='Three retained failed tasks using official source/target assets. Official pairing versus crosspair is recorded per task. Whole valid147 frames and original49 action times; no independent held-out claim.')
s['acceleration_axes'].update(runtime='Exact host9 R102 core/runtime profile and six byte-identical numerical modules inherited through R103; fresh same-service Native/forced per pair.')
for p in defs:
 for arm in ('native','forced'):
  run=ID+'_'+p['pair_key']+'_seed2026101701_'+arm
  c={k:copy.deepcopy(p[k]) for k in ('pair_key','motion_source_id','original_pair_id','group','identity','portrait','portrait_sha256','reference_image_expected','prompt','prompt_file','prompt_sha256','prompt_version','source_is_new_motion_content')}
  c.update(source_id=p['pair_key'],run_id=run,arm=arm,seed=2026101701,geometry=s['geometry'],valid_frame_count=147,reference_image_count=1,reference_video_count=1,evaluation_indices=list(range(0,147,3)),evaluation_crop_xywh=[0,0,1152,768],parent_graph='configs/parent_graphs/r66_native_template.json',parent_graph_sha256=sha(R/'configs/parent_graphs/r66_native_template.json'))
  c.update({k:p['source'][k] for k in ('video','video_sha256','provenance','provenance_sha256')});s['cases'].append(c);s['case_order'].append(run)
put(R/'configs/scientific_contract.json',s);put(R/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
for rel,row in numeric.items():
 row.update(parent_file=str(P/rel),parent_sha256=sha(P/rel),current_sha256=sha(R/rel),byte_equal=sha(P/rel)==sha(R/rel));assert row['byte_equal'];assert sha(O/rel)==row['current_sha256']
put(R/'configs/runtime_kernel_hashes.json',numeric)
put(R/'audit/INHERITED_BYTE_BINDINGS.json',{'parent_r103_seal_sha256':sha(P/'deploy_manifest.json'),'parent_r102_seal_sha256':sha(O/'deploy_manifest.json'),'proposal_sha256':sha(Q/'FINAL_PREPARATION.json'),'six_numerical_files':numeric,'inputs':read(R/'configs/input_hashes.json')})
# Narrow case-count and host metadata adaptations; no numerical core edits.
p=R/'scripts'/f'{ID}_contract.py';t=p.read_text().replace("SOURCES=PAIR_KEYS=('"+KEYS[0]+"','"+KEYS[1]+"')",'SOURCES=PAIR_KEYS='+repr(tuple(KEYS))).replace("len(s['cases'])==4","len(s['cases'])==6").replace('Two original Flex tasks','Three original Flex tasks').replace('two task order','three task order').replace('two paired registry','three paired registry');p.write_text(t)
p=R/'scripts/preflight.py';p.write_text(p.read_text().replace("'sources':2","'sources':3"))
p=R/'scripts/verify_input_timeline.py';p.write_text(p.read_text().replace('.41','cross-host').replace('host41','host9'))
p=R/'scripts/execution_gate.py';p.write_text(p.read_text().replace("'configs/cgroup_policy.json',",''))
p=R/'tests/test_repair_contract.py';t=p.read_text();t=t[:t.index('class PredecessorRelease')]+"if __name__=='__main__':unittest.main()\n";t=t.replace('self.assertEqual(len(order),4)','self.assertEqual(len(order),6)').replace("self.assertEqual(c.SOURCES,('"+KEYS[0]+"','"+KEYS[1]+"'))",'self.assertEqual(c.SOURCES,'+repr(tuple(KEYS))+')');p.write_text(t)
print('Prepared',R,'jobs',len(s['cases']))
