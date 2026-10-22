from pathlib import Path
import json, subprocess, hashlib, math
from PIL import Image,ImageDraw,ImageFont
BASE=Path('/Users/researcher/DevProjects/h3-short-event-pilot-20261013')
FF='/opt/homebrew/bin/ffmpeg'
FONT=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',18)
def run(cmd): subprocess.run(cmd,check=True)
def sheet(video,start=0,end=107,step=1,name=None):
 raw=subprocess.check_output([FF,'-hide_banner','-loglevel','error','-i',str(video),'-vf','scale=328:184','-f','rawvideo','-pix_fmt','rgb24','-'])
 frames=[Image.frombytes('RGB',(328,184),raw[i:i+328*184*3]) for i in range(0,len(raw),328*184*3)]
 sel=list(range(start,min(end,len(frames)),step))
 for page in range(math.ceil(len(sel)/30)):
  ids=sel[page*30:(page+1)*30]; canvas=Image.new('RGB',(5*336,math.ceil(len(ids)/5)*212),'white');d=ImageDraw.Draw(canvas)
  for j,i in enumerate(ids):
   x=(j%5)*336;y=(j//5)*212;canvas.paste(frames[i],(x,y));d.text((x+3,y+186),f'frame {i:03d} | {i/24:.3f}s',font=FONT,fill='black')
  canvas.save(BASE/'source_candidates'/f'{name or video.stem}_frames_p{page+1}.jpg',quality=93)
 frames[0].save(video.with_suffix('.png'))
 return len(frames)
def prepare(n,start,out):
 src=BASE/'source_candidates'/f'mix_{n}.mp4'; dst=BASE/'inputs'/f'{out}.mp4'
 cmd=[FF,'-hide_banner','-loglevel','error','-y','-ss',str(start),'-i',str(src),'-vf','fps=24,scale=1312:736:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1312:736:(ow-iw)/2:(oh-ih)/2,setsar=1','-frames:v','107','-an','-c:v','libx264','-crf','16','-preset','fast','-pix_fmt','yuv420p',str(dst)]
 run(cmd); count=sheet(dst)
 meta={'clip_id':out,'source_id':n,'source_file':str(src),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'output_file':str(dst),'output_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'source_start_seconds':start,'output_frames':count,'output_fps':24,'duration_seconds':count/24,'width':1312,'height':736,'conversion_argv':cmd,'temporal_operation':'fps resampling only; no speed change; no interpolation; no concatenation','spatial_operation':'aspect-preserving scale and thin side padding; no crop'}
 (BASE/'inputs'/f'{out}.json').write_text(json.dumps(meta,indent=2))
 return meta
if __name__=='__main__': print(json.dumps(prepare(4837,7.0,'01_walk_look_up'),indent=2))
