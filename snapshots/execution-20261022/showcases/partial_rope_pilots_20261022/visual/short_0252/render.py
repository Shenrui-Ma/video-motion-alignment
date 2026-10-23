from pathlib import Path
import json, subprocess, hashlib
from PIL import Image,ImageDraw,ImageFont
D=Path(__file__).resolve().parent;E=D.parents[3]
m=json.loads((E/'metrics/manifest.json').read_text())['jobs']
roles=['source','native','global_weak','partial_temporal_rope']
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',18)
records=[]
for role in roles:
 j=next(j for j in m if j['task_id']=='short_0252' and j['method']==role)
 p=D/(role+'.mp4')
 if not p.exists(): subprocess.run(['scp','-q','H3_HOST_CONFIGURE_LOCALLY:'+j['video'],str(p)],check=True)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==j['sha256']
 fd=D/role;fd.mkdir(exist_ok=True)
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(p),'-vf','crop=1280:720:16:8','-frames:v','98','-start_number','0',str(fd/'%03d.png')],check=True)
 records.append({'role':role,'sha256':j['sha256'],'video':j['video']})
(D/'PROVENANCE.json').write_text(json.dumps(records,indent=2))
def sheet(role,frames,name,crop=None,cols=5,width=320):
 ims=[]
 for n in frames:
  im=Image.open(D/role/f'{n:03d}.png')
  if crop: im=im.crop(crop)
  im=im.resize((width,round(im.height*width/im.width)))
  ims.append((n,im))
 h=ims[0][1].height+26;out=Image.new('RGB',(cols*width,((len(ims)+cols-1)//cols)*h),'#101010');dr=ImageDraw.Draw(out)
 for i,(n,im) in enumerate(ims):
  x=(i%cols)*width;y=(i//cols)*h;out.paste(im,(x,y+26));dr.text((x+6,y+3),f'{role}  frame {n}',font=font,fill='white')
 out.save(D/name)
sheet('partial_temporal_rope',list(range(0,98,5))+[97],'partial_overview.jpg',cols=5,width=320)
sheet('partial_temporal_rope',list(range(34,70)),'partial_hands_034_069.jpg',crop=(180,180,920,720),cols=6,width=300)
sheet('partial_temporal_rope',list(range(68,98)),'partial_raise_068_097.jpg',crop=(180,100,920,650),cols=6,width=300)
