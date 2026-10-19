from pathlib import Path
import subprocess,json,io,hashlib
from PIL import Image,ImageDraw,ImageOps
ROOT=Path(__file__).resolve().parent
out=ROOT/'review';out.mkdir(exist_ok=True)
records=[]
for p in sorted((ROOT/'official_assets/benchmark/reference_videos/human').glob('*.mp4')):
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_streams','-show_frames','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames,duration:frame=best_effort_timestamp_time','-of','json',str(p)]));s=probe['streams'][0];pts=[float(x['best_effort_timestamp_time']) for x in probe['frames']];n=len(pts);indices=sorted(set(round(i*(n-1)/11) for i in range(12)));sheet=Image.new('RGB',(4*400,3*252),'#111');draw=ImageDraw.Draw(sheet)
 for j,i in enumerate(indices):
  data=subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-vf',f'select=eq(n\\,{i})','-frames:v','1','-f','image2pipe','-vcodec','png','-']);im=Image.open(io.BytesIO(data)).convert('RGB');thumb=ImageOps.contain(im,(400,225));x=(j%4)*400;y=(j//4)*252;sheet.paste(thumb,(x+(400-thumb.width)//2,y));draw.text((x+5,y+228),f'{p.stem} | frame {i} | {pts[i]:.3f}s',fill='white')
 file=out/(p.stem+'.jpg');sheet.save(file,quality=93);records.append({'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'stream':s,'frame_pts_s':pts,'indices':indices,'review_file':str(file),'review_sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
targets=sorted((ROOT/'official_assets/benchmark/target_images/human').glob('*'));sheet=Image.new('RGB',(5*260,4*330),'#111');d=ImageDraw.Draw(sheet)
for j,p in enumerate(targets):
 im=Image.open(p).convert('RGB');thumb=ImageOps.contain(im,(250,290));x=(j%5)*260;y=(j//5)*330;sheet.paste(thumb,(x+(260-thumb.width)//2,y));d.text((x+4,y+298),p.name,fill='white');d.text((x+4,y+313),str(im.size),fill='white')
sheet.save(out/'all_human_targets.jpg',quality=94)
(ROOT/'audit/SOURCE_FRAME_PROBE.json').write_text(json.dumps(records,indent=2)+'\n')
print([(Path(x['file']).stem,x['stream']) for x in records])
