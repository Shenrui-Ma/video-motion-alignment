"""R86 same-physical-frame display; common padding crop and valid prefixes only."""
import argparse,io,subprocess,time
from PIL import Image,ImageDraw,ImageFont
from common import *
LABELS=('1.参考视频','2.普通编辑','3.在线检测与时序引导')
def media_info(path,ffprobe='ffprobe'):
 cmd=[ffprobe,'-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(path)]
 d=json.loads(subprocess.check_output(cmd,timeout=90));require(len(d['streams'])==1,'video stream count differs');s=d['streams'][0];s['pts_s']=[float(f['best_effort_timestamp_time']) for f in d['frames']];s['count']=len(s['pts_s']);return s

def check_time(info,count,width,height):
 require((info['width'],info['height'],info['count'])==(width,height,count),'actual media geometry/count differs')
 require(info['avg_frame_rate']=='24/1','media FPS differs')
 require(all(abs(t-i/24)<1e-6 for i,t in enumerate(info['pts_s'])),'physical timestamps differ; preserve original and inspect separately')

def choose_font(value=None):
 choices=[Path(value)] if value else [Path('/System/Library/Fonts/STHeiti Light.ttc'),Path('/System/Library/Fonts/PingFang.ttc'),Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
 font=next((p for p in choices if p.is_file()),None);require(font is not None,'Chinese font required');return font

def caption_strip(font,labels=LABELS):
 im=Image.new('RGB',(3840,88),'black');draw=ImageDraw.Draw(im);big=ImageFont.truetype(str(font),32);small=ImageFont.truetype(str(font),22)
 draw.text((14,8),'视频编辑',fill='white',font=small)
 for col,label in enumerate(labels):draw.text((col*1280+(1280-draw.textlength(label,font=big))/2,42),label,font=big,fill='white')
 return im

def display_lengths(valid):
 require(type(valid) is int and valid>0,'invalid valid prefix')
 return [('full_valid',valid)]+([('first2seconds',48)] if valid>48 else [])

def six_frames(valid):return [round(i*(valid-1)/5) for i in range(6)]

def command(inputs,caption,destination,count,ffmpeg,valid):
 require(count in [v for _,v in display_lengths(valid)],'display length not preregistered')
 cmd=[ffmpeg,'-v','error','-nostdin','-n']
 for p in inputs:cmd+=['-threads','2','-i',str(p)]
 cmd+=['-framerate','24','-loop','1','-i',str(caption)]
 filters=[f'[{i}:v]crop=1280:720:16:8,trim=start_frame=0:end_frame={count},setpts=PTS-STARTPTS,setsar=1[v{i}]' for i in range(3)]
 filters+=['[v0][v1][v2]hstack=inputs=3:shortest=1[images]','[images][3:v]vstack=inputs=2:shortest=1[out]']
 return cmd+['-filter_complex',';'.join(filters),'-map','[out]','-frames:v',str(count),'-an','-fps_mode','vfr','-c:v','libx264','-crf','17','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(destination)]

