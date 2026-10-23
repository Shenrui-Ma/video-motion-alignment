from pathlib import Path
import json,subprocess,hashlib
from PIL import Image,ImageDraw,ImageFont
E=Path(__file__).resolve().parents[2];D=Path(__file__).resolve().parent/'visual/short_0358';D.mkdir(parents=True,exist_ok=True)
M=json.loads((E/'metrics/manifest.json').read_text())['jobs']
methods=['source','native','global_weak','partial_temporal_rope']
for method in methods:
 j=next((j for j in M if j['task_id']=='short_0358' and j['method']==method),None)
 if j is None: continue
 p=D/(method+'.mp4')
 if not p.exists(): subprocess.run(['scp','-q','H3_HOST_CONFIGURE_LOCALLY:'+j['video'],str(p)],check=True)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==j['sha256']
 fd=D/method;fd.mkdir(exist_ok=True)
 if not (fd/'104.jpg').exists():
  x,y,w,h=j['crop_xywh']
  subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(p),'-vf',f'crop={w}:{h}:{x}:{y},scale=768:432','-frames:v',str(j['valid_frames']),'-start_number','0','-q:v','2',str(fd/'%03d.jpg')],check=True)
 font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',20)
 frames=list(range(0,105,8));sheet=Image.new('RGB',(4*384,4*240),'#151515');draw=ImageDraw.Draw(sheet)
 for k,f in enumerate(frames):
  im=Image.open(fd/f'{f:03d}.jpg').resize((384,216));x=k%4*384;y=k//4*240;sheet.paste(im,(x,y+24));draw.text((x+8,y),f'{method} frame {f}',font=font,fill='white')
 sheet.save(D/(method+'_overview.jpg'))
print(D)
