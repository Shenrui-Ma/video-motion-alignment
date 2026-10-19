"""Same-frame R85 display; Pillow caption pattern inherited from R73."""
import argparse,io,shutil,subprocess,time
from PIL import Image,ImageDraw,ImageFont
from common import *
LABELS=('1.参考视频','2.普通编辑','3.时序引导')
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

def caption_strip(font):
 im=Image.new('RGB',(3456,88),'black');draw=ImageDraw.Draw(im);big=ImageFont.truetype(str(font),32);small=ImageFont.truetype(str(font),22)
 draw.text((14,8),'角色替换',fill='white',font=small)
 for col,label in enumerate(LABELS):draw.text((col*1152+(1152-draw.textlength(label,font=big))/2,42),label,font=big,fill='white')
 return im

def command(inputs,caption,destination,count,ffmpeg):
 require(count in (48,147),'display length not preregistered')
 cmd=[ffmpeg,'-v','error','-nostdin','-n']
 for p in inputs:cmd+=['-threads','2','-i',str(p)]
 cmd+=['-framerate','24','-loop','1','-i',str(caption)]
 filters=[f'[{i}:v]trim=start_frame=0:end_frame={count},setpts=PTS-STARTPTS,setsar=1[v{i}]' for i in range(3)]
 filters+=['[v0][v1][v2]hstack=inputs=3:shortest=1[images]','[images][3:v]vstack=inputs=2:shortest=1[out]']
 return cmd+['-filter_complex',';'.join(filters),'-map','[out]','-frames:v',str(count),'-an','-fps_mode','vfr','-c:v','libx264','-crf','17','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(destination)]

def render(pair,ffmpeg,ffprobe,font):
 validate_static();verify_intake(pair);p=pair_info(pair);incoming=ROOT/'incoming'/pair;paths=[ROOT/p['source']['file'],incoming/'native.mp4',incoming/'forced.mp4']
 require(sha(paths[0])==p['source']['sha256'],'source pixels changed')
 infos=[media_info(path,ffprobe) for path in paths]
 for info in infos:check_time(info,158,1152,768)
 parent=ROOT/'showcase';parent.mkdir(exist_ok=True);dest=parent/pair;require(not dest.exists(),'presentation already exists')
 staging=ROOT/'audit/render_staging'/f'{pair}_{time.time_ns()}';staging.mkdir(parents=True)
 caption=staging/'caption.png';caption_strip(font).save(caption);videos=[]
 for name,count in [('full_valid',147),('first2seconds',48)]:
  file=staging/(name+'.mp4');cmd=command(paths,caption,file,count,ffmpeg);subprocess.run(cmd,check=True,timeout=420)
  info=media_info(file,ffprobe);check_time(info,count,3456,856)
  videos.append({'name':name,'file':name+'.mp4','sha256':sha(file),'frame_interval_inclusive':[0,count-1],'fps':24,'properties':info,'command':cmd})
 frames=[0,24,48,72,108,144];im=Image.new('RGB',(1728,6*430),'black');draw=ImageDraw.Draw(im);ft=ImageFont.truetype(str(font),19)
 for row,frame in enumerate(frames):
  for col,path in enumerate(paths):
   data=subprocess.check_output([ffmpeg,'-v','error','-threads','1','-i',str(path),'-vf',f'select=eq(n\\,{frame}),scale=576:384:flags=lanczos','-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','-'],timeout=90)
   im.paste(Image.open(io.BytesIO(data)).convert('RGB'),(col*576,row*430));label=LABELS[col];draw.text((col*576+(576-draw.textlength(label,font=ft))/2,row*430+404),label,font=ft,fill='white')
  draw.text((8,row*430+386),f'{frame/24:.3f}s',font=ImageFont.truetype(str(font),14),fill='#bbb')
 im.save(staging/'six_times.jpg',quality=94)
 save(staging/'PRESENTATION.json',{'schema':'r85-same-physical-frame-presentation-v1','pair':pair,'gate':bound(incoming/'PAIR_RUNTIME_GATE.json'),'collection':bound(incoming/'COLLECTION.json'),'inputs':[bound(x) for x in paths],'original_media':infos,'target':p['target'],'prompt_version':p['prompt_version'],'method':'fixed mass-preserving routing, zero-based denoising steps6..14, alpha1, all50blocks; online_observer=false','videos':videos,'six_times':{'file':'six_times.jpg','sha256':sha(staging/'six_times.jpg'),'physical_frame_indices':frames},'source_temporal_resolution':'49 original frames@8fps repeated3 times to24fps; 147 valid frames displayed; final11pad frames retained only in original158 archive','fixed_denominator':3})
 staging.rename(dest);return bound(dest/'PRESENTATION.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--pair',choices=PAIRS,required=True);p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--ffprobe',default='ffprobe');p.add_argument('--font');a=p.parse_args();print(json.dumps(render(a.pair,a.ffmpeg,a.ffprobe,choose_font(a.font))))
