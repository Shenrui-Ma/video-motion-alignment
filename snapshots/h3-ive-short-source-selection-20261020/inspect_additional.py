from pathlib import Path
from fractions import Fraction
import hashlib,io,json,subprocess
from PIL import Image,ImageDraw,ImageFont

R=Path(__file__).resolve().parent;B=R.parent
specs={'short_0353':B/'h3-ivebench-subject-candidates-r82-20261018/sources/short_0353.mp4',
       'long_0039':B/'h3-timing-architecture-r2-20261016/audit/ive_more_subject_sources_20261018/sources/long_0039.mp4'}
extra=R/'sources/long_0034.mp4'
if extra.exists():specs['long_0034']=extra
out=R/'additional_contacts';out.mkdir(exist_ok=True)
rows=[]
for sid,p in specs.items():
 d=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_streams','-of','json',str(p)]));s=d['streams'][0]
 pts=[float(Fraction(f['best_effort_timestamp'])*Fraction(s['time_base'])) for f in d['frames']]
 n=len(pts);indices=sorted(set(round(i*(n-1)/23) for i in range(24)));target=out/f'{sid}_full_contact.jpg'
 if not target.exists():
  vf='select='+'+'.join('eq(n\\,'+str(i)+')' for i in indices)+',scale=384:216:force_original_aspect_ratio=decrease,pad=384:216:(ow-iw)/2:(oh-ih)/2:black,tile=4x6'
  raw=subprocess.check_output(['ffmpeg','-v','error','-threads','2','-i',str(p),'-vf',vf,'-vsync','0','-frames:v','1','-threads','1','-f','image2pipe','-c:v','png','pipe:1'])
  tiles=Image.open(io.BytesIO(raw)).convert('RGB');im=Image.new('RGB',(1536,1500),'black');draw=ImageDraw.Draw(im);font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',16)
  for j,i in enumerate(indices):
   x=j%4*384;y=j//4*250;im.paste(tiles.crop((x,j//4*216,x+384,j//4*216+216)),(x,y));draw.text((x+5,y+220),f'{sid} f{i} {pts[i]:.3f}s',font=font,fill='white')
  im.save(target,quality=89)
 rows.append({'source_id':sid,'source_path':str(p),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size,'frames':n,'fps':s['avg_frame_rate'],'duration_s':float(s['duration']),'contact':str(target),'contact_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'viewed_frame_indices':indices,'viewed_pts_s':[pts[i] for i in indices]})
(R/'ADDITIONAL_SOURCE_CONTACTS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))
