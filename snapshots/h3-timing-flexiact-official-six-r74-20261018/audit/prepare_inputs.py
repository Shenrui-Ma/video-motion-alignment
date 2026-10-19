"""CPU preparation; preserves official bytes and R66 repeat-three recipe."""
from pathlib import Path
import json,hashlib,subprocess,shutil,math,csv,time
from PIL import Image
R=Path(__file__).resolve().parents[1];OLD=Path('/Users/researcher/DevProjects/h3-timing-flexiact-prompt-pair-r72-20261018');SEL=Path('/Users/researcher/DevProjects/h3-flexiact-expanded-selection-20261018')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def probe(p):return json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-show_streams','-show_frames','-of','json',str(p)]))
def hashes(p,vf=None):
 c=['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(p),'-map','0:v:0','-an']
 if vf:c+=['-vf',vf]
 c+=['-pix_fmt','yuv420p','-threads','2','-f','framemd5','-']
 return [x.split(',')[-1].strip() for x in subprocess.check_output(c,text=True).splitlines() if x and not x.startswith('#')]
rows=[p for p in json.loads((R/'design/FIXED_8_CANDIDATES.json').read_text())['pairs'] if p['source'] not in ['fitness','one_leg']]
identities={'game_man_5':'the red-and-gold armored humanoid character','movie_man_7':'the shirtless man wearing black shorts','movie_man_5':'the man wearing a dark suit and tie','movie_man_9':'the elderly man wearing a dark suit','game_man_1':'the cartoon character wearing a red cap, blue overalls and white gloves','game_man_4':'the dark-haired anime man wearing a green cape'}
actions={'chest':'The subject grips the resistance-machine handles, pulls both arms downward and inward, then opens and raises the arms again, repeating the visible movement sequence.','crouch':'The subject bends the knees and hips into a squat while raising the hands in front of the chest, returns to standing, and repeats the squat as shown in the reference video.','rotate':'The subject stands with the legs apart and the hands held together in front of the chest, then rotates the torso and arms from side to side while the feet remain planted.'}
source_notes={'chest':'Both arms start extended laterally and lower/inward, open again and repeat. Some hands/forearms leave the source crop at the first high-arm poses.','crouch':'Outdoor squat sequence on a dock. The resistance-machine caption for movie_man_5 is a metadata mismatch.','rotate':'Torso rotation with hands at chest; full body visible, feet widely planted. Small shoulder/head details may be less reliable in the dark source.'}
inputs=R/'inputs';inputs.mkdir(exist_ok=True);sources={};mapping=[min(i//3,48) for i in range(158)]
for source in dict.fromkeys(p['source'] for p in rows):
 row=next(p for p in rows if p['source']==source);original=inputs/f'source_{source}_original.mp4';video=inputs/f'source_{source}_video.mp4';assert sha(row['source_asset']['path'])==row['source_asset']['sha256'];shutil.copy2(row['source_asset']['path'],original)
 raw=probe(original);frames=[f for f in raw['frames'] if f['media_type']=='video'];assert len(frames)==49 and all((f['width'],f['height'])==(720,480) and abs(float(f['best_effort_timestamp_time'])-i/8)<1e-6 for i,f in enumerate(frames))
 vf='scale=1152:768:flags=lanczos,fps=24:round=near,tpad=stop_mode=clone:stop=11,trim=end_frame=158,setpts=N/(24*TB),setsar=1'
 cmd=['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(original),'-map','0:v:0','-an','-vf',vf,'-c:v','libx264','-crf','0','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(video)]
 if not video.exists():subprocess.run(cmd,check=True,timeout=120)
 actual=probe(video);f=actual['frames'];assert len(actual['streams'])==1 and len(f)==158 and all((v['width'],v['height'])==(1152,768) and abs(float(v['best_effort_timestamp_time'])-i/24)<1e-6 for i,v in enumerate(f))
 before=hashes(original,'scale=1152:768:flags=lanczos,setsar=1');after=hashes(video);assert after==[before[i] for i in mapping]
 p=inputs/f'source_{source}_provenance.json';put(p,{'schema':'r74-flexiact-source-preparation-v1','source_id':source,'selection_sha256':sha(R/'design/FIXED_8_CANDIDATES.json'),'original_source':row['source_asset'],'source_original_sha256':sha(original),'video_sha256':sha(video),'command':cmd,'geometry':{'source':[720,480],'scaled':[1152,768],'crop':None},'frames':158,'fps':24,'valid_frame_count':147,'input_to_original':mapping,'evaluate_indices':list(range(0,147,3)),'evaluate_seconds':[i/8 for i in range(49)],'evaluate_fps':8,'terminal_padding_frames':11,'source_scaled_frame_md5':before,'input_frame_md5':after,'all158_decoded_frames_match_declared_source_exactly':True,'guide_position_bins_half_open':[0,44],'total_latent_bins':47,'guide_position_coverage_inclusive':[0,148],'pure_pad_bins':[44,45,46],'reference_audio_connected':False,'source_only_visual_review':source_notes[source]})
 sources[source]={'video':video.name,'video_sha256':sha(video),'original':original.name,'original_sha256':sha(original),'provenance':p.name,'provenance_sha256':sha(p)};print(source,'158-frame pixel identity PASS',flush=True)
shapes={};pairs=[]
for row in rows:
 source=row['source'];name=Path(row['target']).name;stem=Path(name).stem;pair=source+'__'+stem;target=inputs/('target_'+name);shutil.copy2(row['target_asset']['path'],target);assert sha(target)==row['target_asset']['sha256']
 with Image.open(target) as im:w,h=im.size
 scale=min(1.,math.sqrt(1152*768/(w*h)));tw=max(32,round(w*scale/32)*32);th=max(32,round(h*scale/32)*32)
 shape={'original_width_height':[w,h],'expected_native_ref_image_size_match_width_height':[tw,th],'expected_clean_reference_latent_shape':[1,24,1,th//16,tw//16],'expected_DiT_visual_patch_tokens':tw//32*(th//32),'formula':'native nodes_minimax_h3.py:301-311; scale=min(1,sqrt(1152*768/(w*h))), axes rounded32; no portrait preprocessing'};shapes[target.name]=shape
 csvpath=SEL/'metadata'/f'flexiact_hf__benchmark__captions__human__{source}__crop.csv';csvcopy=R/'design/official_metadata'/csvpath.name;csvcopy.parent.mkdir(exist_ok=True);shutil.copy2(csvpath,csvcopy);source_caption=list(csv.DictReader(csvpath.open()))[0]['caption']
 val=SEL/'metadata'/f'flexiact_hf__benchmark__captions__human__{source}__val_image.csv';shutil.copy2(val,R/'design/official_metadata'/val.name)
 flags=[]
 if stem=='game_man_5':flags.append('Official target caption says cartoon monster; image shows red/gold armored humanoid. P1 follows visible target identity.')
 if pair=='crouch__movie_man_5':flags.append('Official target caption describes resistance-machine exercise; original video and official source caption show squats. P1 follows source squat action; original target caption retained here.')
 if pair=='crouch__movie_man_9':flags.append('Original fixed8 metadata_flag wrongly flags resistance-machine caption; this row official_target_caption already says squats. Preserve original flag as ancestry, corrected by reading row.')
 if stem=='game_man_4':flags.append('P1 binds visible dark-haired anime man in green cape; official brown-coat wording retained in ancestry. No added anatomy/appearance.')
 fields={'target_identity':identities[stem],'source_caption':source_caption,'target_action':actions[source]};prompt=(R/'design/P1_TEMPLATE.txt').read_text().format(**fields);pf=R/'configs/prompts'/f'{pair}.txt';pf.parent.mkdir(parents=True,exist_ok=True);pf.write_text(prompt)
 pairs.append({'pair_key':pair,'motion_source_id':source,'candidate_id':row['candidate_id'],'identity':row['target'],'group':'official_csv_identity_generalization','original_pair_id':row['candidate_id'],'official_csv_row_zero_based':row['csv_row_zero_based'],'official_target_caption':row['official_caption'],'original_metadata_flag':row['metadata_flag'],'caption_review':flags,'source_asset':row['source_asset'],'target_asset':row['target_asset'],'source':sources[source],'portrait':target.name,'portrait_sha256':sha(target),'source_is_new_motion_content':False,'target_pair_previously_generated_at_selection':False,'reference_image_expected':shape,'p1_fields':fields,'prompt_file':str(pf.relative_to(R)),'prompt_sha256':sha(pf),'prompt':prompt})
put(R/'design/PAIR_DEFINITIONS.json',{'schema':'r74-six-remaining-official-flex-pairs-v1','selection_sha256':sha(R/'design/FIXED_8_CANDIDATES.json'),'excluded_R72':['fitness__game_man_5','one_leg__movie_man_9'],'pairs':pairs,'prompt_policy':'R72 P1 structured reference-generation; Picture1 appearance+scene, Video1 full motion/timing; official source caption and visually verified target identity. Complete official target captions retained as ancestry; mismatches recorded before generation. Both Native and forced use exact same P1.'})
put(R/'design/EXPECTED_SHAPES.json',{'reference_images':shapes,'geometry':{'width':1152,'height':768,'frames':158,'fps':24},'target_video_latent':[1,24,47,48,72],'target_audio_latent':[1,32,2,263]})
put(R/'configs/prompt_ancestry.json',{'parent':'R72 P1','pair_definitions_sha256':sha(R/'design/PAIR_DEFINITIONS.json'),'p1_template_sha256':sha(R/'design/P1_TEMPLATE.txt'),'official_guide_sha256':sha(R/'design/official_ref-en.txt'),'official_guide_commit':'d21241f0a4b3acbb34c97dae47fa417b7065e438'})
put(R/'configs/input_hashes.json',{p.name:sha(p) for p in sorted(inputs.iterdir())})
print(json.dumps({p['pair_key']:p['reference_image_expected'] for p in pairs},indent=2))
