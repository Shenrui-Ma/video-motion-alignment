from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,hashlib,subprocess,math,ast
BASE=Path(__file__).resolve().parent.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=BASE/'source_candidates/pexels_5362065.mp4';out=BASE/'inputs/04_fast_motion.mp4'
argv=json.loads((BASE/'source_candidates/04_conversion_argv.json').read_text())
page='https://www.pexels.com/video/man-doing-bboying-outdoors-5362065/'
url='https://videos.pexels.com/video-files/5362065/5362065-uhd_3840_2160_25fps.mp4'
license_url='https://www.pexels.com/license/'
# Evaluate only the pure sampling_plan definition, without importing Torch or writing caches.
p=BASE/'extensions/H3EventAudit/__init__.py';module=ast.parse(p.read_text());fn=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='sampling_plan');scope={};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(p),'exec'),scope);plan=scope['sampling_plan'](107,2,0)
segments=[
 ('upright_entry',0,8,'Standing cross-step, arms open, torso lowers toward the first hand plant.',[0,5,8]),
 ('supported_circular_sweep_1',9,43,'First large hand-supported circular leg sweep: torso tips forward on the hands, legs swing behind and then open into a large elevated split in front before rotating back down.',[12,20,30,36,43]),
 ('supported_circular_sweep_2',44,73,'Second successive hand-supported circular leg-sweep cycle, again passing from face-down support through a large high/low leg split before returning low.',[48,54,60,66,73]),
 ('low_exit_sweep',74,83,'Low supported sweeping pivot; leg comes around and feet gather to end the floor sequence.',[74,79,83]),
 ('rise_to_standing',84,91,'Hands leave the ground, feet widen and torso rises from the floor sequence into upright stance.',[84,88,91]),
 ('closing_hop_and_landing',92,100,'One small upright two-foot hop, followed by landing; this is distinct from the earlier hand-supported airborne leg motions.',[93,96,100]),
 ('upright_settle',101,106,'Landed upright finishing adjustment with back toward camera.',[101,106])]
sequence=[]
for key,a,b,obs,anchors in segments:
 sequence.append({'id':key,'frames_inclusive':[a,b],'seconds_approx':[a/24,b/24],'observation':obs,'evidence_frames':anchors,'expected_2fps_observed_frames':[i for i in plan['sample_indices'] if a<=i<=b],'boundary_uncertainty_frames':3})
limits=[
 'AI visual annotation, not blinded human labels or expert dance nomenclature; phase boundaries are approximate, usually ±3 frames.',
 'This is a continuous breakdance phrase containing two similar supported circular leg-sweep cycles plus approach, exit sweep, rise and closing hop. It is not five unrelated tricks and is not purely a single repeated action.',
 'Source file playback has visibly fast transitions and no obvious slow-motion appearance. Capture camera speed and prior author processing cannot be independently certified; our conversion uses no artificial speed change.',
 'Original source is25FPS, resampled to24FPS by frame selection without motion interpolation. This can omit a source frame about once per second; it does not alter source-time speed.',
 'Some limb self-occlusion is inherent to the original pose, and brief natural motion blur exists. Body remains within the frame and broad movement phases remain clear.',
 'Sparse 2FPS coverage is expected from local instrumentation and is pre-GPU; actual new-sample audit must confirm it. Missing sampled poses do not prove missing information in the VAE path or an H3 generation failure.']
