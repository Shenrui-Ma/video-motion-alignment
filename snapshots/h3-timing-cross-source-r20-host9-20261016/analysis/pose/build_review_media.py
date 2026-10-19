"""Evidence-only deterministic presentation and original playback audit; no GPU."""
import fcntl,hashlib,json,subprocess,time
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'analysis/pose/media'
FF='/opt/homebrew/bin/ffmpeg'; FP='/opt/homebrew/bin/ffprobe'
FRAMES=(60,63,81,105)
FONT='/System/Library/Fonts/STHeiti Light.ttc'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def run(cmd):return subprocess.run(cmd,check=True,capture_output=True)
def probe(p):
 return json.loads(run([FP,'-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','stream=width,height,r_frame_rate,avg_frame_rate,time_base,duration,nb_frames:frame=best_effort_timestamp_time,pkt_duration_time','-of','json',str(p)]).stdout)
def extract(p,n,out):
 run([FF,'-v','error','-y','-threads','2','-i',str(p),'-vf',f'select=eq(n\\,{n})','-vsync','0','-frames:v','1','-threads','2',str(out)])
def build():
 OUT.mkdir(exist_ok=True)
 meta=json.loads((ROOT/'analysis/pose/cpu_complete.json').read_text())
 runs=('r20_s07_native','r20_s07_full_6to14')
 vids=[ROOT/'inputs/07_real_ary_v.mp4']+[ROOT/'analysis/pose/raw'/Path(meta['runs'][k]['video']).name for k in runs]
 expected=['46637cac9d2aba836b96962b0ffcd62607f15264d8bf81b0886e82c552666a11']+[meta['runs'][k]['sha256'] for k in runs]
 audit=[]
 for p,s in zip(vids,expected):
  if sha(p)!=s:raise ValueError('original SHA mismatch')
  a=probe(p);st=a['streams'][0];pts=[float(x['best_effort_timestamp_time']) for x in a['frames']]
  if not (st['width']==1312 and st['height']==736 and st['r_frame_rate']=='24/1' and st['avg_frame_rate']=='24/1' and st['time_base']=='1/12288' and len(pts)==141 and abs(float(st['duration'])-5.875)<1e-6):raise ValueError('playback geometry mismatch')
  if any(abs(t-i/24)>1e-6 for i,t in enumerate(pts)):raise ValueError('nonaligned physical PTS')
  audit.append({'file':str(p),'sha256':s,'probe':a})
 width=656;height=368;footer=76
 captions=('1.参考视频','2.编辑后：未干预','3.编辑后：同时间参考路由')
 ft=ImageFont.truetype(FONT,24);small=ImageFont.truetype(FONT,18)
 label=Image.new('RGB',(width*3,footer),'black');d=ImageDraw.Draw(label)
 for i,t in enumerate(captions):
  bbox=d.textbbox((0,0),t,font=ft);d.text((i*width+(width-(bbox[2]-bbox[0]))/2,7),t,font=ft,fill='white')
 d.text((20,44),'Sam Altman角色替换 | 24fps，同一物理时间，无动作对齐',font=small,fill='#c7c7c7')
 d.text((width*2+32,44),'仅采样索引6–14；视频主窗54–69帧',font=small,fill='#c7c7c7')
 label.save(OUT/'caption.png')
 for n in FRAMES:
  canvas=Image.new('RGB',(width*3,height+footer),'black')
  full=Image.new('RGB',(1312*3,736+2*footer),'black')
  for i,v in enumerate(vids):
   p=OUT/f'raw_frame{n:03d}_col{i}.png';extract(v,n,p)
   im=Image.open(p).convert('RGB');canvas.paste(im.resize((width,height),Image.Resampling.LANCZOS),(i*width,0));full.paste(im,(i*1312,0))
  canvas.paste(label,(0,height));canvas.save(OUT/f'frame{n:03d}_triptych.png')
  fl=label.resize((3936,2*footer),Image.Resampling.LANCZOS);full.paste(fl,(0,736));full.save(OUT/f'frame{n:03d}_triptych_fullres.png')
 base=[FF,'-v','error','-y','-filter_complex_threads','1']
 for v in vids:base+=['-threads','2','-i',str(v)]
 base+=['-loop','1','-i',str(OUT/'caption.png')]
 filt=';'.join([f'[{i}:v]setpts=PTS-STARTPTS,scale=656:368:flags=lanczos,setsar=1[v{i}]' for i in range(3)])+';[v0][v1][v2]hstack=inputs=3[top];[top][3:v]vstack=inputs=2:shortest=1[v]'
 fullvideo=OUT/'source07_native_full_full_length.mp4'
 run(base+['-filter_complex',filt,'-map','[v]','-an','-frames:v','141','-r','24','-c:v','libx264','-crf','17','-preset','medium','-pix_fmt','yuv420p','-threads','4','-movflags','+faststart',str(fullvideo)])
 clip=OUT/'source07_frames042_088_normal.mp4'
 run([FF,'-v','error','-y','-threads','2','-i',str(fullvideo),'-vf','trim=start_frame=42:end_frame=89,setpts=PTS-STARTPTS','-an','-r','24','-c:v','libx264','-crf','17','-preset','medium','-threads','4','-pix_fmt','yuv420p','-movflags','+faststart',str(clip)])
 slow=OUT/'source07_frames042_088_half_speed.mp4'
 run([FF,'-v','error','-y','-threads','2','-i',str(fullvideo),'-vf','trim=start_frame=42:end_frame=89,setpts=2*(PTS-STARTPTS)','-an','-r','12','-fps_mode','cfr','-c:v','libx264','-crf','17','-preset','medium','-threads','4','-pix_fmt','yuv420p','-movflags','+faststart',str(slow)])
 outputaudit={}
 for p,n,rate in ((fullvideo,141,'24/1'),(clip,47,'24/1'),(slow,47,'12/1')):
  a=probe(p)
  if len(a['frames'])!=n or a['streams'][0]['r_frame_rate']!=rate:raise ValueError('media frame/rate gate')
  outputaudit[p.name]={'sha256':sha(p),'bytes':p.stat().st_size,'probe':a}
 (OUT/'manifest.json').write_text(json.dumps({'originals':audit,'outputs':outputaudit,'fixed_frames':FRAMES,'fullfield_scale':[656,368],'crop':None,'footer_height':footer,'lag_alignment':False,'frame_interpolation':False,'audio_in_composite':False,'original_audio_preserved_in_raw':True,'short_clip_frame_interval_inclusive':[42,88]},indent=2))
 pics=''.join(f'<figure><img src="frame{n:03d}_triptych.png"><figcaption>Frame {n} | {n/24:.3f}s</figcaption></figure>' for n in FRAMES)
 (OUT/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>R20 跨源视频检查</title><style>body{background:#111;color:#eee;font:17px sans-serif;max-width:1500px;margin:30px auto}video,img{width:100%;height:auto}figure{margin:25px 0}p{line-height:1.6}figcaption{color:#bbb}</style><h1>床边舞：参考 / 未干预 / 同时间参考路由</h1><p>这是已看过档案中的第二开发案例，不是未见测试集。主窗为54–69帧；观察原画面、身份、背景和肢体重影，时序指标另见分析报告。各列同物理时间起点，保留完整画幅，无帧插值、无延迟补偿。方法启用的6–14是零起始采样索引，不是视频帧。</p><h2>完整5.875秒，正常速度</h2><video controls loop src="source07_native_full_full_length.mp4"></video><h2>42–88帧，正常速度</h2><video controls loop src="source07_frames042_088_normal.mp4"></video><h2>同一片段，半速</h2><video controls loop src="source07_frames042_088_half_speed.mp4"></video>'''+pics)
 print(json.dumps({'passed':True,'output':str(OUT),'original_PTS_frames':141,'time':time.time()}))
if __name__=='__main__':
 lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a')
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 build()
