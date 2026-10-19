"""Four equal panels preserving the 105 original valid frame times."""
import argparse,base64,html,subprocess,time
from PIL import Image,ImageDraw,ImageFont
from common import *

LABELS=('1.参考视频','2.普通编辑','3.固定引导 6–14','4.延长引导 6–19')
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
 im=Image.new('RGB',(5120,88),'black');d=ImageDraw.Draw(im);f=ImageFont.truetype(str(font),32)
 d.text((14,8),'角色 / 外观编辑',font=ImageFont.truetype(str(font),22),fill='white')
 for col,label in enumerate(LABELS):d.text((col*1280+(1280-d.textlength(label,font=f))/2,42),label,font=f,fill='white')
 return im

def command(inputs,caption,out,valid,ffmpeg):
 require(len(inputs)==4,'paired display must have exactly four columns');require(valid>0,'invalid prefix')
 cmd=[ffmpeg,'-v','error','-nostdin','-n']
 for p in inputs:cmd+=['-threads','2','-i',str(p)]
 cmd+=['-framerate','24','-loop','1','-i',str(caption)]
 fs=[f'[{i}:v]crop=1280:720:16:8,trim=start_frame=0:end_frame={valid},setpts=PTS-STARTPTS,setsar=1[v{i}]' for i in range(4)]
 fs+=['[v0][v1][v2][v3]hstack=inputs=4:shortest=1[images]','[images][4:v]vstack=inputs=2:shortest=1[out]']
 return cmd+['-filter_complex',';'.join(fs),'-map','[out]','-frames:v',str(valid),'-an','-fps_mode','vfr','-c:v','libx264','-crf','17','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(out)]

def render_files(inputs,staging,total,valid,font,ffmpeg,ffprobe,rows=(6,12)):
 require(len(inputs)==4 and 0<valid<=total,'invalid paired display scope');infos=[media_info(x,ffprobe) for x in inputs]
 for s in infos:check_time(s,total,1312,736)
 cap=staging/'caption.png';caption_strip(font).save(cap);out=staging/'source_native_fixed_extended_full_valid.mp4';cmd=command(inputs,cap,out,valid,ffmpeg);subprocess.run(cmd,check=True,timeout=420);props=media_info(out,ffprobe);check_time(props,valid,5120,808)
 raw=[];w,h=640,360
 for path in inputs:
  data=subprocess.check_output([ffmpeg,'-v','error','-threads','1','-i',str(path),'-vf',f'crop=1280:720:16:8,scale={w}:{h}:flags=lanczos','-frames:v',str(valid),'-f','rawvideo','-pix_fmt','rgb24','-threads','1','-'],timeout=120);require(len(data)==valid*w*h*3,'frame extraction differs');raw.append(data)
 sheets=[];f=ImageFont.truetype(str(font),22);sm=ImageFont.truetype(str(font),16)
 for n in rows:
  indices=frame_indices(valid,n);im=Image.new('RGB',(2560,n*406),'black');draw=ImageDraw.Draw(im)
  for row,ix in enumerate(indices):
   for col,data in enumerate(raw):
    im.paste(Image.frombytes('RGB',(w,h),data[ix*w*h*3:(ix+1)*w*h*3]),(col*w,row*406));label=LABELS[col];draw.text((col*w+(w-draw.textlength(label,font=f))/2,row*406+382),label,font=f,fill='white')
   draw.text((8,row*406+363),f'frame {ix} | {ix/24:.3f}s',font=sm,fill='#bbb')
  path=staging/f'{n}_times.jpg';im.save(path,quality=94);sheets.append({'file':path.name,'sha256':sha(path),'physical_frame_indices':indices})
 return {'original_media':infos,'videos':[{'file':out.name,'sha256':sha(out),'properties':props,'frame_interval_inclusive':[0,valid-1],'command':cmd}],'contact_sheets':sheets}
def publish(dest,output):
 m=read(dest/'PRESENTATION.json');c=config()
 require(m['columns']==['source','native','fixed','extended'],'four columns required')
 for v in m['videos']+m['contact_sheets']:require(sha(dest/v['file'])==v['sha256'],'rendered media changed')
 v=m['videos'][0];uri='data:video/mp4;base64,'+base64.b64encode((dest/v['file']).read_bytes()).decode()
 pictures=''.join('<details><summary>'+str(len(x['physical_frame_indices']))+'个同帧时刻</summary><img src="data:image/jpeg;base64,'+base64.b64encode((dest/x['file']).read_bytes()).decode()+'"></details>' for x in m['contact_sheets'])
 text=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>眼镜编辑 · 引导区间对照</title><style>body{{background:#111;color:#eee;font:17px system-ui;margin:24px auto;max-width:2400px;padding:0 16px}}video,img{{width:100%;height:auto}}h1{{font-size:26px}}p{{line-height:1.7}}details{{margin:18px 0}}pre{{white-space:pre-wrap;font:14px system-ui}}</style><h1>眼镜编辑：延长后期引导是否改善喝水动作的延后</h1><p>任务：给左侧持瓶男子戴上眼镜，保留原场景与喝水动作。四栏依次为参考视频、普通编辑、去噪步骤索引6–14固定引导、索引6–19延长引导。</p><video controls loop playsinline src="{uri}"></video><p>四栏展示相同的105个有效帧，24fps。普通编辑和固定引导沿用R89实际成片；新一版与固定引导的实际输入、初始噪声以及索引0–14的预测均通过逐位核验。延长区间同时增加了引导总次数，本项用于检查后段动作能否进一步恢复。</p>{pictures}<details><summary>实际编辑提示词</summary><pre>{html.escape(c['prompt'])}</pre></details><p>结论以完整动作顺序、喝水阶段和画面副作用的逐帧审阅为准，审阅结果单独归档。</p></html>'''
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);tmp=output.with_name(output.name+'.tmp');tmp.write_text(text);tmp.replace(output)
 return bound(output)

def render(ffmpeg,ffprobe,font,output):
 c=validate_static();verify_intake();dest=ROOT/'showcase'
 if not dest.exists():
  staging=ROOT/'audit/render_staging'/str(time.time_ns());staging.mkdir(parents=True)
  inputs=[Path(x['file']) for x in c['old_media']]+[ROOT/'incoming/extended.mp4']
  media=render_files(inputs,staging,c['total_frames'],c['valid_frames'],font,ffmpeg,ffprobe)
  save(staging/'PRESENTATION.json',{'schema':'r97-four-column-presentation-v1','source_id':c['source_id'],'columns':['source','native','fixed','extended'],'gate':bound(ROOT/'incoming/CONTROL_RUNTIME_GATE.json'),'collection':bound(ROOT/'incoming/COLLECTION.json'),'inputs':[bound(p) for p in inputs],'timeline':{'valid_frames':105,'total_frames':107,'fps':24,'crop_xywh':c['crop_xywh']},'comparison':'R89 fixed steps6..14 versus extended6..19; position and dose both change','quality_review':'PENDING full-frame review',**media})
  staging.rename(dest)
 else:require(read(dest/'PRESENTATION.json')['collection']['sha256']==sha(ROOT/'incoming/COLLECTION.json'),'render belongs to different intake')
 return {'presentation':bound(dest/'PRESENTATION.json'),'html':publish(dest,output)}

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--ffmpeg',default='/opt/homebrew/bin/ffmpeg');a.add_argument('--ffprobe',default='/opt/homebrew/bin/ffprobe');a.add_argument('--font');a.add_argument('--output',type=Path,required=True);x=a.parse_args();print(json.dumps(render(x.ffmpeg,x.ffprobe,choose_font(x.font),x.output)))
