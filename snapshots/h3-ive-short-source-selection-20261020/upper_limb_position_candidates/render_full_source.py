from pathlib import Path
import av,json,hashlib
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parent;p=R/'sources/long_0191.mp4';out=R/'full_source';out.mkdir(exist_ok=True)
font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',15)
rows=[];page=None;draw=None
with av.open(str(p)) as c:
 for i,f in enumerate(c.decode(video=0)):
  j=i%24
  if j==0: page=Image.new('RGB',(1280,1248),'black');draw=ImageDraw.Draw(page)
  im=f.to_image().convert('RGB');im.thumbnail((320,180));x=j%4*320;y=j//4*208;page.paste(im,(x,y));draw.text((x+4,y+182),f'f{i} {float(f.pts*f.time_base):.3f}s',font=font,fill='white')
  rows.append({'frame':i,'pts':f.pts,'time_base':str(f.time_base),'seconds':float(f.pts*f.time_base)})
  if j==23: page.save(out/f'{i//24+1:03d}.jpg',quality=88)
 if i%24!=23: page.save(out/f'{i//24+1:03d}.jpg',quality=88)
v={'source':str(p),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'frames':rows,'pages':[{'file':str(x),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted(out.glob('*.jpg'))]}
(out/'FRAME_LEDGER.json').write_text(json.dumps(v,indent=2)+'\n');print(len(rows),len(v['pages']))