meta={
 'clip_id':'04_fast_motion','source_id':5362065,'source_provider':'Pexels','source_author':'Allan Mas','source_title':'Man Doing Bboying Outdoors',
 'source_file':str(source),'source_sha256':sha(source),'output_file':str(out),'output_sha256':sha(out),
 'source_start_seconds':0.24,'source_end_nominal_seconds':0.24+107/24,'source_fps_rational':'25/1','source_duration_seconds':5.12,
 'output_frames':107,'output_fps':24,'duration_seconds':107/24,'width':1312,'height':736,
 'conversion_argv':argv,'temporal_operation':'single contiguous crop plus25-to24FPS frame selection only; no speed change, interpolation, looping, concatenation or temporal padding',
 'spatial_operation':'aspect-preserving downscale from3840x2160 to1308x736 then2px side padding to1312x736; no body crop',
 'source_page':page,'download_url':url,'license':'Pexels License; source page links Free license; edits permitted by license page','license_url':license_url,
 'provenance_checked_date':'2026-10-13','selection_before_any_H3_output':True,
 'event':{'label':'continuous fast full-body dance phrase: hand-supported leg sweeps, low exit, rise and closing hop','type':'large-amplitude multi-phase action preservation; not an isolated ultra-short-event case',
          'transition_frames_inclusive':[0,106],'expected_count':1,
          'observable_component_counts':{'supported_circular_leg_sweep_cycles':2,'floor_to_standing_exit':1,'closing_upright_hop':1},
          'action_sequence':sequence,'observation':'All107frames inspected. Body repeatedly changes orientation and support from upright to hand-supported near-horizontal/split-leg poses and back upright, within4.46s. Broad phrase preserved as one contiguous source segment. Phase definitions are operational observations, not claims about canonical dance moves.'},
 'prompts':{
  'A':"Edit the source video by changing only the color of the man's dark charcoal short-sleeved T-shirt to bright red, keeping the same cut, fit and fabric details. Preserve the same person, hair, dark trousers, white shoes, riverside pavement, bridge, background and camera. Preserve all original body motion, gestures, action order, timing and rhythm. Keep all original actions unchanged.",
  'B_addition':"In particular, preserve the complete original dance sequence without simplifying it: the opening standing step and hand-down entry; both of the original large hand-supported circular leg-sweep cycles, first at about 0.4–1.8 seconds and then at about 1.8–3.1 seconds; the low sweeping exit and gathering of the feet around 3.1–3.5 seconds; the rise to standing around 3.5–3.8 seconds; and the single small upright two-foot hop with its landing around 3.8–4.2 seconds, followed by the original finishing adjustment. Keep the original two sweep cycles and one closing hop at their original times and in their original order; do not omit, add, repeat, slow down or replace any part of the motion."},
 'qa':{'all_107_frames_viewed_in_numbered_sheets':True,'full_body_visible':True,'single_principal_subject':True,'no_scene_cut':True,'edit_target_visible':True,'observed_fast_source_playback':True,'capture_real_time_certified':False,'limitations':limits},
 'evidence':{'numbered_contact_sheets':[str(BASE/f'source_candidates/04_fast_motion_frames_p{i}.jpg') for i in range(1,5)],'keyframe_sheet':str(BASE/'source_candidates/04_fast_motion_key_phases.jpg'),'expected_2fps_sheet':str(BASE/'source_candidates/04_fast_motion_expected_2fps.jpg'),'first_frame':str(BASE/'inputs/04_fast_motion.png')},
 'semantic_sampling_pre_gpu':{'status':'expected_pre_GPU_not_actual_new_sample_audit','basis_function':'extensions/H3EventAudit/__init__.py sampling_plan(107,2,0)','basis_file_sha256':sha(p),'plan':plan,
 'coverage_summary':'Nine distinct frames0,12,...96. Two-frame temporal grouping repeats96 for its final pair. The74–83 low exit and101–106 finishing adjustment have no sampled frame; the closing hop is represented at96 but its landing is not directly sampled. Adjacent observed poses may still imply transitions; no generation outcome or branch attribution is inferred.'}}
(BASE/'inputs/04_fast_motion.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
(BASE/'inputs/source_manifest.json').write_text(json.dumps({'date':'2026-10-13','purpose':'Single-source fast large-motion follow-up, selected before H3 results','clips':[meta],'selection_notes':['Separate lab; old pilot archive read only.','Same107frames24FPS1312x736 geometry; source-time speed retained.','Download-and-view budget used on exactly3actual candidate files.','No source selection on H3 failure.']},ensure_ascii=False,indent=2)+'\n')
# Derivative sheets for source selection only.
raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(out),'-vf','scale=400:224','-f','rawvideo','-pix_fmt','rgb24','-']);size=400*224*3
frames=[Image.frombytes('RGB',(400,224),raw[i*size:(i+1)*size]) for i in range(107)]
font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',18)
for name,ids,pad in [('04_fast_motion_key_phases',[0,8,20,30,43,49,60,73,80,90,96,102],False),('04_fast_motion_expected_2fps',plan['sample_indices']+[96],True)]:
 cols=4 if not pad else 5
 can=Image.new('RGB',(cols*400,math.ceil(len(ids)/cols)*253+36),'white');d=ImageDraw.Draw(can)
 d.text((5,5),'SOURCE phase evidence' if not pad else 'EXPECTED native2FPS phase0 (pre-GPU); last96 is temporal-pair padding',font=font,fill='black')
 for j,i in enumerate(ids):
  x=j%cols*400;y=j//cols*253+36;can.paste(frames[i],(x,y));label=f'f{i:03d} | {i/24:.3f}s'+(' | PAD repeat' if pad and j==len(ids)-1 else'');d.text((x+3,y+226),label,font=font,fill='black')
 can.save(BASE/'source_candidates'/f'{name}.jpg',quality=95)
