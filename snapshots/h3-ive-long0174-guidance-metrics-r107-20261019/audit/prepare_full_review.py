"""After real paired intake, render all valid frames for the existing event review."""
from pathlib import Path
import hashlib
import json
import subprocess
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'audit/full_frame_review'
manifest=ROOT/'showcase/long_0174/PRESENTATION.json'
data=json.loads(manifest.read_text())
assert data['valid_frames']==145 and data['fps']==24
assert len(data['inputs'])==3
assert not OUT.exists()
OUT.mkdir()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(data['gate']['file'])==data['gate']['sha256']
gate=json.loads(Path(data['gate']['file']).read_text());assert gate['passed'] is True
frames=[]
for item in data['inputs']:
    assert sha(item['file'])==item['sha256']
    raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',item['file'],
          '-vf','crop=1280:720:16:8,scale=480:270','-frames:v','145','-f','rawvideo','-pix_fmt','rgb24','-threads','1','-'])
    assert len(raw)==145*480*270*3
    frames.append(raw)
font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',18)
pages=[]
for first in range(0,145,10):
    ids=list(range(first,min(145,first+10)))
    image=Image.new('RGB',(1440,len(ids)*300),'black');draw=ImageDraw.Draw(image)
    for row,idx in enumerate(ids):
        for col,raw in enumerate(frames):
            image.paste(Image.frombytes('RGB',(480,270),raw[idx*480*270*3:(idx+1)*480*270*3]),(col*480,row*300))
            draw.text((col*480+8,row*300+274),f'{["Source","Native","Guided"][col]}  f{idx:03d}  {idx/24:.3f}s',font=font,fill='white')
    target=OUT/f'frames_{first:03d}_{ids[-1]:03d}.jpg';image.save(target,quality=96)
    pages.append({'file':str(target),'sha256':sha(target),'frames':ids})
ledger={'presentation':{'file':str(manifest),'sha256':sha(manifest)},'inputs':data['inputs'],'frame_indices':list(range(145)),'pages':pages,'scope':'All145 valid frames, same timestamp and identical crop/scale. Rendering is not a visual verdict.'}
(OUT/'FRAME_LEDGER.json').write_text(json.dumps(ledger,indent=2)+'\n')
print(json.dumps({'pages':len(pages),'review_status':'pending actual inspection'}))
