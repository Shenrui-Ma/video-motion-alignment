from pathlib import Path
import hashlib,io,json,subprocess
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
source=ROOT/'inputs/short_0135_video.mp4';native=HERE/'native.mp4';paths=[source,native]
manifest=json.loads((HERE/'MANIFEST.json').read_text());assert hashlib.sha256(source.read_bytes()).hexdigest()==manifest['source_sha256']
assert hashlib.sha256(native.read_bytes()).hexdigest()==next(x['sha256'] for x in manifest['files'] if x['name']=='native.mp4')
props=[]
for path in paths:
 p=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_frames','-show_entries','stream=width,height,nb_read_frames,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(path)]))
 s=p['streams'][0];pts=[float(x['best_effort_timestamp_time']) for x in p['frames']]
 assert (s['width'],s['height'],int(s['nb_read_frames']),s['avg_frame_rate'])==(1312,736,124,'24/1')
 assert len(pts)==124 and all(abs(t-i/24)<=1e-6 for i,t in enumerate(pts))
 props.append({'file':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'properties':s,'pts_equal_i_over_24':True})
indices=[round(i*111/5) for i in range(6)];font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',18)
canvas=Image.new('RGB',(1280,408*6),'black');draw=ImageDraw.Draw(canvas)
for row,frame in enumerate(indices):
 for col,path in enumerate(paths):
  data=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(path),'-vf',f'select=eq(n\\,{frame}),crop=1280:720:16:8,scale=640:360:flags=lanczos','-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','-'],timeout=90)
  canvas.paste(Image.open(io.BytesIO(data)).convert('RGB'),(640*col,408*row))
  txt=['1.参考视频','2.编辑后视频'][col];draw.text((640*col+(640-draw.textlength(txt,font=font))/2,408*row+380),txt,fill='white',font=font)
 draw.text((8,row*408+362),f'{frame/24:.3f}s | frame {frame:03}',font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',13),fill='#aaa')
figure=HERE/'source_native_six_times.png';canvas.save(figure)
receipt={'source_id':'short_0135','scope':'Native-only preliminary task review, forced still running','valid_frames':112,'total_frames':124,'fps':24,'crop_xywh':[16,8,1280,720],'uniform_frame_indices':indices,'inputs':props,'figure':{'file':str(figure),'sha256':hashlib.sha256(figure.read_bytes()).hexdigest()}}
(HERE/'PRESENTATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
