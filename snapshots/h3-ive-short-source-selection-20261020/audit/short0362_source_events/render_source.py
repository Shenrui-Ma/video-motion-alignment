from pathlib import Path
import json,hashlib,subprocess
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parent;P=R.parents[1]/'R122_SIX_SOURCE_INPUT_PLAN.json';d=json.loads(P.read_text());c=next(x for x in d['pairs'] if x['source_id']=='short_0362');src=Path(c['source']['file']);assert hashlib.sha256(src.read_bytes()).hexdigest()==c['source']['sha256']
cmd=['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(src),'-vf','scale=640:360','-frames:v','67','-f','rawvideo','-pix_fmt','rgb24','-'];proc=subprocess.Popen(cmd,stdout=subprocess.PIPE);font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',17);frames=[]
for i in range(67):
 b=proc.stdout.read(640*360*3);assert len(b)==640*360*3;frames.append(Image.frombytes('RGB',(640,360),b))
assert proc.wait()==0
pages=[]
for start in range(0,67,6):
 im=Image.new('RGB',(1920,768),'black');dr=ImageDraw.Draw(im);inds=list(range(start,min(start+6,67)))
 for k,i in enumerate(inds):
  x=(k%3)*640;y=(k//3)*384;dr.text((x+6,y+3),f'SOURCE original frame {i:02d} | {i/25:.3f}s',font=font,fill='white');im.paste(frames[i],(x,y+24))
 f=R/f'{start//6+1:03d}.jpg';im.save(f,quality=92);pages.append(dict(file=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),original_frames=inds))
(R/'FRAME_LEDGER.json').write_text(json.dumps(dict(source=c['source'],plan_sha256=hashlib.sha256(P.read_bytes()).hexdigest(),frames_reviewable=list(range(67)),pages=pages,generated_output_viewed=False),indent=2)+'\n')
print(R)
