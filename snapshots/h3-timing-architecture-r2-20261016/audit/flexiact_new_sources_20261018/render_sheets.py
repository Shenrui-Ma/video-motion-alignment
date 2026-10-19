from pathlib import Path
import json,subprocess,csv,hashlib
from PIL import Image,ImageDraw,ImageFont,ImageOps
R=Path(__file__).resolve().parent;F=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',24);S=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',18)
rows=[]
for source in ['dogjump','dogstand','kangaroo']:
 p=R/'assets/benchmark/reference_videos/animal'/(source+'.mp4')
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_frames','-select_streams','v:0','-show_entries','frame=best_effort_timestamp_time','-of','json',str(p)]));pts=[float(f['best_effort_timestamp_time'])for f in probe['frames']]
 data=subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-f','rawvideo','-pix_fmt','rgb24','-threads','1','-']);size=720*480*3;assert len(data)==size*49
 canvas=Image.new('RGB',(1680,1340),'black');d=ImageDraw.Draw(canvas);d.text((12,8),source+' | ALL original frames | 49 frames at8fps | no generated video',font=F,fill='white')
 for n in range(49):
  im=Image.frombytes('RGB',(720,480),data[n*size:(n+1)*size]);im=ImageOps.contain(im,(234,156));x=(n%7)*240+3;y=40+(n//7)*184;canvas.paste(im,(x,y));d.text((x,y+159),f'{n:02d} | {pts[n]:.3f}s',font=S,fill='white')
 out=R/(source+'_source_all49.png');canvas.save(out)
 rows.append({'source':source,'source_file':str(p),'source_sha':hashlib.sha256(p.read_bytes()).hexdigest(),'pts':pts,'sheet':str(out)})
 targets=list(csv.DictReader((R/'assets/benchmark/captions/animal'/source/'val_image.csv').open()))
 can=Image.new('RGB',(500*min(3,len(targets)),440*((len(targets)+2)//3)),'black');dr=ImageDraw.Draw(can)
 for i,t in enumerate(targets):
  im=Image.open(R/'assets'/t['path']).convert('RGB');im=ImageOps.contain(im,(480,380));x=i%3*500+(500-im.width)//2;y=i//3*440+36;can.paste(im,(x,y));dr.text((i%3*500+10,i//3*440+8),f'CSV {i+1}: '+Path(t['path']).stem,font=S,fill='white')
 can.save(R/(source+'_official_targets.png'))
(R/'MEDIA_RECEIPT.json').write_text(json.dumps({'sources':rows,'all_frames_present':True,'GPU_started':False},indent=2)+'\n')
print('rendered 3 complete source grids and3target grids')
