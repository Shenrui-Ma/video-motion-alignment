from pathlib import Path
import json,hashlib,subprocess
from PIL import Image,ImageDraw,ImageFont
O=Path(__file__).resolve().parent
mp=Path('/Users/researcher/DevProjects/h3-timing-flexiact-prompt-pair-r72-20261018/showcase/fitness__game_man_5/PRESENTATION.json');m=json.loads(mp.read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bound(p):return {'file':str(p),'sha256':sha(p)}
assert sha(m['gate']['file'])==m['gate']['sha256'];assert json.loads(Path(m['gate']['file']).read_text())['passed'] is True
w,h,n=384,256,147;raws=[];timelines=[]
for b in m['inputs']:
 p=Path(b['file']);assert sha(p)==b['sha256']
 q=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(p)]));pts=[float(x['best_effort_timestamp_time']) for x in q['frames']];assert len(pts)==158 and all(abs(t-i/24)<1e-6 for i,t in enumerate(pts));timelines.append(q)
 raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',str(p),'-vf',f'scale={w}:{h}:flags=lanczos','-frames:v',str(n),'-f','rawvideo','-pix_fmt','rgb24','-threads','1','-']);assert len(raw)==n*w*h*3;raws.append(raw)
f=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',18);roles=['参考','P0普通编辑','P1普通编辑'];pages=[]
def make(ids,p):
 im=Image.new('RGB',(3*w,len(ids)*(h+30)),'black');d=ImageDraw.Draw(im)
 for row,i in enumerate(ids):
  for c,r in enumerate(raws):
   im.paste(Image.frombytes('RGB',(w,h),r[i*w*h*3:(i+1)*w*h*3]),(c*w,row*(h+30)));d.text((c*w+8,row*(h+30)+h+4),f'{roles[c]} f{i:03d} {i/24:.3f}s',font=f,fill='white')
 im.save(p,quality=96)
for i in range(0,n,7):
 p=O/f'frames_{i:03d}_{min(i+6,n-1):03d}.jpg';make(list(range(i,min(i+7,n))),p);pages.append(bound(p))
make([0,24,39,48,60,72,84,96,120,144],O/'events.jpg')
(O/'FRAME_LEDGER.json').write_text(json.dumps({'presentation':bound(mp),'inputs':m['inputs'],'gate':m['gate'],'all_indices':list(range(n)),'source_precision_s':.125,'display_fps':24,'pages':pages,'events':bound(O/'events.jpg'),'timelines':timelines},ensure_ascii=False,indent=2)+'\n');print(len(pages))
