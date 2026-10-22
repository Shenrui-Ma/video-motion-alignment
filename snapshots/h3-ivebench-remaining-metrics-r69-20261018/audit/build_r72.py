from pathlib import Path
import json,hashlib,shutil,copy,math
from PIL import Image
B=Path('/Users/researcher/DevProjects');R=B/'h3-timing-flexiact-prompt-pair-r72-20261018';P71=B/'h3-timing-ivebench-prompt-pair-r71-20261018';P66=B/'h3-timing-flexiact-expanded-r66-20261018';SEL=B/'h3-ivebench-remaining-metrics-r69-20261018/audit/flex_official_inventory'
assert not R.exists();R.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):p=R/p;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def cp(source,dest):p=R/dest;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,p)
for folder in ['scripts','extensions','analysis/postrun','tests/fixtures']:
 for p in (P71/folder).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:
   dest=R/p.relative_to(P71);dest.parent.mkdir(parents=True,exist_ok=True)
   if p.suffix=='.py':dest.write_text(p.read_text().replace('r71','r72').replace('R71','R72'))
   else:shutil.copy2(p,dest)
(R/'scripts/r72_contract.py').write_text((R/'scripts/r71_contract.py').read_text());(R/'scripts/r71_contract.py').unlink()
for name in ['parent_core_hashes.json','expected_checkpoint_hashes.json']:
 cp(P71/'configs'/name,'configs/'+name)
