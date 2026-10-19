from pathlib import Path
from PIL import Image,ImageDraw
import subprocess,json
OUT=Path(__file__).parent
rows=json.loads((OUT/'SOURCE_INPUTS.json').read_text())
for s in ('long_0031','long_0091'):
 x=next(a for a in rows if a['source_id']==s);indices=list(range(0,150,5))+[149]
 expr='+'.join('eq(n\\,'+str(i)+')' for i in indices)
 raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-i',x['path'],'-vf',f'select={expr},scale=426:240:force_original_aspect_ratio=decrease,pad=426:240:(ow-iw)/2:(oh-ih)/2','-vsync','0','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
 size=426*240*3;assert len(raw)==len(indices)*size
 for start in range(0,len(indices),12):
  batch=indices[start:start+12];im=Image.new('RGB',(1278,4*265),(25,25,25));d=ImageDraw.Draw(im)
  for j,i in enumerate(batch):
   idx=start+j;frame=Image.frombytes('RGB',(426,240),raw[idx*size:(idx+1)*size]);x0=(j%3)*426;y=(j//3)*265;im.paste(frame,(x0,y+22));d.text((x0+5,y+4),f'{s} f{i} t={i/25:.2f}s',fill='white')
  im.save(OUT/f'{s}_window_{start:02d}.jpg',quality=90)
 print(s,indices)
