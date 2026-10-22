from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import subprocess,json,math,sys,hashlib
base=Path(__file__).resolve().parent;name=sys.argv[1];start=float(sys.argv[2]);count=int(sys.argv[3]);out=base/f'{name}_window_{count}.mp4'
argv=['/opt/homebrew/bin/ffmpeg','-v','error','-y','-ss',str(start),'-i',str(base/(name+'.mp4')),'-vf','fps=24,scale=1312:736:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1312:736:(ow-iw)/2:(oh-ih)/2,setsar=1','-frames:v',str(count),'-an','-c:v','libx264','-crf','16','-preset','fast','-pix_fmt','yuv420p',str(out)];subprocess.run(argv,check=True)
raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(out),'-vf','scale=400:224','-f','rawvideo','-pix_fmt','rgb24','-']);s=400*224*3;n=len(raw)//s;assert n==count;font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',18)
for page in range(math.ceil(n/30)):
 ids=list(range(page*30,min(n,(page+1)*30)));can=Image.new('RGB',(2000,math.ceil(len(ids)/5)*253),'white');d=ImageDraw.Draw(can)
 for j,i in enumerate(ids):
  x=j%5*400;y=j//5*253;can.paste(Image.frombytes('RGB',(400,224),raw[i*s:(i+1)*s]),(x,y));d.text((x+3,y+226),f'f{i:03d} | {i/24:.3f}s | src~{start+i/24:.3f}s',font=font,fill='black')
 can.save(base/f'{name}_window_{count}_all_p{page+1}.jpg',quality=95)
meta={'file':str(out),'source_start_seconds':start,'frames':count,'fps':24,'duration':count/24,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'conversion_argv':argv,'no_speed_change':True,'no_temporal_interpolation':True};(base/f'{name}_window_{count}.json').write_text(json.dumps(meta,indent=2));print(meta)
