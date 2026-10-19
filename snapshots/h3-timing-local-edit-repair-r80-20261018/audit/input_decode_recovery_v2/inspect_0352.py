from pathlib import Path
import json,hashlib,subprocess,io
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2];out=Path(__file__).parent/'visual_short_0352';out.mkdir(exist_ok=True)
video=Path(__file__).parent/'incoming/short_0352/native.mp4';gate=json.loads((video.parent/'NATIVE_RUNTIME_GATE_HOST9_v2.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert gate['passed'] and sha(video)==gate['runs']['native']['video']['sha256']
source=ROOT/'inputs/short_0352_video.mp4';n=gate['runs']['native']['valid_frames'];frames=[round(i*(n-1)/5) for i in range(6)]
font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',20)
canvas=Image.new('RGB',(1280,402*6),'black');draw=ImageDraw.Draw(canvas)
for y,frame in enumerate(frames):
 for x,path in enumerate((source,video)):
  data=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',str(path),'-vf',f'select=eq(n\\,{frame}),crop=1280:720:16:8,scale=640:360','-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','-'],timeout=90)
  canvas.paste(Image.open(io.BytesIO(data)).convert('RGB'),(640*x,402*y))
  label=f'{"参考视频" if x==0 else "P1普通编辑"}  {frame/24:.3f}s'
  draw.text((x*640+(640-draw.textlength(label,font=font))/2,y*402+370),label,font=font,fill='white')
canvas.save(out/'six_times.png')
(out/'BINDING.json').write_text(json.dumps({'gate_sha256':sha(video.parent/'NATIVE_RUNTIME_GATE_HOST9_v2.json'),'native_sha256':sha(video),'source_sha256':sha(source),'valid_frames':n,'indices':frames,'selection':'six uniform frames over all valid source frames'},indent=2)+'\n')
print(out/'six_times.png')
