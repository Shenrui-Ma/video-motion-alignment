"""Fixed-time evidence presentation. Full fields, no retiming/interpolation."""
import fcntl,hashlib,json,subprocess,time
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'media'
OLD=ROOT.parent/'h3-timing-spatial-r3-20261016/analysis/pose/raw'
FF='/opt/homebrew/bin/ffmpeg';FP='/opt/homebrew/bin/ffprobe'
FRAMES=(55,86,105)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def run(a):return subprocess.run(a,check=True,capture_output=True)
def probe(p):return json.loads(run([FP,'-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','stream=width,height,avg_frame_rate,duration:frame=best_effort_timestamp_time','-of','json',str(p)]).stdout)
def build():
 if not read(HERE/'comparison/COMPARISON_COMPLETE.json')['passed']:raise ValueError('final comparison incomplete')
 b=read(HERE/'BINDING.json');videos=[ROOT/'inputs/05_real_megumi_v.mp4'];expected=[b['source_video_sha256']]
 labels=['参考视频','Native：未干预','正向 Full','反向 BLOCK','反向 SAME']
 for key in ('native','full'):
  p=b['parents'][key];videos.append(OLD/(p['run_id']+'_00001_.mp4'));expected.append(p['video_sha256'])
 for lane in ('reverse_block','reverse_same'):
  arc=HERE/'captured'/b['lanes'][lane]['run_id'];d=read(arc/'CPU_COMPLETE.json')
  if not read(arc/'PLAYBACK_GATE.json')['passed']:raise ValueError('download playback gate')
  videos.append(arc/'output'/Path(d['video']).name);expected.append(d['video_sha256'])
 originals=[]
 for v,s in zip(videos,expected):
  if sha(v)!=s:raise ValueError('original SHA mismatch')
  a=probe(v);z=a['streams'][0]
  if (z['width'],z['height'],z['avg_frame_rate'],len(a['frames']))!=(1312,736,'24/1',141):raise ValueError('geometry mismatch')
  if any(abs(float(f['best_effort_timestamp_time'])-i/24)>1e-6 for i,f in enumerate(a['frames'])):raise ValueError('physical time mismatch')
  originals.append({'file':str(v),'sha256':s,'probe':a})
 OUT.mkdir(exist_ok=True);w,h,footer=656,368,76;ft=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',24);small=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',18)
 caption=Image.new('RGB',(5*w,footer),'black');d=ImageDraw.Draw(caption)
 for i,label in enumerate(labels):
  text=f'{i+1}.{label}';bbox=d.textbbox((0,0),text,font=ft);d.text((i*w+(w-bbox[2]+bbox[0])/2,6),text,font=ft,fill='white')
 d.text((20,44),'角色替换 | 24fps，同帧排列 | Sam，已知开发案例',font=small,fill='#c7c7c7')
 d.text((2*w+20,44),'三个干预：采样索引6–14；物理事件50–65帧',font=small,fill='#c7c7c7');caption.save(OUT/'caption.png')
 for n in FRAMES:
  canvas=Image.new('RGB',(5*w,h+footer),'black');full=Image.new('RGB',(5*1312,736+2*footer),'black')
  for i,v in enumerate(videos):
   f=OUT/f'raw_frame{n:03d}_col{i}.png';run([FF,'-v','error','-y','-threads','2','-i',str(v),'-vf',f'select=eq(n\\,{n})','-vsync','0','-frames:v','1','-threads','2',str(f)])
   im=Image.open(f).convert('RGB');canvas.paste(im.resize((w,h),Image.Resampling.LANCZOS),(i*w,0));full.paste(im,(i*1312,0))
  canvas.paste(caption,(0,h));canvas.save(OUT/f'frame{n:03d}_comparison.png');full.paste(caption.resize((5*1312,2*footer),Image.Resampling.LANCZOS),(0,736));full.save(OUT/f'frame{n:03d}_comparison_fullres.png')
 args=[FF,'-v','error','-y','-filter_complex_threads','1']
 for v in videos:args+=['-threads','2','-i',str(v)]
 args+=['-loop','1','-i',str(OUT/'caption.png')]
 filt=';'.join(f'[{i}:v]setpts=PTS-STARTPTS,scale=656:368:flags=lanczos,setsar=1[v{i}]' for i in range(5))+';[v0][v1][v2][v3][v4]hstack=inputs=5[top];[top][5:v]vstack=inputs=2:shortest=1[v]'
 fullvideo=OUT/'source_native_forward_reverse_full_length.mp4'
 run(args+['-filter_complex',filt,'-map','[v]','-an','-frames:v','141','-r','24','-c:v','libx264','-crf','17','-preset','medium','-pix_fmt','yuv420p','-threads','4','-movflags','+faststart',str(fullvideo)])
 clip=OUT/'frames042_082_normal.mp4';run([FF,'-v','error','-y','-threads','2','-i',str(fullvideo),'-vf','trim=start_frame=42:end_frame=83,setpts=PTS-STARTPTS','-an','-r','24','-c:v','libx264','-crf','17','-preset','medium','-threads','4','-pix_fmt','yuv420p','-movflags','+faststart',str(clip)])
 outputs={}
 for p,n in ((fullvideo,141),(clip,41)):
  a=probe(p)
  if len(a['frames'])!=n or a['streams'][0]['avg_frame_rate']!='24/1':raise ValueError('rendered frame/rate')
  outputs[p.name]={'sha256':sha(p),'bytes':p.stat().st_size,'probe':a}
 (OUT/'manifest.json').write_text(json.dumps({'originals':originals,'outputs':outputs,'fixed_frames':FRAMES,'clip_inclusive':[42,82],'crop':None,'lag_alignment':False,'interpolation':False,'comparison_audio':False,'original_audio_in_raw_unchanged':True,'created_unix':time.time()},indent=2)+'\n')
 pics=''.join(f'<figure><a href="frame{n:03d}_comparison_fullres.png"><img src="frame{n:03d}_comparison.png"></a><figcaption>Frame {n} | {n/24:.3f}s</figcaption></figure>' for n in FRAMES)
 (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>R25 反向参考路径诊断</title><style>body{background:#111;color:#eee;font:17px sans-serif;margin:30px}video,img{width:100%}figure{margin:20px 0}p{line-height:1.6}</style><h1>参考 / Native / 正向Full / 反向BLOCK / 反向SAME</h1><p>同一已知开发案例；固定视频50–65帧与采样索引6–14。五列采用24fps同帧排列、完整画幅。该对照检验参考分支读取目标特征的作用；身份、重影和全片质量随指标一起检查。点击截图可看原分辨率。</p><video controls loop src="source_native_forward_reverse_full_length.mp4"></video><h2>42–82帧</h2><video controls loop src="frames042_082_normal.mp4"></video>'+pics)
 print(json.dumps({'passed':True,'media':str(OUT)}))
if __name__=='__main__':
 lock=(ROOT.parent/'h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);build()
