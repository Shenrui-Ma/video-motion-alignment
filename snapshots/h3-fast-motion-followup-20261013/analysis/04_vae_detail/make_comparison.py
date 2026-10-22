from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import subprocess,json,hashlib,math
base=Path(__file__).resolve().parents[2];dest=Path(__file__).resolve().parent
paths={'SOURCE':base/'inputs/04_fast_motion.mp4','PREPARED':base/'outputs/04_fast_motion_actual_prepared_reference_00001_.mp4','VAE':base/'outputs/04_fast_motion_reference_vae_reconstruction_00001_.mp4'}
ids=[42,43,44,45]+list(range(72,86))+list(range(91,102));font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',18);frames={};ledger={}
for label,path in paths.items():
 probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(path)]))['streams'][0]
 assert probe['nb_read_frames']=='107' and probe['r_frame_rate']=='24/1'
 raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(path),'-vf','crop=800:680:480:50,scale=400:340','-f','rawvideo','-pix_fmt','rgb24','-']);n=400*340*3
 frames[label]=[Image.frombytes('RGB',(400,340),raw[i*n:(i+1)*n]) for i in range(len(raw)//n)]
 ledger[label]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'probe':probe}
for page in range(math.ceil(len(ids)/4)):
 values=ids[page*4:(page+1)*4];can=Image.new('RGB',(1200,len(values)*367+35),'white');d=ImageDraw.Draw(can)
 for col,label in enumerate(paths):d.text((col*400+3,5),label+' | same native frame',font=font,fill='black')
 for row,i in enumerate(values):
  for col,label in enumerate(paths):
   x=col*400;y=row*367+35;can.paste(frames[label][i],(x,y));d.text((x+3,y+341),f'f{i:03d} | {i/24:.3f}s',font=font,fill='black')
 can.save(dest/f'transitions_p{page+1}.jpg',quality=96)
ledger['operation']={'indices':ids,'crop_xywh':[480,50,800,680],'display_size_each':[400,340],'enhancement':False,'temporal_interpolation':False,'spatial_resize':'ffmpeg scale800x680 crop to400x340 for display','time_alignment':'same zero-based frame index at24FPS','page_count':math.ceil(len(ids)/4)}
(dest/'ledger.json').write_text(json.dumps(ledger,indent=2))
print(json.dumps(ledger,indent=2))
