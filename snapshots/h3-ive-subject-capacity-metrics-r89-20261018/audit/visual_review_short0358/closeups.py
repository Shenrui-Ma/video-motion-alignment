from pathlib import Path
import json, subprocess, hashlib
from PIL import Image, ImageDraw, ImageFont
O=Path(__file__).parent; R=O.parents[1]; M=json.loads((R/'showcase/short_0358/PRESENTATION.json').read_text()); W,H=512,400
frames=[]
for b in M['inputs']:
 p=Path(b['file']);assert hashlib.sha256(p.read_bytes()).hexdigest()==b['sha256']
 frames.append(subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',str(p),'-vf','crop=640:500:16:88,scale=512:400','-frames:v','105','-f','rawvideo','-pix_fmt','rgb24','-threads','1','-']))
font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',20)
for k,inds in enumerate([[34,36,39],[44,47,50],[79,83,86],[93,96,99]]):
 im=Image.new('RGB',(W*3,(H+32)*len(inds)));dr=ImageDraw.Draw(im)
 for r,n in enumerate(inds):
  for c,raw in enumerate(frames):
   im.paste(Image.frombytes('RGB',(W,H),raw[n*W*H*3:(n+1)*W*H*3]),(c*W,r*(H+32)))
   dr.text((c*W+4,r*(H+32)+H+4),['参考视频','普通编辑','时序引导'][c]+f' f{n} {n/24:.3f}s',font=font,fill='white')
 im.save(O/f'contact_detail_{k}.jpg',quality=97)
