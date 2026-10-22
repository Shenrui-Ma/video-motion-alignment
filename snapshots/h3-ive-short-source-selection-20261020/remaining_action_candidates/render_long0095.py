from pathlib import Path
import av,json,hashlib
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parent;p=R/'sources/long_0095.mp4';out=R/'long0095_frames130_279';out.mkdir(exist_ok=True)
font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',15)
rows=[];page=None;draw=None
with av.open(str(p)) as c:
 for i,f in enumerate(c.decode(video=0)):
  if i<130 or i>=280: continue
  j=(i-130)%24
  if j==0: page=Image.new('RGB',(1280,1248),'black');draw=ImageDraw.Draw(page)
  im=f.to_image().convert('RGB');im.thumbnail((320,180));x=j%4*320;y=j//4*208;page.paste(im,(x,y));draw.text((x+4,y+182),f'f{i} {float(f.pts*f.time_base):.3f}s',font=font,fill='white')
  rows.append({'frame':i,'pts':f.pts,'time_base':str(f.time_base),'seconds':float(f.pts*f.time_base)})
  if j==23: page.save(out/f'{(i-130)//24+1:03d}.jpg',quality=88)
 if len(rows)%24: page.save(out/f'{(len(rows)-1)//24+1:03d}.jpg',quality=88)
v={'source':str(p),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'frames':rows,'pages':[{'file':str(x),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted(out.glob('*.jpg'))]}
(out/'FRAME_LEDGER.json').write_text(json.dumps(v,indent=2)+'\n');print(len(rows),len(v['pages']))
