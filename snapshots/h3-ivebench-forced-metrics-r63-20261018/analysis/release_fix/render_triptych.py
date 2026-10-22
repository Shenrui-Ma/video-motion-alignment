from pathlib import Path
import hashlib,json,subprocess
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[2]
inputs=[root/'inputs/source_scores/short_0210/source_score.mp4',root/'prepared/short_0210/native_score.mp4',root/'prepared/short_0210/forced_score.mp4']
output=Path('/Users/researcher/Downloads/R63_IVEBench_0210_三组同帧对比_20261018.mp4')
font='/System/Library/Fonts/STHeiti Light.ttc'
caption=Image.new('RGB',(3840,88),'black');draw=ImageDraw.Draw(caption);f=ImageFont.truetype(font,32)
for i,label in enumerate(['1.参考视频','2.编辑后视频','3.编辑＋时序引导后视频']):
 box=draw.textbbox((0,0),label,font=f);draw.text((1280*i+(1280-(box[2]-box[0]))/2,26),label,font=f,fill='white')
draw.text((24,31),'角色替换',font=ImageFont.truetype(font,25),fill='white')
cp=Path(__file__).parent/'caption_0210.png';caption.save(cp)
cmd=['/opt/homebrew/bin/ffmpeg','-v','error','-nostdin','-n']
for p in inputs:cmd+=['-threads','2','-i',str(p)]
cmd+=['-loop','1','-framerate','24','-i',str(cp),'-filter_complex','[0:v]setsar=1[a];[1:v]setsar=1[b];[2:v]setsar=1[c];[a][b][c]hstack=inputs=3:shortest=1[top];[top][3:v]vstack=inputs=2:shortest=1[out]','-map','[out]','-an','-frames:v','87','-vsync','0','-c:v','libx264','-crf','17','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(output)]
subprocess.run(cmd,check=True,timeout=240)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(output)],text=True));assert (probe['streams'][0]['width'],probe['streams'][0]['height'])==(3840,808);times=[float(f['best_effort_timestamp_time']) for f in probe['frames']];assert len(times)==87 and all(abs(t-i/24)<1e-6 for i,t in enumerate(times))
bound=lambda p:{'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
record={'passed':True,'input':list(map(bound,inputs)),'output':bound(output),'frames':87,'seconds':[0,86/24],'fps':24,'column_width':1280,'caption_height':88,'command':cmd,'numerical_frame_offsets':[0,0,0]}
(Path(__file__).parent/'PRESENTATION_0210.json').write_text(json.dumps(record,indent=2)+'\n');print(str(output))
