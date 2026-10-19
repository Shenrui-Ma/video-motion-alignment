from pathlib import Path
import json,subprocess,io,hashlib
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parents[1];tb={x['source_id']:x for x in json.loads((R/'metadata/TIMEBASE.json').read_text())}
windows={'long_0047':(0,179),'long_0123':(45,224),'long_0167':(9,158),'long_0173':(105,248),'long_0174':(9,152),'long_0031':(179,328),'long_0059':(171,320),'long_0163':(52,201)}
rows=[]
for sid,(a,b) in windows.items():
 t=tb[sid];pts=t['pts_s'];indices=sorted(set(round(a+i*(b-a)/23) for i in range(24)));p=R/'sources'/(sid+'.mp4');target=R/'contact_sheets'/(sid+'_suggested_window.jpg')
 vf='select='+ '+'.join('eq(n\\,'+str(i)+')' for i in indices)+',scale=384:216:force_original_aspect_ratio=decrease,pad=384:216:(ow-iw)/2:(oh-ih)/2:black,tile=4x6'
 raw=subprocess.check_output(['ffmpeg','-v','error','-threads','2','-i',str(p),'-vf',vf,'-vsync','0','-frames:v','1','-threads','1','-f','image2pipe','-c:v','png','pipe:1'])
 tiles=Image.open(io.BytesIO(raw));out=Image.new('RGB',(1536,1488),'black');d=ImageDraw.Draw(out);font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',15)
 for j,i in enumerate(indices):
  x=j%4*384;y=j//4*248;out.paste(tiles.crop((x,j//4*216,x+384,j//4*216+216)),(x,y));d.text((x+6,y+220),f'{sid} | {i} | {pts[i]:.3f}s',font=font,fill='white')
 out.save(target,quality=90)
 rows.append({'source_id':sid,'start_frame':a,'end_frame_inclusive':b,'start_pts_s':pts[a],'end_pts_s_inclusive':pts[b],'end_exclusive_s':pts[b+1] if b+1<len(pts) else t['duration_s'],'duration_by_frame_intervals_s':(b-a+1)/(eval(t['fps_rational'])),'indices':indices,'times_s':[pts[i] for i in indices],'sheet':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'proposal_only_no_clip_generated':True})
 print(sid,pts[a],pts[b],flush=True)
(R/'metadata/SUGGESTED_WINDOWS.json').write_text(json.dumps(rows,indent=2)+'\n')
