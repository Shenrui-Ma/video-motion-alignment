from pathlib import Path
import argparse, hashlib, json, subprocess
from PIL import Image, ImageDraw, ImageFont

p = argparse.ArgumentParser()
p.add_argument('--source', required=True, choices=['short_0114','short_0392'])
p.add_argument('--paired', action='store_true')
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
manifest = root / ('showcase_pairs' if a.paired else 'showcase') / a.source / 'PRESENTATION.json'
data = json.loads(manifest.read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(data['gate']['file']) == data['gate']['sha256']
assert json.loads(Path(data['gate']['file']).read_text())['passed']
assert data['columns'] == (['source','native','forced'] if a.paired else ['source','native'])
timeline = data['timeline']
n, fps = timeline['valid_frames'], timeline['fps']
x,y,cw,ch = timeline['crop_xywh']
width,height = 480,270
out = root / 'audit' / ('root_pair_review_' if a.paired else 'root_native_review_') / a.source
out.mkdir(parents=True,exist_ok=True)
assert not (out/'FRAME_LEDGER.json').exists()
frames=[]
for entry in data['inputs']:
    assert sha(entry['file']) == entry['sha256']
    raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',entry['file'],'-vf',f'crop={cw}:{ch}:{x}:{y},scale={width}:{height}:flags=lanczos','-frames:v',str(n),'-pix_fmt','rgb24','-f','rawvideo','-threads','1','-'])
    assert len(raw)==n*width*height*3
    frames.append(raw)
font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',16)
labels=['参考视频','普通编辑','时序引导'];pages=[]
for start in range(0,n,6):
    indices=list(range(start,min(n,start+6)))
    im=Image.new('RGB',(len(frames)*width,len(indices)*(height+26)),'black');d=ImageDraw.Draw(im)
    for row,i in enumerate(indices):
        for col,raw in enumerate(frames):
            pos=i*width*height*3
            im.paste(Image.frombytes('RGB',(width,height),raw[pos:pos+width*height*3]),(col*width,row*(height+26)))
            d.text((col*width+4,row*(height+26)+height+3),f'{labels[col]} | f{i:03d} | {i/fps:.3f}s',font=font,fill='white')
    path=out/f'frames_{start:03d}_{indices[-1]:03d}.jpg';im.save(path,quality=96)
    pages.append({'file':str(path),'sha256':sha(path),'indices':indices})
(out/'FRAME_LEDGER.json').write_text(json.dumps({'manifest':str(manifest),'manifest_sha256':sha(manifest),'inputs':data['inputs'],'physical_indices':list(range(n)),'fps':fps,'pages':pages},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'out':str(out),'frames':n,'pages':len(pages)}))
