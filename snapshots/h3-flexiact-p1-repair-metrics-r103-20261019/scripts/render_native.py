"""Same-index source/Native display. No guided column or synthetic outcome."""
import argparse,base64,html,subprocess,time
from PIL import Image,ImageDraw,ImageFont
from common import *
LABELS=('1.参考视频','2.普通编辑')
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
 im=Image.new('RGB',(2304,88),'black');d=ImageDraw.Draw(im);f=ImageFont.truetype(str(font),32)
 d.text((14,8),'普通编辑预览 · Native-only',font=ImageFont.truetype(str(font),22),fill='white')
 for col,label in enumerate(LABELS):d.text((col*1152+(1152-d.textlength(label,font=f))/2,42),label,font=f,fill='white')
 return im

def command(inputs,caption,out,valid,ffmpeg):
 require(len(inputs)==2,'Native-only must have exactly two columns');require(valid>0,'invalid prefix')
 cmd=[ffmpeg,'-v','error','-nostdin','-n']
 for p in inputs:cmd+=['-threads','2','-i',str(p)]
 cmd+=['-framerate','24','-loop','1','-i',str(caption)]
 fs=[f'[{i}:v]crop=1152:768:0:0,trim=start_frame=0:end_frame={valid},setpts=PTS-STARTPTS,setsar=1[v{i}]' for i in range(2)]
 fs+=['[v0][v1]hstack=inputs=2:shortest=1[images]','[images][2:v]vstack=inputs=2:shortest=1[out]']
 return cmd+['-filter_complex',';'.join(fs),'-map','[out]','-frames:v',str(valid),'-an','-fps_mode','vfr','-c:v','libx264','-crf','17','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(out)]

def render_files(inputs,staging,total,valid,font,ffmpeg,ffprobe,rows=(6,12)):
 require(len(inputs)==2 and 0<valid<=total,'invalid Native display scope');infos=[media_info(x,ffprobe) for x in inputs]
 for s in infos:check_time(s,total,1152,768)
 cap=staging/'caption.png';caption_strip(font).save(cap);out=staging/'source_native_full_valid.mp4';cmd=command(inputs,cap,out,valid,ffmpeg);subprocess.run(cmd,check=True,timeout=420);props=media_info(out,ffprobe);check_time(props,valid,2304,856)
 raw=[];w,h=576,384
 for path in inputs:
  data=subprocess.check_output([ffmpeg,'-v','error','-threads','1','-i',str(path),'-vf',f'crop=1152:768:0:0,scale={w}:{h}:flags=lanczos','-frames:v',str(valid),'-f','rawvideo','-pix_fmt','rgb24','-threads','1','-'],timeout=120);require(len(data)==valid*w*h*3,'frame extraction differs');raw.append(data)
 sheets=[];f=ImageFont.truetype(str(font),22);sm=ImageFont.truetype(str(font),16)
 for n in rows:
  indices=frame_indices(valid,n);im=Image.new('RGB',(1152,n*430),'black');draw=ImageDraw.Draw(im)
  for row,ix in enumerate(indices):
   for col,data in enumerate(raw):
    im.paste(Image.frombytes('RGB',(w,h),data[ix*w*h*3:(ix+1)*w*h*3]),(col*w,row*430));label=LABELS[col];draw.text((col*w+(w-draw.textlength(label,font=f))/2,row*430+406),label,font=f,fill='white')
   draw.text((8,row*430+387),f'frame {ix} | {ix/24:.3f}s',font=sm,fill='#bbb')
  path=staging/f'{n}_times.jpg';im.save(path,quality=94);sheets.append({'file':path.name,'sha256':sha(path),'physical_frame_indices':indices})
 return {'original_media':infos,'videos':[{'file':out.name,'sha256':sha(out),'properties':props,'frame_interval_inclusive':[0,valid-1],'command':cmd}],'contact_sheets':sheets}

def publish(source,dest,output):
 m=read(dest/'PRESENTATION.json');p=info(source)
 require(m['mode']=='Native-only' and m['columns']==['source','native'],'presentation is not Native-only')
 for v in m['videos']+m['contact_sheets']:require(sha(dest/v['file'])==v['sha256'],'presentation media changed')
 video=m['videos'][0];uri='data:video/mp4;base64,'+base64.b64encode((dest/video['file']).read_bytes()).decode();task=html.escape(p.get('display_task',p['original_task']['edit_prompt']));prompt=html.escape(p['prompt'])
 portrait=ROOT/p['portrait']['file'];require(sha(portrait)==p['portrait']['sha256'],'portrait changed');portrait_uri='data:image/'+('webp' if portrait.suffix=='.webp' else 'jpeg')+';base64,'+base64.b64encode(portrait.read_bytes()).decode()
 pictures=''.join('<details><summary>'+str(len(x['physical_frame_indices']))+'个同帧时刻</summary><img src="data:image/jpeg;base64,'+base64.b64encode((dest/x['file']).read_bytes()).decode()+'"></details>' for x in m['contact_sheets'])
 text=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>R103 {source} 普通编辑预览 Native-only</title><style>body{{background:#111;color:#eee;font:17px system-ui;margin:28px auto;max-width:1700px;padding:0 16px}}video,img{{width:100%;height:auto}}h1{{font-size:25px}}p{{line-height:1.65}}details{{margin:16px 0}}pre{{white-space:pre-wrap;font:14px system-ui}}</style><h1>R103 {source} · 普通编辑预览（Native-only）</h1><p>任务：{task}</p><figure><img style="width:auto;max-width:260px;max-height:300px" src="{portrait_uri}"><figcaption>目标角色参考图（原始素材）</figcaption></figure><p>两栏为参考视频与普通编辑。展示完整有效{p['valid_frames']}帧、24fps，使用相同帧号与统一裁剪。完整生成{p['geometry']['frames']}帧另行归档。原始视频时间映射保存在 provenance。当前页面供检查编辑任务与动作；引导结果尚未纳入。</p><video controls loop playsinline src="{uri}"></video>{pictures}<details><summary>实际提示词</summary><pre>{prompt}</pre></details><p>FlexiAct 原素材，固定2个动作来源；本页仅展示这一条已通过实际Native门的普通编辑。完整实验分母及guide/skip由生产台账保留。</p></html>'''
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);tmp=output.with_name(output.name+'.tmp');tmp.write_text(text);tmp.replace(output);return bound(output)

def render(source,ffmpeg,ffprobe,font,output):
 validate_static();verify_intake(source);p=info(source);dest=ROOT/'showcase'/source
 if not dest.exists():
  staging=ROOT/'audit/render_staging'/f'{source}_{time.time_ns()}';staging.mkdir(parents=True);inputs=[ROOT/p['source']['file'],ROOT/'incoming'/source/'native.mp4'];media=render_files(inputs,staging,p['geometry']['frames'],p['valid_frames'],font,ffmpeg,ffprobe)
  save(staging/'PRESENTATION.json',{'schema':'r103-native-only-presentation-v1','source_id':source,'mode':'Native-only','columns':['source','native'],'gate':bound(ROOT/'incoming'/source/'NATIVE_RUNTIME_GATE.json'),'collection':bound(ROOT/'incoming'/source/'COLLECTION.json'),'inputs':[bound(x) for x in inputs],'timeline':{'fps':24,'valid_frames':p['valid_frames'],'total_frames':p['geometry']['frames'],'crop_xywh':p['crop_xywh'],'provenance':p['provenance']},'original_task':p['original_task'],'prompt_version':p['prompt_version'],'reference_image':p['portrait'],'reference_image_expected':p['reference_image_expected'],'fixed_source_denominator':2,'quality_review':'PENDING visual review','method':'普通编辑（Native）',**media});dest.parent.mkdir(exist_ok=True);staging.rename(dest)
 else:
  m=read(dest/'PRESENTATION.json');require(m['collection']['sha256']==sha(ROOT/'incoming'/source/'COLLECTION.json'),'render bound to different intake')
 return {'presentation':bound(dest/'PRESENTATION.json'),'html':publish(source,dest,output)}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--source',choices=SOURCES,required=True);a.add_argument('--ffmpeg',default='/opt/homebrew/bin/ffmpeg');a.add_argument('--ffprobe',default='/opt/homebrew/bin/ffprobe');a.add_argument('--font');a.add_argument('--output',type=Path,required=True);x=a.parse_args();print(json.dumps(render(x.source,x.ffmpeg,x.ffprobe,choose_font(x.font),x.output)))
