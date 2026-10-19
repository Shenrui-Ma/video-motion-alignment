from pathlib import Path
import fcntl,json,hashlib,subprocess,time,shutil
root=Path(__file__).resolve().parent;p=json.loads((root/'design/PROTOCOL.json').read_text());freeze=json.loads((root/'design/FREEZE.json').read_text())
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
for f,h in freeze['files'].items():assert sha(root/'design'/f)==h
lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
out=root/'inputs';out.mkdir(exist_ok=True)
portrait=Path('/Users/researcher/DevProjects/h3-timing-karate-native-r31-20261017/inputs/source_49617_portrait.jpg');assert sha(portrait)=='4231440d7d8c8305b5f1bdd497ad699fee30e07443ba8ee681cedd19c1a7da42'
allrows=[]
for row in p['cases']:
 src=Path(row['source_file']);assert sha(src)==row['source_sha256'];dst=out/f'source_{row["id"]}_video.mp4';assert not dst.exists()
 cmd=['/opt/homebrew/bin/ffmpeg','-nostdin','-v','error','-threads','2','-i',str(src),'-vf',p['prepare_filter'],'-an','-r','24','-fps_mode','cfr','-c:v','libx264','-crf','18','-preset','fast','-threads','2','-filter_threads','1','-pix_fmt','yuv420p','-movflags','+faststart',str(dst)]
 t=time.time();subprocess.run(cmd,check=True,timeout=90)
 probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','frame=best_effort_timestamp_time:stream=width,height,nb_frames,avg_frame_rate,duration','-of','json',str(dst)]));stream=probe['streams'][0]
 assert (stream['width'],stream['height'],int(stream['nb_frames']),stream['avg_frame_rate'])==(1312,736,141,'24/1');assert len(probe['frames'])==141
 assert all(abs(float(x['best_effort_timestamp_time'])-i/24)<1e-5 for i,x in enumerate(probe['frames']))
 photo=out/f'source_{row["id"]}_portrait.jpg';shutil.copy2(portrait,photo)
 record={'source_id':row['id'],'source_path':str(src),'source_sha256':sha(src),'prepared_sha256':sha(dst),'portrait_sha256':sha(photo),'command':cmd,'source_selection':row,'design_freeze_sha256':sha(root/'design/FREEZE.json'),'script_sha256':sha(__file__),'probe':probe,'wall_seconds':time.time()-t,'no_GPU':True,'generated_output_used_to_select':False}
 prov=out/f'source_{row["id"]}_provenance.json';prov.write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n');allrows.append({'video':dst.name,'video_sha256':sha(dst),'portrait':photo.name,'portrait_sha256':sha(photo),'provenance':prov.name,'provenance_sha256':sha(prov)})
(root/'INPUTS_READY.json').write_text(json.dumps({'passed':True,'cases':allrows,'timestamp':time.time()},indent=2)+'\n');print(json.dumps(allrows))
