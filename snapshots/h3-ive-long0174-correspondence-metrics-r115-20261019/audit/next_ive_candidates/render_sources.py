from pathlib import Path
import json,hashlib,subprocess
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parent
items={x['source_id']:x for x in json.loads((R/'UNTESTED_CACHED_METADATA.json').read_text())}
ids=['long_0031','long_0091','long_0115','short_0362','long_0143','long_0166','short_0212','short_0279','short_0353','short_0182']
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',18)
rows=[]
for sid in ids:
 item=items[sid];p=Path(item['paths'][0]);d=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_frames,duration','-of','json',str(p)],text=True))['streams'][0]
 count=int(d['nb_frames']);fps=eval(d['r_frame_rate'],{'__builtins__':{}},{});indices=sorted(set(round(i*(count-1)/11) for i in range(12)));folder=R/'contacts'/sid;folder.mkdir(parents=True,exist_ok=True)
 vf='select='+ '+'.join('eq(n\\,%d)'%i for i in indices)+',scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2:black'
 subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',str(p),'-vf',vf,'-vsync','0',str(folder/'frame_%02d.png')],check=True)
 canvas=Image.new('RGB',(1920,918),'black');draw=ImageDraw.Draw(canvas)
 for k,(frame,index) in enumerate(zip(sorted(folder.glob('frame_*.png')),indices)):
  col,row=k%4,k//4;canvas.paste(Image.open(frame),(col*480,row*306));draw.text((col*480+8,row*306+277),f'{sid} | frame {index} | {index/fps:.3f}s',font=font,fill='white')
 output=R/'contacts'/(sid+'.jpg');canvas.save(output,quality=90)
 rows.append({'source_id':sid,'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'width':d['width'],'height':d['height'],'frames':count,'fps':fps,'duration_seconds':count/fps,'reviewed_original_indices':indices,'contact':str(output),'contact_sha256':hashlib.sha256(output.read_bytes()).hexdigest()})
(R/'SOURCE_CONTACTS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))
