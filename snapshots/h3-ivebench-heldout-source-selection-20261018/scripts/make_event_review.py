"""Human source-only event inspection frames; never input to the intervention."""
import hashlib,io,json,subprocess
from pathlib import Path
from PIL import Image,ImageDraw
B=Path(__file__).resolve().parents[1]
chosen={'short_0092':[16,21,27,32],'short_0114':[35,39,43,47,49,53,57,61],'short_0126':[10,20,31,41],'short_0392':[0,10,20,30,40,50]}
m=json.loads((B/'SELECTED_4_MANIFEST.json').read_text())
(B/'source_event_review').mkdir(exist_ok=True)
records=[]
for row in m['pairs']:
 id=row['pair_id'];indices=chosen[id];p=Path(row['source']['file'])
 sheet=Image.new('RGB',(1920,((len(indices)+3)//4)*295),'#111111');draw=ImageDraw.Draw(sheet)
 for j,i in enumerate(indices):
  raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(p),'-map','0:v:0','-vf',f'select=eq(n\\,{i}),scale=480:270:force_original_aspect_ratio=decrease','-frames:v','1','-f','image2pipe','-c:v','png','-threads','1','pipe:1'],timeout=30)
  image=Image.open(io.BytesIO(raw));x=(j%4)*480;y=(j//4)*295
  sheet.paste(image,(x,y+25));draw.text((x+4,y+5),f'{id} source frame {i} / {row["source"]["actual_pts_s"][i]:.6f}s',fill='white')
 dest=B/'source_event_review'/f'{id}.jpg';sheet.save(dest,quality=94)
 records.append({'pair_id':id,'source_sha256':row['source']['sha256'],'indices':indices,'file':str(dest),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
(B/'source_event_review/FRAMES.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
