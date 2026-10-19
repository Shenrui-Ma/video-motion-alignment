"""Fixed same-physical-time evidence layout; does not select successful frames."""
import argparse,fcntl,hashlib,json,subprocess,time
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
FF='/opt/homebrew/bin/ffmpeg';FP='/opt/homebrew/bin/ffprobe'
SPECS={'fresh_a':{'frames':(18,45,57,86,105),'primary':(44,61),'clip':(36,69)},'fresh_b':{'frames':(25,65,77,107,119),'primary':(64,81),'clip':(56,89)}}
FONT='/System/Library/Fonts/STHeiti Light.ttc';LOCK=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def run(cmd):return subprocess.run(cmd,check=True,capture_output=True)
def probe(p):return json.loads(run([FP,'-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','stream=width,height,r_frame_rate,avg_frame_rate,time_base,duration,nb_frames:frame=best_effort_timestamp_time','-of','json',str(p)]).stdout)
def extract(p,n,out):run([FF,'-v','error','-y','-threads','2','-i',str(p),'-vf',f'select=eq(n\\,{n})','-vsync','0','-frames:v','1','-threads','2',str(out)])
def build(cid,seed):
 spec=SPECS[cid];key=f'{cid}_seed{seed}';pair=read(HERE/'pairs'/key/'PAIR_COMPLETE.json')
 if not pair['passed']:raise ValueError('pair not verified')
 dst=HERE/'media'/key;dst.mkdir(parents=True,exist_ok=True)
 names=[f'r24_{cid}_seed{seed}_{a}' for a in ('native','full_6to14')];arcs=[HERE/'captured'/x for x in names]
 done=[read(x/'CPU_COMPLETE.json') for x in arcs];source=ROOT/'assets/prepared'/f'{cid}.mp4'
 vids=[source]+[p/'output'/Path(d['video']).name for p,d in zip(arcs,done)]
 expected=[read(arcs[0]/'RUN_GATE.json')['case']['video_sha256']]+[d['video_sha256'] for d in done]
 original=[]
 for v,s in zip(vids,expected):
  if sha(v)!=s:raise ValueError('source SHA changed')
  a=probe(v);st=a['streams'][0]
  if not(st['width']==1312 and st['height']==736 and st['r_frame_rate']=='24/1' and len(a['frames'])==141 and abs(float(st['duration'])-5.875)<1e-6):raise ValueError('source geometry')
  if any(abs(float(f['best_effort_timestamp_time'])-i/24)>1e-6 for i,f in enumerate(a['frames'])):raise ValueError('source PTS')
  original.append({'path':str(v),'sha256':s,'probe':a})
 w,h,foot=656,368,76;labels=('1.参考视频','2.编辑后：未干预','3.编辑后：同时间参考路由')
 font=ImageFont.truetype(FONT,24);small=ImageFont.truetype(FONT,17)
 caption=Image.new('RGB',(3*w,foot),'black');dr=ImageDraw.Draw(caption)
 for i,t in enumerate(labels):
  box=dr.textbbox((0,0),t,font=font);dr.text((i*w+(w-(box[2]-box[0]))/2,7),t,font=font,fill='white')
 dr.text((18,45),f'Sam Altman角色替换 | {cid} | seed {seed}',font=small,fill='#c7c7c7')
 dr.text((w+30,45),'24fps，同一物理时间，无动作延迟补偿',font=small,fill='#c7c7c7')
 dr.text((2*w+30,45),f'采样索引6–14；视频主窗{spec["primary"][0]}–{spec["primary"][1]}帧',font=small,fill='#c7c7c7')
 caption.save(dst/'caption.png')
 for n in spec['frames']:
  im=Image.new('RGB',(3*w,h+foot),'black');full=Image.new('RGB',(3936,736+2*foot),'black')
  for i,v in enumerate(vids):
   p=dst/f'raw_frame{n:03d}_col{i}.png';extract(v,n,p);raw=Image.open(p).convert('RGB');full.paste(raw,(i*1312,0));im.paste(raw.resize((w,h),Image.Resampling.LANCZOS),(i*w,0))
  im.paste(caption,(0,h));im.save(dst/f'frame{n:03d}_triptych.png');full.paste(caption.resize((3936,2*foot),Image.Resampling.LANCZOS),(0,736));full.save(dst/f'frame{n:03d}_triptych_fullres.png')
 base=[FF,'-v','error','-y','-filter_complex_threads','1']
 for v in vids:base+=['-threads','2','-i',str(v)]
 base+=['-loop','1','-i',str(dst/'caption.png')]
 filt=';'.join(f'[{i}:v]setpts=PTS-STARTPTS,scale=656:368:flags=lanczos,setsar=1[v{i}]' for i in range(3))+';[v0][v1][v2]hstack=inputs=3[top];[top][3:v]vstack=inputs=2:shortest=1[v]'
 fullvideo=dst/'full_length.mp4';run(base+['-filter_complex',filt,'-map','[v]','-an','-frames:v','141','-r','24','-c:v','libx264','-crf','17','-preset','medium','-pix_fmt','yuv420p','-threads','4','-movflags','+faststart',str(fullvideo)])
 start,end=spec['clip'];outfiles=[(fullvideo,141,24)]
 for name,rate,factor in (('primary_normal.mp4',24,1),('primary_half_speed.mp4',12,2)):
  out=dst/name;run([FF,'-v','error','-y','-threads','2','-i',str(fullvideo),'-vf',f'trim=start_frame={start}:end_frame={end+1},setpts={factor}*(PTS-STARTPTS)','-an','-r',str(rate),'-fps_mode','cfr','-c:v','libx264','-crf','17','-preset','medium','-threads','4','-pix_fmt','yuv420p','-movflags','+faststart',str(out)]);outfiles.append((out,end-start+1,rate))
 outputs={}
 for p,n,rate in outfiles:
  a=probe(p);st=a['streams'][0]
  if len(a['frames'])!=n or st['r_frame_rate']!=str(rate)+'/1' or (st['width'],st['height'])!=(1968,444):raise ValueError('composite geometry/rate')
  if any(abs(float(x['best_effort_timestamp_time'])-i/rate)>1e-6 for i,x in enumerate(a['frames'])):raise ValueError('composite PTS')
  outputs[p.name]={'sha256':sha(p),'bytes':p.stat().st_size,'probe':a}
 if any(sha(v)!=s for v,s in zip(vids,expected)):raise ValueError('source changed after media')
 (dst/'manifest.json').write_text(json.dumps({'originals':original,'outputs':outputs,'source_only_fixed_frames':spec['frames'],'primary_window':spec['primary'],'clip_inclusive':spec['clip'],'fullfield_scale':[656,368],'crop':None,'footer_height':foot,'lag_alignment':False,'frame_interpolation':False,'composite_audio':False,'original_audio_preserved':True,'selection_before_generation':True,'builder_sha256':sha(__file__)},indent=2)+'\n')
 pics=''.join(f'<figure><img src="frame{n:03d}_triptych.png"><figcaption>Frame {n} | {n/24:.3f}s</figcaption></figure>' for n in spec['frames'])
 (dst/'index.html').write_text(f'<!doctype html><meta charset="utf-8"><title>R24 {key}</title><style>body{{background:#111;color:#eee;font:17px sans-serif;max-width:1600px;margin:30px auto}}video,img{{width:100%;height:auto}}figure{{margin:25px 0}}p{{line-height:1.6}}figcaption{{color:#bbb}}</style><h1>{key}：参考 / 未干预 / 同时间参考路由</h1><p>新参考视频的窗口与展示帧由源素材预先选定；这是该源的两个预定种子之一，全部结果均保留。各列保留完整视野及相同缩放，按原始物理时间同步，无延迟补偿或帧插值。6–14为零起始采样索引，不是视频帧。时序、可观测性与形状/身份/背景质量分别评价。</p><h2>完整5.875秒</h2><video controls loop src="full_length.mp4"></video><h2>主窗附近{start}–{end}帧，正常速度</h2><video controls loop src="primary_normal.mp4"></video><h2>同片段半速，无插帧</h2><video controls loop src="primary_half_speed.mp4"></video>'+pics)
 print(json.dumps({'passed':True,'path':str(dst),'time':time.time()}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('case',choices=SPECS);p.add_argument('seed',type=int,choices=(2026101610,2026101611));a=p.parse_args()
 with LOCK.open('a') as l:
  fcntl.flock(l,fcntl.LOCK_EX|fcntl.LOCK_NB);build(a.case,a.seed)
