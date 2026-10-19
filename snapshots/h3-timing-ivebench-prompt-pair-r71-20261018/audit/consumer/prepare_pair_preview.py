"""Prepare the preregistered six times before the full MP4 rendering."""
import io
from PIL import Image,ImageDraw,ImageFont
import postrun as p
from pathlib import Path
import subprocess
incoming=p.HERE/'incoming';p.validate_gate(p.read(incoming/'PAIR_RUNTIME_GATE.json'));files=p.read(incoming/'COLLECTION.json')['files']
for name,b in files.items():p.check(p.sha(incoming/name)==b['sha256'],'intake mismatch')
paths=[p.PRODUCER/'inputs/short_0210_video.mp4',incoming/'p0.mp4',incoming/'p1.mp4'];indices=[0,17,34,52,69,86]
for path in paths:
 s=p.probe(path);p.check((s['width'],s['height'],s['avg_frame_rate'],len(s['pts']))==(1312,736,'24/1',90),'shape mismatch');p.check(all(abs(t-i/24)<1e-6 for i,t in enumerate(s['pts'])),'PTS mismatch')
out=p.HERE/'pair_preliminary';out.mkdir(exist_ok=False);canvas=Image.new('RGB',(1920,408*6),'black');d=ImageDraw.Draw(canvas);font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',18);tiny=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',13)
for row,i in enumerate(indices):
 for col,path in enumerate(paths):
  raw=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(path),'-vf',f'select=eq(n\\,{i}),crop=1280:720:16:8,scale=640:360:flags=lanczos','-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','-'],timeout=90)
  canvas.paste(Image.open(io.BytesIO(raw)).convert('RGB'),(640*col,408*row));label=p.LABELS[col];d.text((640*col+(640-d.textlength(label,font=font))/2,408*row+374),label,font=font,fill='white')
 d.text((6,408*row+362),f'{i/24:.3f}s',font=tiny,fill='#bbb')
fig=out/'six_times.png';canvas.save(fig);p.save(out/'RECEIPT.json',{'gate':p.bound(incoming/'PAIR_RUNTIME_GATE.json'),'files':[p.bound(x) for x in paths],'indices':indices,'figure':p.bound(fig),'timeline':'90 raw frames24fps; six uniform indices inside87 validframes; exactPTSchecked'});print(fig)
