"""Three equal same-time panels, with all 49 original motion timestamps on seven pages."""
import argparse,base64,html,mimetypes,shutil,subprocess,time
from PIL import Image,ImageDraw,ImageFont
from common import *
LABELS=('1.参考视频','2.普通编辑','3.时序引导')
def media_info(path,ffprobe):
 d=json.loads(subprocess.check_output([ffprobe,'-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(path)],timeout=90));require(len(d['streams'])==1,'one video stream required');s=d['streams'][0];s['pts_s']=[float(x['best_effort_timestamp_time']) for x in d['frames']];s['count']=len(s['pts_s']);return s

def check_time(s,count,width,height):
 require((s['width'],s['height'],s['count'])==(width,height,count),'actual media dimensions/count differ');require(s['avg_frame_rate']=='24/1','actual FPS differs');require(all(abs(t-i/24)<1e-6 for i,t in enumerate(s['pts_s'])),'physical PTS differ')

def choose_font(path=None):
 paths=[Path(path)] if path else [Path('/System/Library/Fonts/STHeiti Light.ttc'),Path('/System/Library/Fonts/PingFang.ttc'),Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
 selected=next((x for x in paths if x.is_file()),None);require(selected is not None,'Chinese font required');return selected

def caption_strip(font,width=1152):
 im=Image.new('RGB',(3*width,88),'black');d=ImageDraw.Draw(im);f=ImageFont.truetype(str(font),max(8,round(32*width/1152)))
 d.text((14,8),'角色替换',font=ImageFont.truetype(str(font),max(8,round(22*width/1152))),fill='white')
 for col,label in enumerate(LABELS):d.text((col*width+(width-d.textlength(label,font=f))/2,42),label,font=f,fill='white')
 return im

def command(inputs,caption,out,valid,ffmpeg):
 require(len(inputs)==3 and valid>0,'three actual columns and valid frames required');cmd=[ffmpeg,'-v','error','-nostdin','-n']
 for p in inputs:cmd+=['-threads','2','-i',str(p)]
 cmd+=['-framerate','24','-loop','1','-i',str(caption)]
 fs=[f'[{i}:v]trim=start_frame=0:end_frame={valid},setpts=PTS-STARTPTS,setsar=1[v{i}]' for i in range(3)]
 fs+=['[v0][v1][v2]hstack=inputs=3:shortest=1[images]','[images][3:v]vstack=inputs=2:shortest=1[out]']
 return cmd+['-filter_complex',';'.join(fs),'-map','[out]','-frames:v',str(valid),'-an','-fps_mode','vfr','-c:v','libx264','-crf','17','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(out)]

def page_indices():return [list(range(i,i+7)) for i in range(0,49,7)]

def render_files(inputs,staging,font,ffmpeg,ffprobe,width=1152,height=768,sample_width=576):
 require(len(inputs)==3,'three columns required');infos=[media_info(x,ffprobe) for x in inputs]
 for s in infos:check_time(s,158,width,height)
 cap=staging/'caption.png';caption_strip(font,width).save(cap);out=staging/'source_native_guided_full_valid.mp4';cmd=command(inputs,cap,out,147,ffmpeg);subprocess.run(cmd,check=True,timeout=420);props=media_info(out,ffprobe);check_time(props,147,width*3,height+88)
 w=sample_width;h=round(height*w/width);raw=[]
 for path in inputs:
  data=subprocess.check_output([ffmpeg,'-v','error','-threads','1','-i',str(path),'-vf',f'scale={w}:{h}:flags=lanczos','-frames:v','147','-f','rawvideo','-pix_fmt','rgb24','-threads','1','-'],timeout=120);require(len(data)==147*w*h*3,'actual extracted frame count differs');raw.append(data)
 sheets=[];font_main=ImageFont.truetype(str(font),max(8,round(19*w/576)));font_small=ImageFont.truetype(str(font),max(8,round(14*w/576)))
 for page,indices in enumerate(page_indices(),1):
  im=Image.new('RGB',(w*3,7*(h+46)),'black');draw=ImageDraw.Draw(im)
  for row,original in enumerate(indices):
   physical=3*original
   for col,data in enumerate(raw):
    im.paste(Image.frombytes('RGB',(w,h),data[physical*w*h*3:(physical+1)*w*h*3]),(col*w,row*(h+46)))
    label=LABELS[col];draw.text((col*w+(w-draw.textlength(label,font=font_main))/2,row*(h+46)+h+24),label,font=font_main,fill='white')
   draw.text((8,row*(h+46)+h+3),f'{original}/48 | {original/8:.3f}s | frame {physical}',font=font_small,fill='#bbb')
  path=staging/f'original_times_page_{page:02d}.jpg';im.save(path,quality=94);sheets.append({'file':path.name,'sha256':sha(path),'original_frame_indices':indices,'physical_frame_indices':[3*i for i in indices]})
 poster=staging/'poster.jpg';subprocess.run([ffmpeg,'-v','error','-threads','1','-i',str(out),'-frames:v','1','-threads','1',str(poster)],check=True,timeout=90)
 return {'original_media':infos,'video':{'file':out.name,'sha256':sha(out),'properties':props,'frame_interval_inclusive':[0,146],'command':cmd},'contact_sheets':sheets,'poster':{'file':poster.name,'sha256':sha(poster)}}

def data_uri(path):return 'data:'+(mimetypes.guess_type(str(path))[0] or 'application/octet-stream')+';base64,'+base64.b64encode(Path(path).read_bytes()).decode()

def publish(dest,output):
 c=config();p=read(dest/'PRESENTATION.json')
 for row in [p['video'],p['poster']]+p['contact_sheets']:require(sha(dest/row['file'])==row['sha256'],'presentation changed')
 target=Path(c['media']['target']['file']);require(sha(target)==c['media']['target']['sha256'],'target changed');video=dest/p['video']['file']
 sheets=''.join(f'<details><summary>第{i}页 · 原动作帧 {s["original_frame_indices"][0]}–{s["original_frame_indices"][-1]}</summary><img class="sheet" src="{data_uri(dest/s["file"])}" alt="原动作时刻对照"></details>' for i,s in enumerate(p['contact_sheets'],1))
 document=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>俯卧支撑：普通编辑与时序引导</title><style>body{{margin:24px auto;padding:0 18px;max-width:2200px;background:#0b0c10;color:#eee;font:18px/1.6 system-ui}}h1{{font-size:29px}}video,.sheet{{display:block;width:100%;height:auto;background:black}}.reference{{display:flex;gap:24px;align-items:center;margin:22px 0}}.reference img{{max-width:320px;max-height:230px;object-fit:contain;background:white}}details{{margin:20px 0}}summary{{cursor:pointer}}pre{{white-space:pre-wrap;font:14px/1.5 monospace}}a{{color:#9bd2ff}}</style><h1>俯卧支撑：普通编辑与时序引导</h1><p>任务：使用目标图中的短黑发男性、绿披肩和棕外套，在白色背景中完成参考视频的低伏、撑起、伸背与拱背动作。</p><div class="reference"><img src="{data_uri(target)}" alt="实际人物参考图"><div>实际目标人物图<br>人物外观、白色背景与动作分别检查。</div></div><video controls playsinline preload="none" poster="{data_uri(dest/p['poster']['file'])}" src="{data_uri(video)}"></video><p>三栏依次为参考视频、普通编辑、时序引导。展示147个有效帧、24fps、6.125秒。原动作49帧、8fps，每帧重复3次，动作时间精度为125毫秒。</p><p>普通编辑为R98已完成版本；引导版使用相同提示词、参考素材和原始噪声，在去噪步骤6–14施加固定时序引导（α=1）。配对通过实际条件与干预前六步预测相等检查。</p><a download="H3_R101_参考_普通_引导_147帧_20261019.mp4" id="download-video">下载完整三栏视频</a><h2>49个原动作时刻</h2>{sheets}<details><summary>实际提示词与素材范围</summary><pre>{html.escape(c['prompt'])}</pre><p>{html.escape(c['scope'])}</p></details><script>document.getElementById("download-video").href=document.querySelector("video").src;</script></html>'''
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
 if output.exists():require(output.read_text()==document,'HTML differs from established artifact')
 else:output.write_text(document)
 mp4=output.with_name('H3_R101_参考_普通_引导_147帧_20261019.mp4')
 if mp4.exists():require(sha(mp4)==sha(video),'Downloads video conflict')
 else:shutil.copy2(video,mp4)
 import re
 videos=re.findall(r'data:video/mp4;base64,([A-Za-z0-9+/=]+)',document);require(len(videos)==1 and hashlib.sha256(base64.b64decode(videos[0])).hexdigest()==sha(video),'embedded video changed')
 require(document.count('class="sheet"')==7 and 'file://' not in document and 'src="/' not in document,'embedded page structure differs')
 manifest={'schema':'r101-shareable-presentation-v1','html':bound(output),'download_video':bound(mp4),'presentation':bound(dest/'PRESENTATION.json'),'source_media':c['media'],'embedded_unique_videos':1,'embedded_video_instances':1,'contact_sheet_pages':7,'original_motion_frames':49,'UI_visual_assessment':'Static layout, timeline and media byte validation; no browser access.'}
 manifest_path=output.with_suffix('.json')
 if manifest_path.exists():require(read(manifest_path)==manifest,'published manifest differs')
 else:save(manifest_path,manifest)
 return manifest

def render(ffmpeg,ffprobe,font,output):
 c=validate_static();g=verify_intake();dest=ROOT/'showcase'
 if not dest.exists():
  staging=ROOT/'audit/render_staging'/str(time.time_ns());staging.mkdir(parents=True)
  inputs=[Path(c['media']['source']['file']),Path(c['media']['native']['file']),ROOT/'incoming/forced.mp4'];media=render_files(inputs,staging,font,ffmpeg,ffprobe)
  save(staging/'PRESENTATION.json',{'schema':'r101-matched-fixed-guidance-presentation-v1','columns':c['columns'],'gate':bound(ROOT/'incoming/PAIR_RUNTIME_GATE.json'),'collection':bound(ROOT/'incoming/COLLECTION.json'),'inputs':[bound(x) for x in inputs],'target':c['media']['target'],'valid_frames':147,'fps':24,'guidance_routed_calls':[0,450],'method':c['method'],'quality_review':'PENDING',**media});staging.rename(dest)
 else:require(read(dest/'PRESENTATION.json')['collection']['sha256']==sha(ROOT/'incoming/COLLECTION.json'),'presentation belongs to different attempt')
 return publish(dest,output)
