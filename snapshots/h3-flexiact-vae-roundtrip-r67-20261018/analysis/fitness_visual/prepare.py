from pathlib import Path
import json,hashlib,subprocess,argparse
from PIL import Image,ImageFont,ImageDraw
ap=argparse.ArgumentParser();ap.add_argument('--attempt',default='fitness_attempt2');args=ap.parse_args();assert args.attempt in ['fitness_attempt2'];
r=Path(__file__).resolve().parent;root=r.parents[1];media=r/'media';media.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=json.loads((root/'inputs/fitness/PREPARED.json').read_text());d=json.loads((root/'outputs'/args.attempt/'RESULT.json').read_text());assert d['status']=='complete' and d['fallback_guard']['calls']==0 and d['prepared_sha256']==sha(root/'inputs/fitness/PREPARED.json')
items={'source':(root/'inputs/fitness',p['products']['prepared_158']),'reconstruction':(root/'outputs'/args.attempt,d['products']['reconstruction_158'])};ev={'decode_receipt_sha256':sha(root/'outputs'/args.attempt/'RESULT.json'),'videos':{}}
for arm,(folder,item) in items.items():
 video=folder/item['file'];assert sha(video)==item['sha256'];dest=media/arm;dest.mkdir(exist_ok=True)
 info=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(video)]));pts=[float(x['best_effort_timestamp_time']) for x in info['frames']];assert len(pts)==158 and all(abs(t-i/24)<1e-5 for i,t in enumerate(pts))
 subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-y','-i',str(video),'-vf','select=not(mod(n\\,3))*lte(n\\,144)','-fps_mode','passthrough','-start_number','0',str(dest/'original_%03d.png')],check=True)
 files=sorted(dest.glob('original_*.png'));assert len(files)==49
 ev['videos'][arm]={'file':str(video),'sha256':sha(video),'frame_count':158,'sample_indices':list(range(0,147,3)),'extracted_file_hashes':[sha(x) for x in files]}
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf',20)
labels=['实际参考 RGB','参考 VAE 回解'];arms=list(items)
def sheet(indices,name):
 width=576;height=384;cap=34;can=Image.new('RGB',(width*2,len(indices)*(height+cap)),'black');draw=ImageDraw.Draw(can)
 for row,i in enumerate(indices):
  for col,arm in enumerate(arms):
   im=Image.open(media/arm/f'original_{i:03d}.png').convert('RGB');assert im.size==(1152,768);can.paste(im.resize((width,height),Image.Resampling.LANCZOS),(col*width,row*(height+cap)));draw.text((col*width+8,row*(height+cap)+height+5),f'{labels[col]} | {i/8:.3f}s',font=font,fill='white')
 can.save(media/name)
sheet([0,4,8,12,16,20],'six_times_0_to_2p5s.png')
for start in range(0,49,7):sheet(range(start,start+7),f'all49_page_{start:02d}_{start+6:02d}.png')
(r/'ACTUAL_BINDING.json').write_text(json.dumps(ev,ensure_ascii=False,indent=2)+'\n')
print(media/'six_times_0_to_2p5s.png')
