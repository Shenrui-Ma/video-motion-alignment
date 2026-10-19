"""Same-index source/Native/guided display from actual paired evidence."""
import argparse,base64,html,subprocess,time
from PIL import Image,ImageDraw,ImageFont
from common import *
LABELS=('1.参考视频','2.普通编辑','3.时序引导')
def media_info(path,ffprobe):
 d=json.loads(subprocess.check_output([ffprobe,'-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(path)],timeout=90));require(len(d['streams'])==1,'video stream count differs');s=d['streams'][0];s['pts_s']=[float(x['best_effort_timestamp_time']) for x in d['frames']];s['count']=len(s['pts_s']);return s

def check_time(s,count,width,height):
 require((s['width'],s['height'],s['count'])==(width,height,count),'actual geometry/framecount differs');require(s['avg_frame_rate']=='24/1','actual FPS differs')
 require(all(abs(t-i/24)<1e-6 for i,t in enumerate(s['pts_s'])),'actual PTS differs; preserve file for review')

def choose_font(path=None):
 choices=[Path(path)] if path else [Path('/System/Library/Fonts/STHeiti Light.ttc'),Path('/System/Library/Fonts/PingFang.ttc'),Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
 p=next((p for p in choices if p.is_file()),None);require(p is not None,'Chinese font missing');return p

def frame_indices(valid,n):
 require(valid>=n>=2,'not enough valid frames');return [round(i*(valid-1)/(n-1)) for i in range(n)]

def caption_strip(font):
 im=Image.new('RGB',(3840,88),'black');d=ImageDraw.Draw(im);f=ImageFont.truetype(str(font),32)
 d.text((14,8),'角色替换',font=ImageFont.truetype(str(font),22),fill='white')
 for col,label in enumerate(LABELS):d.text((col*1280+(1280-d.textlength(label,font=f))/2,42),label,font=f,fill='white')
 return im

def command(inputs,caption,out,valid,ffmpeg):
 require(len(inputs)==3,'paired display must have three columns');require(valid>0,'invalid prefix')
 cmd=[ffmpeg,'-v','error','-nostdin','-n']
 for p in inputs:cmd+=['-threads','2','-i',str(p)]
 cmd+=['-framerate','24','-loop','1','-i',str(caption)]
 fs=[f'[{i}:v]crop=1280:720:16:8,trim=start_frame=0:end_frame={valid},setpts=PTS-STARTPTS,setsar=1[v{i}]' for i in range(3)]
 fs+=['[v0][v1][v2]hstack=inputs=3:shortest=1[images]','[images][3:v]vstack=inputs=2:shortest=1[out]']
 return cmd+['-filter_complex',';'.join(fs),'-map','[out]','-frames:v',str(valid),'-an','-fps_mode','vfr','-c:v','libx264','-crf','17','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(out)]

def render_files(inputs,staging,total,valid,font,ffmpeg,ffprobe,rows=(6,12)):
 require(len(inputs)==3 and 0<valid<=total,'invalid paired display scope');infos=[media_info(x,ffprobe) for x in inputs]
 for s in infos:check_time(s,total,1312,736)
 cap=staging/'caption.png';caption_strip(font).save(cap);out=staging/'source_native_guided_full_valid.mp4';cmd=command(inputs,cap,out,valid,ffmpeg);subprocess.run(cmd,check=True,timeout=420);props=media_info(out,ffprobe);check_time(props,valid,3840,808)
 raw=[];w,h=640,360
 for path in inputs:
  data=subprocess.check_output([ffmpeg,'-v','error','-threads','1','-i',str(path),'-vf',f'crop=1280:720:16:8,scale={w}:{h}:flags=lanczos','-frames:v',str(valid),'-f','rawvideo','-pix_fmt','rgb24','-threads','1','-'],timeout=120);require(len(data)==valid*w*h*3,'frame extraction differs');raw.append(data)
 sheets=[];f=ImageFont.truetype(str(font),22);sm=ImageFont.truetype(str(font),16)
 for n in rows:
  indices=frame_indices(valid,n);im=Image.new('RGB',(1920,n*406),'black');draw=ImageDraw.Draw(im)
  for row,ix in enumerate(indices):
   for col,data in enumerate(raw):
    im.paste(Image.frombytes('RGB',(w,h),data[ix*w*h*3:(ix+1)*w*h*3]),(col*w,row*406));label=LABELS[col];draw.text((col*w+(w-draw.textlength(label,font=f))/2,row*406+382),label,font=f,fill='white')
   draw.text((8,row*406+363),f'frame {ix} | {ix/24:.3f}s',font=sm,fill='#bbb')
  path=staging/f'{n}_times.jpg';im.save(path,quality=94);sheets.append({'file':path.name,'sha256':sha(path),'physical_frame_indices':indices})
 return {'original_media':infos,'videos':[{'file':out.name,'sha256':sha(out),'properties':props,'frame_interval_inclusive':[0,valid-1],'command':cmd}],'contact_sheets':sheets}

