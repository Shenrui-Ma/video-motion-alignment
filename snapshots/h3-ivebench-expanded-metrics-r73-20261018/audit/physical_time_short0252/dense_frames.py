import json,hashlib,subprocess,io
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parent;C=R.parents[1];P=json.loads((R/'PROTOCOL.json').read_text());F=P['dense_frames'];W,H=416,461
out=R/'dense_frames';out.mkdir(exist_ok=False)
font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',18)
frames={}
for arm in ['source','native','forced']:
 p=C/'prepared/short_0252'/(arm+'_score.mp4')
 data=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(p),'-vf','crop=650:720:440:0,scale=416:461:flags=lanczos','-fps_mode','passthrough','-pix_fmt','rgb24','-threads','2','-f','rawvideo','-'],timeout=90)
 assert len(data)==98*W*H*3
 frames[arm]={i:Image.frombytes('RGB',(W,H),data[i*W*H*3:(i+1)*W*H*3]) for i in F}
files=[]
for start in range(0,len(F),4):
 chosen=F[start:start+4];canvas=Image.new('RGB',(W*3,505*len(chosen)),'black');draw=ImageDraw.Draw(canvas)
 for j,i in enumerate(chosen):
  for col,(arm,label) in enumerate([('source','参考视频'),('native','普通编辑'),('forced','固定时序引导')]):
   canvas.paste(frames[arm][i],(col*W,j*505));draw.text((col*W+8,j*505+466),f'{label} | frame {i} | {i/24:.3f}s',font=font,fill='white')
 p=out/f'frames_{chosen[0]:03d}_{chosen[-1]:03d}.png';canvas.save(p);files.append({'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'frames':chosen})
(out/'MANIFEST.json').write_text(json.dumps({'protocol_sha256':hashlib.sha256((R/'PROTOCOL.json').read_bytes()).hexdigest(),'exploratory':True,'crop_xywh':P['dense_crop_xywh'],'files':files},indent=2)+'\n')
print(out)
