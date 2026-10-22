from pathlib import Path
import subprocess,json,math,sys
from PIL import Image,ImageDraw,ImageFont
base=Path(__file__).resolve().parent;font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',17)
for name in sys.argv[1:]:
 p=base/(name+'.mp4');probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-show_entries','stream=width,height,r_frame_rate,nb_frames,duration','-of','json',str(p)]));(base/(name+'_probe.json')).write_text(json.dumps(probe,indent=2))
 raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(p),'-vf','fps=4,scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2','-f','rawvideo','-pix_fmt','rgb24','-']);s=320*180*3;n=len(raw)//s
 for page in range(math.ceil(n/30)):
  ids=list(range(page*30,min(n,(page+1)*30)));can=Image.new('RGB',(1600,math.ceil(len(ids)/5)*204),'white');d=ImageDraw.Draw(can)
  for j,i in enumerate(ids):
   x=j%5*320;y=j//5*204;can.paste(Image.frombytes('RGB',(320,180),raw[i*s:(i+1)*s]),(x,y));d.text((x+3,y+181),f'{i/4:.2f}s',font=font,fill='black')
  can.save(base/f'{name}_overview_p{page+1}.jpg',quality=94)
 print(name,probe,'pages',math.ceil(n/30))
