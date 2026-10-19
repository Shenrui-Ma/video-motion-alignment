from pathlib import Path
import subprocess,json,hashlib,io,sys
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parents[1];rows=[]
for p in sorted((R/'sources').glob('*.mp4')):
 meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,r_frame_rate,nb_frames,duration:frame=best_effort_timestamp_time','-show_frames','-of','json',str(p)]));s=meta['streams'][0];pts=[float(x['best_effort_timestamp_time']) for x in meta['frames']];n=len(pts);idx=sorted(set(round(i*(n-1)/15) for i in range(16)));assert len(idx)==16
 target=R/'contact_sheets'/(p.stem+'.jpg')
 if not target.exists():
  filt='select='+ '+'.join('eq(n\\,'+str(i)+')' for i in idx)+',scale=384:216:force_original_aspect_ratio=decrease,pad=384:216:(ow-iw)/2:(oh-ih)/2:black,tile=4x4'
  raw=subprocess.check_output(['ffmpeg','-v','error','-threads','2','-i',str(p),'-vf',filt,'-vsync','0','-frames:v','1','-threads','1','-f','image2pipe','-c:v','png','pipe:1'])
  tiles=Image.open(io.BytesIO(raw));out=Image.new('RGB',(1536,992),'black');d=ImageDraw.Draw(out);font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',15)
  for j,i in enumerate(idx):
   x=j%4*384;y=j//4*248;out.paste(tiles.crop((x,j//4*216,x+384,j//4*216+216)),(x,y));d.text((x+6,y+220),f'{p.stem} | {i} | {pts[i]:.3f}s',font=font,fill='white')
  out.save(target,quality=91)
 row={'source_id':p.stem,'width':s['width'],'height':s['height'],'fps_rational':s['avg_frame_rate'],'frames':n,'first_pts_s':pts[0],'last_pts_s':pts[-1],'duration_s':float(s.get('duration',pts[-1]+1/eval(s['avg_frame_rate']))),'pts_s':pts,'sheet_indices':idx,'sheet_times_s':[pts[i] for i in idx],'contact_sheet':str(target),'contact_sheet_sha256':hashlib.sha256(target.read_bytes()).hexdigest()};rows.append(row)
 print(p.stem,n,row['fps_rational'],row['duration_s'],flush=True)
(R/'metadata/TIMEBASE.json').write_text(json.dumps(rows,indent=2)+'\n')
