from pathlib import Path
import subprocess,json,hashlib,math
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).resolve().parent.parent
src=BASE/'source_candidates/pexels_5362065.mp4';dst=BASE/'inputs/04_fast_motion.mp4'
argv=['/opt/homebrew/bin/ffmpeg','-hide_banner','-loglevel','error','-y','-ss','0.24','-i',str(src),'-vf','fps=24,scale=1312:736:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1312:736:(ow-iw)/2:(oh-ih)/2,setsar=1','-frames:v','107','-an','-c:v','libx264','-crf','16','-preset','fast','-pix_fmt','yuv420p',str(dst)]
subprocess.run(argv,check=True)
probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(dst)]))
assert probe['streams'][0]['nb_read_frames']=='107'
(BASE/'inputs/04_fast_motion_ffprobe.json').write_text(json.dumps(probe,indent=2))
(BASE/'source_candidates/04_conversion_argv.json').write_text(json.dumps(argv,indent=2))
font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',18)
raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(dst),'-vf','scale=400:224','-f','rawvideo','-pix_fmt','rgb24','-']);s=400*224*3
frames=[Image.frombytes('RGB',(400,224),raw[i*s:(i+1)*s]) for i in range(len(raw)//s)]
for page in range(4):
 ids=list(range(page*30,min(len(frames),(page+1)*30)));can=Image.new('RGB',(2000,math.ceil(len(ids)/5)*252),'white');d=ImageDraw.Draw(can)
 for j,i in enumerate(ids):
  x=j%5*400;y=j//5*252;can.paste(frames[i],(x,y));d.text((x+3,y+226),f'f{i:03d} | {i/24:.3f}s | src~{i/24+.24:.3f}s',font=font,fill='black')
 can.save(BASE/f'source_candidates/04_fast_motion_frames_p{page+1}.jpg',quality=95)
subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-y','-i',str(dst),'-frames:v','1',str(BASE/'inputs/04_fast_motion.png')],check=True)
print(probe)
print(hashlib.sha256(dst.read_bytes()).hexdigest())
