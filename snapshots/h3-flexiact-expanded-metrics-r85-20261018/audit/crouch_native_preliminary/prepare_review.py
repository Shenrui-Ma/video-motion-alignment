from pathlib import Path
import json,subprocess,hashlib
from PIL import Image,ImageDraw,ImageFont
O=Path(__file__).resolve().parent;R=O.parents[1];N=147;w,h=576,384
F='/opt/homebrew/bin/ffmpeg';FP='/opt/homebrew/bin/ffprobe'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bound(p):return {'file':str(p),'sha256':sha(p)}
rec=json.loads((O/'NATIVE_ONLY_RECEIPT.json').read_text()); roles=['参考视频','普通编辑'];streams=[];raws=[]
for b in [rec['source'],rec['local_video']]:
 p=Path(b['file']);assert sha(p)==b['sha256']
 info=json.loads(subprocess.check_output([FP,'-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(p)],timeout=90))
 pts=[float(x['best_effort_timestamp_time']) for x in info['frames']]
 assert len(pts)==158 and info['streams'][0]['width']==1152 and info['streams'][0]['height']==768 and info['streams'][0]['avg_frame_rate']=='24/1'
 assert all(abs(t-i/24)<1e-6 for i,t in enumerate(pts))
 raw=subprocess.check_output([F,'-v','error','-threads','1','-i',str(p),'-vf',f'scale={w}:{h}:flags=lanczos','-frames:v',str(N),'-f','rawvideo','-pix_fmt','rgb24','-threads','1','-'],timeout=90)
 assert len(raw)==N*w*h*3;raws.append(raw);streams.append({'video':b,'pts_s':pts,'properties':info['streams'][0]})
font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',22)
def sheet(indices,path):
 im=Image.new('RGB',(2*w,len(indices)*(h+38)),'black');d=ImageDraw.Draw(im)
 for row,i in enumerate(indices):
  for col,raw in enumerate(raws):
   im.paste(Image.frombytes('RGB',(w,h),raw[i*w*h*3:(i+1)*w*h*3]),(col*w,row*(h+38)))
   d.text((col*w+8,row*(h+38)+h+6),f'{roles[col]} | f{i:03d} | {i/24:.3f}s',font=font,fill='white')
 im.save(path,quality=95)
keys=[0,12,24,36,48,60,72,84,96,108,120,146];sheet(keys,O/'twelve_times.jpg')
pages=[]
for start in range(0,N,7):
 p=O/f'all_frames_{start:03d}_{min(start+6,N-1):03d}.jpg';sheet(range(start,min(start+7,N)),p);pages.append(bound(p))
cap=Image.new('RGB',(2304,70),'black');d=ImageDraw.Draw(cap);fontbig=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',32)
for i,t in enumerate(['1.参考视频','2.普通编辑']):d.text((i*1152+576,35),t,anchor='mm',font=fontbig,fill='white')
cap.save(O/'caption.png')
subprocess.run([F,'-v','error','-threads','1','-i',rec['source']['file'],'-threads','1','-i',rec['local_video']['file'],'-loop','1','-i',str(O/'caption.png'),'-filter_complex','[0:v]trim=end_frame=147,setpts=PTS-STARTPTS[a];[1:v]trim=end_frame=147,setpts=PTS-STARTPTS[b];[a][b]hstack=inputs=2[top];[top][2:v]vstack=inputs=2[v]','-map','[v]','-frames:v','147','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-threads','2','-y',str(O/'source_native_full_valid.mp4')],check=True,timeout=180)
ledger={'scope':'Native-only preliminary; no pair conclusion','receipt':bound(O/'NATIVE_ONLY_RECEIPT.json'),'videos':streams,'physical_frame_indices':list(range(N)),'all_frames_pages':pages,'uniform_twelve_indices':keys,'twelve_times':bound(O/'twelve_times.jpg'),'full_valid_video':bound(O/'source_native_full_valid.mp4'),'source_native_fps':8,'source_temporal_precision_s':.125,'display_fps':24,'padding_removed_frames':11}
(O/'FRAME_LEDGER.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'sheet':str(O/'twelve_times.jpg'),'video':str(O/'source_native_full_valid.mp4'),'pages':len(pages)}))
