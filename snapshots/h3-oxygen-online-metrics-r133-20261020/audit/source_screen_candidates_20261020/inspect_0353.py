from pathlib import Path
import json,subprocess,hashlib
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parent/'short0353_source_events';R.mkdir(exist_ok=True);S=Path('/Users/researcher/DevProjects/h3-ivebench-subject-candidates-r82-20261018/sources/short_0353.mp4');h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(S)]));assert len(probe['frames'])==49
raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(S),'-vf','scale=384:216','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','pipe:1']);assert len(raw)==49*384*216*3
font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',14);pages=[]
for first,last in [(0,24),(25,48)]:
 im=Image.new('RGB',(1920,1230),'black');d=ImageDraw.Draw(im)
 for j,i in enumerate(range(first,last+1)):
  x=j%5*384;y=j//5*246;b=raw[i*384*216*3:(i+1)*384*216*3];im.paste(Image.frombytes('RGB',(384,216),b),(x,y));d.text((x+4,y+220),f'f{i:02d} t={probe["frames"][i]["best_effort_timestamp_time"]}s',font=font,fill='white')
 p=R/f'frames_{first:02d}_{last:02d}.jpg';im.save(p,quality=91);pages.append({'file':str(p),'sha256':h(p),'frame_indices':list(range(first,last+1))})
(R/'BINDING.json').write_text(json.dumps({'source':{'file':str(S),'sha256':h(S)},'frames':49,'fps':probe['streams'][0]['avg_frame_rate'],'all_frame_pts_s':[float(f['best_effort_timestamp_time'])for f in probe['frames']],'pages':pages,'source_only':True,'new_downloads':0,'new_inference':False},indent=2)+'\n');print(json.dumps(pages))
