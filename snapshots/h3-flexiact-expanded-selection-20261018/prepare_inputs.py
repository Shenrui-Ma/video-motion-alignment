"""Local CPU preparation of frozen source-only selected official assets; no inference."""
from pathlib import Path
import json,subprocess,hashlib,shutil,time
R=Path(__file__).resolve().parent;OUT=R/'inputs';OUT.mkdir(exist_ok=True)
FFMPEG='/opt/homebrew/bin/ffmpeg';FFPROBE='/opt/homebrew/bin/ffprobe';OLD=Path('/Users/researcher/DevProjects/h3-timing-flexiact-native-r49-20261017')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def probe(p):return json.loads(subprocess.check_output([FFPROBE,'-v','error','-select_streams','v:0','-show_frames','-show_streams','-of','json',str(p)]))
def frame_hashes(p,vf=None):
 cmd=[FFMPEG,'-v','error','-threads','2','-i',str(p),'-map','0:v:0','-an']
 if vf:cmd+=['-vf',vf]
 cmd+=['-pix_fmt','yuv420p','-threads','2','-f','framemd5','-'];return [line.split(',')[-1].strip() for line in subprocess.check_output(cmd,text=True).splitlines() if line and not line.startswith('#')]
manifest=json.loads((R/'SELECTED_8_MANIFEST.json').read_text());freeze=json.loads((R/'SELECTION_FREEZE.json').read_text());assert sha(R/'SELECTED_8_MANIFEST.json')==freeze['manifest_sha256'];sources={p['action']:p['source'] for p in manifest['pairs']};targets={Path(p['target']['official_path']).name:p['target'] for p in manifest['pairs']};mapping=[min(i//3,48) for i in range(158)];prepared={}
for action,row in sources.items():
 start=time.monotonic();original=OUT/f'source_{action}_original.mp4';video=OUT/f'source_{action}_video.mp4';assert sha(row['local_path'])==row['official_lfs_sha256'];shutil.copy2(row['local_path'],original)
 raw=probe(original);assert len(raw['frames'])==49 and all((x['width'],x['height'])==(720,480) and abs(float(x['best_effort_timestamp_time'])-i/8)<1e-6 for i,x in enumerate(raw['frames']))
 if action in ['fitness','one_leg']:
  source=OLD/'inputs'/video.name;shutil.copy2(source,video);command=None;inherited={'file':str(source),'sha256':sha(source)}
 else:
  vf='scale=1152:768:flags=lanczos,fps=24:round=near,tpad=stop_mode=clone:stop=11,trim=end_frame=158,setpts=N/(24*TB),setsar=1'
  command=[FFMPEG,'-v','error','-threads','2','-i',str(original),'-map','0:v:0','-an','-vf',vf,'-c:v','libx264','-crf','0','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(video)];subprocess.run(command,check=True,timeout=90);inherited=None
 actual=probe(video);frames=actual['frames'];assert len(frames)==158 and all((x['width'],x['height'])==(1152,768) and abs(float(x['best_effort_timestamp_time'])-i/24)<1e-6 for i,x in enumerate(frames))
 source_hash=frame_hashes(original,'scale=1152:768:flags=lanczos,setsar=1');out_hash=frame_hashes(video);assert len(source_hash)==49 and out_hash==[source_hash[i] for i in mapping]
 prov={'schema':'flexiact-expanded-input-v1','source_id':action,'selection_manifest_sha256':freeze['manifest_sha256'],'source_original_sha256':sha(original),'video_sha256':sha(video),'official_source':row,'command':command,'inherited_prepared_source':inherited,'geometry':{'source':[720,480],'scaled':[1152,768],'crop':None},'frames':158,'fps':24,'valid_frame_count':147,'input_to_original':mapping,'evaluate_indices':[i*3 for i in range(49)],'evaluate_seconds':[i/8 for i in range(49)],'evaluate_fps':8,'terminal_padding_frames':11,'source_scaled_frame_md5':source_hash,'input_frame_md5':out_hash,'all158_decoded_frames_match_declared_source_exactly':True,'guide_position_bins_half_open':[0,44],'total_latent_bins':47,'guide_position_coverage_inclusive':[0,148],'pure_pad_bins':[44,45,46],'reference_audio_connected':False,'elapsed_seconds':time.monotonic()-start,'inference_observed':False};path=OUT/f'source_{action}_provenance.json';put(path,prov);prepared[action]={'video':str(video),'video_sha256':sha(video),'original':str(original),'original_sha256':sha(original),'provenance':str(path),'provenance_sha256':sha(path)};print(action,'PASS',flush=True)
for name,row in targets.items():
 target=OUT/('target_'+name);shutil.copy2(row['local_path'],target);assert sha(target)==row['official_lfs_sha256'];row['prepared_local_path']=str(target);row['prepared_sha256']=sha(target)
shutil.copy2(R/'H3_PROMPT.txt',OUT/'prompt.txt')
entries=[]
for p in manifest['pairs']:
 target=targets[Path(p['target']['official_path']).name];entries.append({'pair_id':p['pair_id'],'group':p['group'],'action':p['action'],'source_is_new_motion_content':p['source_is_new_motion_content'],'source':prepared[p['action']],'target':target,'prompt_file':str(OUT/'prompt.txt'),'prompt_sha256':sha(OUT/'prompt.txt'),'prompt_exact':p['h3_prompt_exact'],'official_metadata_entry':'SELECTED_8_MANIFEST.json pairs matched by pair_id','geometry':{'width':1152,'height':768,'frames':158,'fps':24},'valid_frame_count':147,'evaluation_indices':[i*3 for i in range(49)],'evaluation_fps':8})
put(R/'PREPARED_8_PAIRS.json',{'schema':'flexiact-expanded-eight-pairs-ready-v1','status':'CPU_INPUTS_READY_NO_GPU','selection_sha256':freeze['manifest_sha256'],'source_count':len(sources),'new_source_count':3,'target_count':len(targets),'pair_count':len(entries),'pairs':entries})
