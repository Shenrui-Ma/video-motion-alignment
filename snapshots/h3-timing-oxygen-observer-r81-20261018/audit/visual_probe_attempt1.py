"""Fixed same-time source/x0 contact sheet. CPU visualization only."""
import hashlib,json,subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'audit/consumer_attempt1/visual_probe';OUT.mkdir(parents=True,exist_ok=True)
source=ROOT.parent/'h3-timing-ivebench-expanded-r73-20261018/inputs/short_0252_video.mp4'
rows=[('Source',source)]+[(f'x0 denoise index {i}',ROOT/f'outputs/attempt1/step{i:03d}.mp4') for i in (0,6,12,19)]
frames=(0,20,40,60,80,97);w,h=400,225;bar=28
canvas=Image.new('RGB',(6*w,5*(h+bar)),(0,0,0));draw=ImageDraw.Draw(canvas)
font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',17)
ledger=[]
for ri,(label,path) in enumerate(rows):
    expression='+'.join(f'eq(n,{i})' for i in frames)
    vf=f'select=\'{expression}\',crop=1280:720:16:8,scale={w}:{h}:flags=lanczos'
    raw=subprocess.check_output(['ffmpeg','-v','error','-threads','2','-i',str(path),'-vf',vf,'-fps_mode','passthrough','-frames:v','6','-pix_fmt','rgb24','-threads','2','-f','rawvideo','-'],timeout=90)
    assert len(raw)==6*w*h*3
    for ci,f in enumerate(frames):
        im=Image.frombytes('RGB',(w,h),raw[ci*w*h*3:(ci+1)*w*h*3]);canvas.paste(im,(ci*w,ri*(h+bar)+bar));draw.text((ci*w+7,ri*(h+bar)+5),f'{label} | f{f:03d} | {f/24:.3f}s',font=font,fill='white')
    ledger.append({'label':label,'file':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'frames':list(frames),'PTS_seconds':[f/24 for f in frames]})
canvas.save(OUT/'source_x0_fixed6_times.png')
(OUT/'MANIFEST.json').write_text(json.dumps({'fixed_physical_frames':list(frames),'fixed_denoising_indices':[0,6,12,19],'source_based_adult':'right-side adult; whole frame retained to inspect person selection','no_temporal_alignment':True,'diagnostic_only':True,'rows':ledger},indent=2)+'\n')
print(OUT/'source_x0_fixed6_times.png')
