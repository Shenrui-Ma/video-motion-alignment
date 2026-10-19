import fcntl,json,hashlib
from pathlib import Path
lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:print('CPU_BUSY');raise SystemExit(75)
from PIL import Image,ImageDraw,ImageFont
root=Path('/Users/researcher/DevProjects/h3-timing-manual-source51310-r41-20261017/analysis/postrun');p=json.loads((root/'PROTOCOL.json').read_text());font=ImageFont.truetype(p['presentation']['font_source'],24)
for name,layout in p['presentation']['layouts'].items():
 image=Image.new('RGB',(656*len(layout['keys']),48),'black');draw=ImageDraw.Draw(image)
 for i,label in enumerate(layout['labels']):
  bb=draw.textbbox((0,0),label,font=font);draw.text((i*656+(656-bb[2]+bb[0])/2,(48-bb[3]+bb[1])/2-bb[1]),label,font=font,fill='white')
 path=root/'assets'/(name+'.png');assert not path.exists();image.save(path);layout['asset']=str(path.relative_to(root));layout['asset_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
(root/'PROTOCOL.json').write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n');b=json.loads((root/'BINDING.template.json').read_text());b['protocol_sha256']=hashlib.sha256((root/'PROTOCOL.json').read_bytes()).hexdigest();(root/'BINDING.template.json').write_text(json.dumps(b,indent=2)+'\n');print('PASS two fixed Chinese caption PNGs; source font SHA recorded; no video/model read')
