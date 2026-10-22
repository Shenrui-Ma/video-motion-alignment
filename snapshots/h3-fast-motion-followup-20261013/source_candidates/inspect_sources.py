from pathlib import Path
import subprocess, math,json,hashlib
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).resolve().parent
FONT=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',17)
for name in ['pexels_5362065','pexels_4938874']:
 p=BASE/(name+'.mp4')
 info=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-show_entries','stream=width,height,r_frame_rate,nb_frames,duration','-of','json',str(p)]))
 (BASE/(name+'_ffprobe.json')).write_text(json.dumps(info,indent=2))
 raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(p),'-vf','fps=4,scale=320:180','-f','rawvideo','-pix_fmt','rgb24','-'])
 size=320*180*3;n=len(raw)//size
 for page in range(math.ceil(n/30)):
  ids=list(range(page*30,min(n,(page+1)*30)));canvas=Image.new('RGB',(1600,math.ceil(len(ids)/5)*205),'white');d=ImageDraw.Draw(canvas)
  for j,i in enumerate(ids):
   x=j%5*320;y=j//5*205;canvas.paste(Image.frombytes('RGB',(320,180),raw[i*size:(i+1)*size]),(x,y));d.text((x+3,y+181),f'{i/4:.2f}s preview (4fps)',font=FONT,fill='black')
  canvas.save(BASE/f'{name}_overview_p{page+1}.jpg',quality=94)
 print(name,info,'pages',math.ceil(n/30),'sha',hashlib.sha256(p.read_bytes()).hexdigest())
