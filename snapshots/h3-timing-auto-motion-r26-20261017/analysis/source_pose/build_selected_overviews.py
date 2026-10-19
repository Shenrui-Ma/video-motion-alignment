"""Presentation-only fixed five-frame overlay; no selection changes."""
import io,json,subprocess,fcntl,hashlib
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
P=Path(__file__).resolve().parent;R=P.parents[1];FF='/opt/homebrew/bin/ffmpeg';FRAMES=[0,35,70,105,140];BONES=[(5,6),(5,7),(7,9),(6,8),(8,10),(5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16)]
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16)
lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
m=json.loads((R/'configs/source_selection_manifest.json').read_text());records={}
for cid,item in m['sources'].items():
 vid=R/item['prepared_path'];pose=json.loads((R/item['source_pose_path']).read_text());canvas=Image.new('RGB',(656*3,400*2),'black');files=[]
 for j,idx in enumerate(FRAMES):
  b=subprocess.check_output([FF,'-v','error','-threads','2','-i',str(vid),'-vf',f'select=eq(n\\,{idx})','-frames:v','1','-c:v','png','-threads','1','-f','image2pipe','-']);im=Image.open(io.BytesIO(b)).convert('RGB');plain=P/f'{cid}_selected_frame{idx:03d}.png';im.save(plain);draw=ImageDraw.Draw(im);row=pose['frames'][idx]
  if row['selected_person'] is not None:
   person=row['persons'][row['selected_person']];xy=person['coco17_xy'];cf=person['coco17_score']
   def valid(k):return cf[k]>=.3 and 0<=xy[k][0]<1312 and 0<=xy[k][1]<736
   for a,bone in BONES:
    if valid(a) and valid(bone):draw.line([tuple(xy[a]),tuple(xy[bone])],fill=(0,255,0),width=3)
   for k in range(17):
    if valid(k):
     x,y=xy[k];draw.ellipse((x-4,y-4,x+4,y+4),fill=(0,255,0));draw.text((x+5,y),str(k),font=font,fill='white')
  tile=Image.new('RGB',(656,400),'black');tile.paste(im.resize((656,368),Image.Resampling.LANCZOS));ImageDraw.Draw(tile).text((8,375),f'{cid} | selected frame {idx} | full source {row["full_source_frame"]}',font=font,fill='white');canvas.paste(tile,((j%3)*656,(j//3)*400));files.append(str(plain.relative_to(R)))
 d=ImageDraw.Draw(canvas);d.text((1320,405),f'{cid}: fixed source-only checkpoints',font=font,fill='white');d.text((1320,430),'Green skeleton: unchanged original selector',font=font,fill='white');d.text((1320,455),'No generated video used for selection',font=font,fill='white')
 out=P/f'{cid}_selected_overview.jpg';canvas.save(out,quality=92);records[cid]={'image':str(out.relative_to(R)),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'frames':FRAMES,'raw_frames':files}
(P/'selected_overview_manifest.json').write_text(json.dumps(records,indent=2)+'\n')
