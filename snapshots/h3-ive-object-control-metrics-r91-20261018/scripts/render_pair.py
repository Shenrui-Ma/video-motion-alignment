"""R91 same-physical-frame display; common padding crop and valid prefixes only."""
import argparse,io,subprocess,time
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
 im=Image.new('RGB',(3840,88),'black');draw=ImageDraw.Draw(im);big=ImageFont.truetype(str(font),32);small=ImageFont.truetype(str(font),22)
 draw.text((14,8),'视频编辑',fill='white',font=small)
 for col,label in enumerate(LABELS):draw.text((col*1280+(1280-draw.textlength(label,font=big))/2,42),label,font=big,fill='white')
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

def render(pair,ffmpeg,ffprobe,font):
 validate_static();verify_intake(pair);p=pair_info(pair);incoming=ROOT/'incoming'/pair;paths=[ROOT/p['source']['file'],incoming/'native.mp4',incoming/'forced.mp4']
 require(sha(paths[0])==p['source']['sha256'],'source pixels changed');infos=[media_info(path,ffprobe) for path in paths]
 for info in infos:check_time(info,p['geometry']['frames'],1312,736)
 parent=ROOT/'showcase';parent.mkdir(exist_ok=True);dest=parent/pair;require(not dest.exists(),'presentation already exists')
 staging=ROOT/'audit/render_staging'/f'{pair}_{time.time_ns()}';staging.mkdir(parents=True)
 caption=staging/'caption.png';caption_strip(font).save(caption);videos=[];valid=p['valid_frames']
 for name,count in display_lengths(valid):
  file=staging/(name+'.mp4');cmd=command(paths,caption,file,count,ffmpeg,valid);subprocess.run(cmd,check=True,timeout=420)
  info=media_info(file,ffprobe);check_time(info,count,3840,808)
  videos.append({'name':name,'file':name+'.mp4','sha256':sha(file),'frame_interval_inclusive':[0,count-1],'fps':24,'properties':info,'command':cmd})
 frames=six_frames(valid);im=Image.new('RGB',(1440,6*316),'black');draw=ImageDraw.Draw(im);ft=ImageFont.truetype(str(font),18)
 for row,frame in enumerate(frames):
  for col,path in enumerate(paths):
   data=subprocess.check_output([ffmpeg,'-v','error','-threads','1','-i',str(path),'-vf',f'select=eq(n\\,{frame}),crop=1280:720:16:8,scale=480:270:flags=lanczos','-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','-'],timeout=90)
   im.paste(Image.open(io.BytesIO(data)).convert('RGB'),(col*480,row*316));label=LABELS[col];draw.text((col*480+(480-draw.textlength(label,font=ft))/2,row*316+290),label,font=ft,fill='white')
  draw.text((8,row*316+272),f'frame {frame} | {frame/24:.3f}s',font=ImageFont.truetype(str(font),13),fill='#bbb')
 im.save(staging/'six_times.jpg',quality=94)
 # Use the first actual comparison frame as the browser poster.
 subprocess.run([ffmpeg,'-v','error','-threads','1','-i',str(staging/'full_valid.mp4'),'-frames:v','1','-threads','1','-q:v','2',str(staging/'poster.jpg')],check=True,timeout=90)
 save(staging/'PRESENTATION.json',{'schema':'r91-same-physical-frame-presentation-v1','pair':pair,'gate':bound(incoming/'PAIR_RUNTIME_GATE.json'),'collection':bound(incoming/'COLLECTION.json'),'inputs':[bound(x) for x in paths],'original_media':infos,'prompt_version':p['prompt_version'],'original_task':p['original_task'],'method':config()['method'],'videos':videos,'reference_image_used':False,'evaluation_scope':p['evaluation_scope'],'clip':p['clip'],'poster':{'file':'poster.jpg','sha256':sha(staging/'poster.jpg')},'six_times':{'file':'six_times.jpg','sha256':sha(staging/'six_times.jpg'),'physical_frame_indices':frames},'timeline':{'fps':24,'valid_frames':valid,'full_generated_frames':p['geometry']['frames'],'crop_xywh':p['evaluation_crop_xywh'],'original_frame_mapping':p['provenance'],'description':'Prepared24fps nearest-source-PTS mapping; identical same-index display; original and padded videos retained.'},'fixed_denominator':2})
 staging.rename(dest);return bound(dest/'PRESENTATION.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--pair',choices=PAIRS,required=True);p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--ffprobe',default='ffprobe');p.add_argument('--font');a=p.parse_args();print(json.dumps(render(a.pair,a.ffmpeg,a.ffprobe,choose_font(a.font))))
