from pathlib import Path
import subprocess,json,hashlib,io
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parents[1];out=R/'source_review';results=[]
for p in sorted((R/'sources').glob('*.mp4')):
 meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,r_frame_rate,nb_frames:frame=best_effort_timestamp_time','-show_frames','-of','json',str(p)]));s=meta['streams'][0];pts=[float(x['best_effort_timestamp_time']) for x in meta['frames']];n=len(pts);indices=sorted(set(round(i*(n-1)/5) for i in range(6)));assert len(indices)==6
 target=out/(p.stem+'.jpg')
 if not target.exists():
  select='+'.join('eq(n\\,'+str(i)+')' for i in indices)
  vf='select='+select+',scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2:black,tile=3x2'
  data=subprocess.check_output(['ffmpeg','-v','error','-threads','2','-i',str(p),'-vf',vf,'-vsync','0','-frames:v','1','-threads','1','-f','image2pipe','-c:v','png','pipe:1'])
  tiles=Image.open(io.BytesIO(data)).convert('RGB');sheet=Image.new('RGB',(1440,600),'black');d=ImageDraw.Draw(sheet)
  font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',17)
  for j,i in enumerate(indices):
   x=(j%3)*480;y=(j//3)*300;sheet.paste(tiles.crop((x,(j//3)*270,x+480,(j//3)*270+270)),(x,y));d.text((x+8,y+276),f'{p.stem} | frame {i} | {pts[i]:.3f}s',font=font,fill='white')
  sheet.save(target,quality=91)
 row={'source_id':p.stem,'width':s['width'],'height':s['height'],'fps_rational':s['avg_frame_rate'],'decoded_frames':n,'last_pts_s':pts[-1],'actual_pts_s':pts,'six_time_indices':indices,'six_times_s':[pts[i] for i in indices],'overview':str(target),'overview_sha256':hashlib.sha256(target.read_bytes()).hexdigest()};results.append(row)
 print(p.stem,n,s['avg_frame_rate'],pts[-1],flush=True)
(R/'audit/SOURCE_TIMEBASE.json').write_text(json.dumps(results,indent=2)+'\n')