provenance={'selected_clip_id':meta['clip_id'],'source':meta['source_page'],'download_url':url,'author':'Allan Mas','source_sha256':meta['source_sha256'],'output_sha256':meta['output_sha256'],'license_url':license_url,'license_evidence':'Pexels source page identifies license as Free; license page permits free downloading/use and modification. No endorsement is implied.','license_checked_via_web_tool':True,'local_page_fetch_note':'Direct Pexels HTML curl was HTTP403 challenge; web tool read source and license successfully. Public Free download link resolved to the recorded videos.pexels.com asset, downloaded directly.','actual_downloaded_candidates':[],'page_only_exclusions':[{'source_url':'https://mixkit.co/free-stock-video/breakdancer-practicing-488/','reason':'explicitSlowMotion tag'},{'source_url':'https://mixkit.co/free-stock-video/man-breakdancing-452/','reason':'explicitSlowMotion tag'},{'source_url':'https://mixkit.co/free-stock-video/urban-dancer-dancing-breakdance-3628/','reason':'explicitSlowMotion tag and portrait frame'},{'source_url':'https://mixkit.co/free-stock-video/young-break-dancer-performing-in-white-clothes-36741/','reason':'freeversionRestrictedLicense; betterfreelyeditableoptionfound'},{'source_url':'https://mixkit.co/free-stock-video/guy-dancing-breakdance-on-the-roof-47128/','reason':'freeversionRestrictedLicense; betterfreelyeditableoptionfound'}]}
for name,sourcepage,reason in [
 ('mix_444','https://mixkit.co/free-stock-video/breakdancing-444/','Rejected after whole-source2FPS overview: strong backlight and suspected existing slow playback; not enough evidence for desired fast visible transitions.'),
 ('pexels_5362065',page,'Selected: clear entire body, natural continuous fast pose changes, two floor sweep cycles plus distinct upright entry/low exit/rise/hop phases in4.46s. All107outputframes viewed.'),
 ('pexels_4938874','https://www.pexels.com/video/man-doing-breakdancing-4938874/','Rejected after whole-source4FPS overview: primarily repeated rolling/inversion cycles, dark scene, and later approach crops head; chosen5362065offersclearerfullbodyphasechanges.')]:
 file=BASE/'source_candidates'/f'{name}.mp4';provenance['actual_downloaded_candidates'].append({'file':str(file),'sha256':sha(file),'source_page':sourcepage,'decision':reason})
(BASE/'analysis/source_selection_provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
review={'status':'selected_ready_for_root_visual_acceptance','human_review':False,'selection_before_any_generated_result':True,'clip_id':meta['clip_id'],'metadata_path':str(BASE/'inputs/04_fast_motion.json'),'source_frame_count':107,'all_frames_actually_viewed':True,'action_sequence':sequence,'expected_sampling':meta['semantic_sampling_pre_gpu'],'evidence':meta['evidence'],'limits':limits,'conclusion':'Suitable single clear fast large-motion follow-up. Contains multiple broad motion phases, while explicitly retaining that the central leg-sweep pattern repeats twice. Nothing here establishes H3 failure or a research mechanism.'}
(BASE/'analysis/source_selection_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'input':str(out),'metadata':str(BASE/'inputs/04_fast_motion.json'),'sha256':sha(out),'phases':sequence,'sample_indices':plan['sample_indices']},ensure_ascii=False,indent=2))
