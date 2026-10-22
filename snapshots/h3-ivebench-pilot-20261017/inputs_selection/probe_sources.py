from pathlib import Path
import subprocess,json,hashlib,fcntl,io
from PIL import Image,ImageDraw,ImageFont
base=Path(__file__).parent; lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock'); lock.parent.mkdir(parents=True,exist_ok=True)
results=[]; review=base/'source_review';review.mkdir(exist_ok=True)
with lock.open('a') as f:
 fcntl.flock(f,fcntl.LOCK_EX)
 for path in sorted((base/'candidate_sources').glob('*.mp4')):
  args=['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','stream=width,height,nb_frames,avg_frame_rate,r_frame_rate,duration:frame=best_effort_timestamp_time','-of','json',str(path)]
  p=json.loads(subprocess.check_output(args)); s=p['streams'][0]; ts=[float(x['best_effort_timestamp_time']) for x in p['frames']]; n=len(ts); indices=sorted(set(round(i*(n-1)/7) for i in range(8)))
  s.update({'file':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'pts_s':ts,'decoded_frames':n,'contact_sheet_indices':indices});results.append(s)
  sheet=Image.new('RGB',(1600,510),'#111111');d=ImageDraw.Draw(sheet)
  for j,i in enumerate(indices):
   raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(path),'-vf',f"select=eq(n\\,{i}),scale=400:230:force_original_aspect_ratio=decrease",'-frames:v','1','-f','image2pipe','-c:v','png','-threads','1','pipe:1'])
   im=Image.open(io.BytesIO(raw));x=(j%4)*400+(400-im.width)//2;y=(j//4)*255+25;sheet.paste(im,(x,y));d.text(((j%4)*400+6,(j//4)*255+5),f'{path.stem} frame {i} / {ts[i]:.3f}s',fill='white')
  sheet.save(review/(path.stem+'.jpg'),quality=90)
 (base/'SOURCE_TIMEBASE.json').write_text(json.dumps(results,indent=2));print([(Path(r['file']).name,r['width'],r['height'],r['decoded_frames'],r['avg_frame_rate'],r['pts_s'][-1]) for r in results])
