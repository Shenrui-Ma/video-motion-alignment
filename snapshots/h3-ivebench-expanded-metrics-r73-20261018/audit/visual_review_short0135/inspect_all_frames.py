"""All112 same-index brush-region triplets; crop fixed identically from source geometry."""
import hashlib
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
names=('source','native','forced')
loaded={}
roi=[500,0,500,500]
for name in names:
    path=ROOT/'prepared/short_0135'/(name+'_score.mp4')
    raw=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(path),
        '-vf','crop=500:500:500:0,scale=224:224:flags=lanczos',
        '-fps_mode','vfr','-pix_fmt','rgb24','-f','rawvideo','-'])
    size=224*224*3
    assert len(raw)==112*size
    loaded[name]=[Image.frombytes('RGB',(224,224),raw[i*size:(i+1)*size]) for i in range(112)]
files=[]
for page in range(4):
    image=Image.new('RGB',(1568,2800))
    draw=ImageDraw.Draw(image)
    indices=list(range(page*28,(page+1)*28))
    for j,index in enumerate(indices):
        x,y=j%7*224,j//7*700
        draw.text((x+4,y+5),f'frame {index:03d} / {index/24:.3f}s',fill='white')
        for row,name in enumerate(names):
            image.paste(loaded[name][index],(x,y+24+row*224))
            draw.text((x+4,y+26+row*224),name,fill='#ffff00',stroke_width=1,stroke_fill='black')
    dest=OUT/f'all112_brush_page{page+1:02d}.jpg'
    image.save(dest,quality=97)
    files.append(dict(path=str(dest),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),frames=indices))
(OUT/'ALL112_BRUSH_FRAMES.json').write_text(json.dumps(dict(crop_xywh=roi,
    selection='fixed spatial crop covering brush, applied identically; all112 physical frames in original order',
    columns='one physical frame each; rows within column source/native/forced',files=files),indent=2)+'\n')
