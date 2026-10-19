from pathlib import Path
import fcntl, subprocess, json, hashlib
from PIL import Image, ImageDraw
root=Path(__file__).resolve().parents[1];batch=root/'analysis/postrun/captured/batch';out=root/'analysis/root_transition_preview';out.mkdir(exist_ok=True)
lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
paths=[batch/'input/source_49617_video.mp4',batch/'output/r31_source_49617_seed2026101701_native_00001_.mp4',batch/'output/r31_source_49617_seed2026101702_native_00001_.mp4']
frames=[24,28,32,36,40,44];width,height=576,324
cols=[]
for p in paths:
 filt='select='+ '+'.join('eq(n\\,%d)'%i for i in frames)+',scale=%d:%d'%(width,height)
 raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',str(p),'-vf',filt,'-fps_mode','vfr','-filter_threads','1','-pix_fmt','rgb24','-f','rawvideo','-'])
 assert len(raw)==len(frames)*width*height*3
 cols.append([Image.frombytes('RGB',(width,height),raw[i*width*height*3:(i+1)*width*height*3]) for i in range(len(frames))])
canvas=Image.new('RGB',(width*3,(height+24)*len(frames)),'black');d=ImageDraw.Draw(canvas)
for row,f in enumerate(frames):
 for c,lab in enumerate(['Source','Native seed1701','Native seed1702']):
  y=row*(height+24);d.text((c*width+8,y+4),f'{lab} | frame {f} | {f/24:.3f}s',fill='white');canvas.paste(cols[c][row],(c*width,y+24))
canvas.save(out/'frames24_28_32_36_40_44.png')
(out/'MANIFEST.json').write_text(json.dumps({'frames':frames,'input_files':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths],'output':'frames24_28_32_36_40_44.png','same_frame_indices':True,'image_scale_only':True},indent=2))
print(out/'frames24_28_32_36_40_44.png')