rt=json.loads((P66/'configs/runtime.json').read_text());rt.update(status='CPU_PREPARED_ROOT_LAUNCH_PENDING',remote_root='/data3/researcher/h3_runs/timing_flexiact_prompt_pair_r72_20261018',port=8539,expected_gpu_index=6,profile='host41_gpu6_normal_reserve8',profile_scope='R66 same-host numeric runtime; two fresh Native P0/P1 official Flex pairs. Root40GiB trial after R64 release; wait first-pair review before second pair.')
# Resolve original stable GPU6 identity from current R64 contract, without touching live runtime.
rs=list(B.glob('h3-timing-ivebench-*-r64-20261018'));r64=next(p for p in rs if (p/'configs/runtime.json').exists());rt['gpu_uuid']=json.loads((r64/'configs/runtime.json').read_text())['gpu_uuid'];put('configs/runtime.json',rt)
put('configs/admission.json',{'ready_for_launch':False,'permitted_compute_processes':[],'scope':'Root admits only after current R64 GPU6 exact release; R69 may remain active on GPU7.'})
for f in ['source_fitness_video.mp4','source_fitness_provenance.json','source_one_leg_video.mp4','source_one_leg_provenance.json']:cp(P66/'inputs'/f,'inputs/'+f)
selected=json.loads((SEL/'FIXED_8_CANDIDATES.json').read_text());chosen=[x for x in selected['pairs'] if x['source'] in ('fitness','one_leg')];assert len(chosen)==2
cp(SEL/'FIXED_8_CANDIDATES.json','design/FIXED_8_CANDIDATES.json')
cp(B/'h3-ivebench-remaining-metrics-r69-20261018/audit/flex_prompt_review/official_ref-en.txt','design/official_ref-en.txt')
cp(B/'h3-ivebench-remaining-metrics-r69-20261018/audit/flex_prompt_review/actual_comfy_minimax.py','design/actual_comfy_minimax.py')
cp(P66/'configs/graphs/r66_fitness__game_man_4_seed2026101701_native.json','configs/parent_graphs/r66_fitness_native_template.json')
p0=json.loads((P66/'configs/scientific_contract.json').read_text())['cases'][0]['prompt']
(R/'configs/prompts').mkdir(parents=True);(R/'configs/prompts/p0.txt').write_text(p0)
template='''subject_definitions:
<Subject 1> is {target_identity} in <Picture 1>. <Picture 1> provides this subject's identity, appearance, clothing and visual style.
<Subject 2> is the background and environment shown in <Picture 1>.
<Video 1> provides the complete body-motion sequence and its timing. Source motion context: {source_caption}

summary:
[reference generation] Generate <Subject 1> performing the complete body-motion sequence from <Video 1> in <Subject 2>.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - preserve the identity, appearance, clothing and visual style provided by <Picture 1>.
<Subject 2> (appears in [Shot 1]): fully_preserved - preserve the background and environment provided by <Picture 1>.
<Video 1> (body-motion reference): fully_preserved - reproduce the complete sequence of body motions, including their order, timing, direction and amplitude, with the target subject.

detailed_description:
[Shot 1] <Subject 1>, {target_identity} from <Picture 1>, performs the body movements from <Video 1> in <Subject 2>. {target_action}
Follow the complete visible motion sequence and its timing in <Video 1> throughout the clip. The subject's appearance and the scene come from <Picture 1>.

overall_soundscape:
No specific soundscape is requested.

non_diegetic_music:
No specific music is requested.
'''
(R/'design/P1_TEMPLATE.txt').write_text(template)
fields={
'fitness':{'target_identity':'the red-and-gold armored humanoid character','source_caption':'A woman raised her arms above her head, then slowly brought her hands together and lowered them to her chest.','target_action':'The character raises both arms above the head, then slowly brings the hands together and lowers them to the chest.'},
'one_leg':{'target_identity':'the elderly man wearing a dark suit','source_caption':'A man raised his hands above his head while placing his right foot against his left knee.','target_action':'The man raises his hands above his head while placing his right foot against his left knee.'}}
parent='configs/parent_graphs/r66_fitness_native_template.json';g0=json.loads((R/parent).read_text());cases=[];order=[];pairs=[]
for item in chosen:
 s=item['source'];identity=item['target'];pair=s+'__'+Path(identity).stem;portrait='target_'+Path(identity).name
 cp(Path(item['target_asset']['path']),'inputs/'+portrait);cp(Path(item['source_asset']['path']),'inputs/source_'+s+'_original.mp4')
 iw,ih=Image.open(R/'inputs'/portrait).size;scale=min(1,math.sqrt(1152*768/(iw*ih)));w=max(32,round(iw*scale/32)*32);h=max(32,round(ih*scale/32)*32)
 expected={'original_width_height':[iw,ih],'expected_native_ref_image_size_match_width_height':[w,h],'expected_clean_reference_latent_shape':[1,24,1,h//16,w//16],'expected_DiT_visual_patch_tokens':(h//32)*(w//32),'formula':'frozen native ref_image_size=match, proportional scale down then each axis rounded32'}
 p1=template.format(**fields[s]);(R/'configs/prompts'/(pair+'_p1.txt')).write_text(p1)
 info={'pair_key':pair,'motion_source_id':s,'identity':identity,'official_csv_row_zero_based':item['csv_row_zero_based'],'official_target_caption':item['official_caption'],'source_caption':fields[s]['source_caption'],'target_semantic_description':fields[s]['target_identity'],'target_action':fields[s]['target_action'],'source_is_new_motion_content':False,'target_pair_previously_generated':False,'reference_image_expected':expected,'target_asset':item['target_asset'],'source_asset':item['source_asset'],'p1_fields':fields[s],'prompt_files':{'p0':'configs/prompts/p0.txt','p1':'configs/prompts/'+pair+'_p1.txt'}}
 info['prompt_sha256']={a:sha(R/f) for a,f in info['prompt_files'].items()};pairs.append(info)
 for arm,prompt in [('p0',p0),('p1',p1)]:
  run='r72_'+pair+'_seed2026101701_'+arm;order.append(run);video='source_'+s+'_video.mp4';prov='source_'+s+'_provenance.json'
  case={'run_id':run,'source_id':pair,'pair_key':pair,'motion_source_id':s,'arm':arm,'seed':2026101701,'prompt':prompt,'prompt_version':arm.upper(),'reference_cache_id':'r72_'+pair+'_'+arm+'_shared','prompt_file':info['prompt_files'][arm],'prompt_sha256':info['prompt_sha256'][arm],'parent_graph':parent,'parent_graph_sha256':sha(R/parent),'video':video,'portrait':portrait,'provenance':prov,'identity':identity,'video_sha256':sha(R/'inputs'/video),'portrait_sha256':sha(R/'inputs'/portrait),'provenance_sha256':sha(R/'inputs'/prov),'geometry':{'width':1152,'height':768,'frames':158,'fps':24},'reference_video_count':1,'reference_image_count':1,'valid_frame_count':147,'evaluation_indices':list(range(0,147,3)),'evaluation_crop_xywh':[0,0,1152,768],'reference_image_expected':expected}
  cases.append(case);g=copy.deepcopy(g0)
  for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(Path(rt['remote_root'])/suffix)
  g['5']['inputs'].update(run_id=case['reference_cache_id'],prompt=prompt);g['51']['inputs']['source_run_id']=case['reference_cache_id']
  for node in ['6','50','51','52']:g[node]['inputs']['run_id']=run
  g['6']['inputs']['pair_id']='r72_'+pair+'_seed2026101701';g['14']['inputs']['filename_prefix']=run;g['21']['inputs']['image']=portrait;g['22']['inputs']['file']=video
  put('configs/graphs/'+run+'.json',g)
put('design/PAIR_DEFINITIONS.json',{'schema':'r72-two-new-official-flex-pairs-v1','selection_sha256':sha(R/'design/FIXED_8_CANDIDATES.json'),'pairs':pairs,'prompt_policy':'P0 verbatim R49/R65/R66; P1 structured reference-generation roles with image appearance+scene and video complete motion/time. No event windows, new actions, output-informed refinements or source-scene retention added.','caption_note':'fitness game_man_5 official target caption calls an armored humanoid a cartoon monster; P1 binds visible red-and-gold armored character rather than adding monster anatomy. Original caption retained.','guide_commit':'d21241f0a4b3acbb34c97dae47fa417b7065e438'})
sci=json.loads((P71/'configs/scientific_contract.json').read_text());sci.update(schema='r72-preregistered-flex-prompt-pairs-v1',case_order=order,cases=cases,geometry=cases[0]['geometry'],source_ids=[x['pair_key'] for x in pairs],pair_keys=[x['pair_key'] for x in pairs],input_reference_images=1,router={'mode':'native','alpha':1.,'blocks':[0,50],'steps':[0,20],'physical_frames':[0,146],'query_support':'all44 valid-overlapping temporal bins and all spatial queries'},purpose='Two preselected new official FlexiAct identity pairs; fresh P0/P1 Native prompt-protocol diagnostic; no timing-method performance claim.',condition_scope='Original image/video bytes and actual VAE/Qwen pre-encoder reference values equal within each pair; per-arm joint embeddings, text tags, positions and all x0 may differ; actual AV noise equal.',first_pair='fitness game_man_5 P0 then P1; root review before one_leg movie_man_9 P0/P1',source_event_annotations='No event windows; source49@8 expanded by3 exact repeats plus11tailpadding to158@24; evaluation147valid/indices0,3,...144.')
sci['evaluation']={'official':'FlexiAct pinned official Motion Fidelity on49@8 sampled indices0,3,...144','padding_evaluated':False,'full_benchmark_reproduction':False,'fixed_pairs':2};sci['acceleration_axes']['runtime']='Same .41 numerical/runtime kernel profile as R66; actual versions recorded at launch';sci['acceleration_axes']['cache']='P0/P1 separate conditioning IDs and same actual AV noise per pair';sci['continuous']['idle_hold_seconds']=1800;sci['continuous']['job_timeout_seconds']=14400
put('configs/scientific_contract.json',sci);put('configs/queue.json',{'jobs':order,'finalize':True});put('configs/input_hashes.json',{p.name:sha(p) for p in sorted((R/'inputs').iterdir())})
put('configs/runtime_kernel_hashes.json',{f:{'parent_file':str(P66/f),'parent_sha256':sha(P66/f),'current_sha256':sha(R/f),'byte_equal':sha(P66/f)==sha(R/f)} for f in json.loads((P71/'configs/runtime_kernel_hashes.json').read_text())})
put('configs/prompt_ancestry.json',{'p0_parent_contract':{'file':str(P66/'configs/scientific_contract.json'),'sha256':sha(P66/'configs/scientific_contract.json')},'p0_sha256':sha(R/'configs/prompts/p0.txt'),'p1_template_sha256':sha(R/'design/P1_TEMPLATE.txt'),'pair_definitions_sha256':sha(R/'design/PAIR_DEFINITIONS.json'),'official_guide_sha256':sha(R/'design/official_ref-en.txt')})
print(R);print('GPU',rt['gpu_uuid'],'pairs',[x['pair_key'] for x in pairs]);print('inputs',sum(p.stat().st_size for p in (R/'inputs').iterdir()))
