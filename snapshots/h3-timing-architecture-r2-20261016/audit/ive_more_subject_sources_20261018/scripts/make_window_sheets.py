from pathlib import Path
from fractions import Fraction
import json,io,subprocess,hashlib
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parents[1];timebase={x['source_id']:x for x in json.loads((R/'metadata/TIMEBASE.json').read_text())}
windows={'long_0035':(125,274),'long_0039':(0,149),'long_0060':(310,459),'short_0185':(0,99)}
records=[]
for key,(a,b) in windows.items():
 row=timebase[key];pts=list(map(Fraction,row['pts_rational']));idx=sorted(set(a+round(i*(b-a)/23) for i in range(24)));p=R/'sources'/(key+'.mp4')
 filt='select='+ '+'.join('eq(n\\,'+str(i)+')' for i in idx)+',scale=384:216:force_original_aspect_ratio=decrease,pad=384:216:(ow-iw)/2:(oh-ih)/2:black,tile=4x6'
 raw=subprocess.check_output(['ffmpeg','-v','error','-threads','2','-i',str(p),'-vf',filt,'-fps_mode','passthrough','-frames:v','1','-threads','1','-f','image2pipe','-c:v','png','pipe:1']);tiles=Image.open(io.BytesIO(raw));im=Image.new('RGB',(1536,1488),'black');d=ImageDraw.Draw(im);font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',15)
 for j,k in enumerate(idx):
  x=j%4*384;y=j//4*248;im.paste(tiles.crop((x,j//4*216,x+384,j//4*216+216)),(x,y));d.text((x+6,y+220),f'{key} | {k} | {float(pts[k]):.3f}s',fill='white',font=font)
 out=R/'contact_sheets'/(key+'_suggested_window.jpg');im.save(out,quality=93)
 end=pts[b+1] if b+1<len(pts) else Fraction(row['duration_ts'])*Fraction(row['time_base'])
 records.append({'source_id':key,'start_frame':a,'end_frame_inclusive':b,'start_pts_rational':str(pts[a]),'end_pts_rational_inclusive':str(pts[b]),'end_exclusive_rational':str(end),'duration_s':float(end-pts[a]),'indices':idx,'pts_rational':[str(pts[i]) for i in idx],'sheet':str(out),'sheet_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_only':True,'actual_clip_produced':False})
 print(key,str(pts[a]),str(end),flush=True)
(R/'metadata/SUGGESTED_WINDOWS.json').write_text(json.dumps(records,indent=2)+'\n')
