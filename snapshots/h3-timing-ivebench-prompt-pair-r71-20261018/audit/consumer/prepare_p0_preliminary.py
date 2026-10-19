"""CPU presentation of completed P0 only, selected before P1 completion."""
import hashlib,io,json,subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import postrun as p
out=p.HERE/'p0_preliminary';v=out/'p0.mp4';src=p.PRODUCER/'inputs/short_0210_video.mp4'
assert p.sha(v)=='7bf0c73dac230c92030fdb712293a1f369b0885c274f14721230411ea3b59910'
assert p.sha(src)=='1c595e408c119b3833af109816304fc0dca23fe6e05348651b03c556e9bf0600'
indices=[0,17,34,52,69,86];details=[]
for path in [src,v]:
 s=p.probe(path);assert (s['width'],s['height'],s['avg_frame_rate'],len(s['pts']))==(1312,736,'24/1',90)
 assert all(abs(t-i/24)<1e-6 for i,t in enumerate(s['pts']));details.append({'file':str(path),'sha256':p.sha(path),'frames':90,'fps':24,'PTS_verified':True})
font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',20)
canvas=Image.new('RGB',(1280,408*6),'black');draw=ImageDraw.Draw(canvas)
for row,i in enumerate(indices):
 for col,path in enumerate([src,v]):
  raw=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(path),'-vf',f'select=eq(n\\,{i}),crop=1280:720:16:8,scale=640:360:flags=lanczos','-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','-'],timeout=90)
  canvas.paste(Image.open(io.BytesIO(raw)).convert('RGB'),(640*col,408*row));label=['1.参考视频','2.原始提示词编辑'][col];draw.text((640*col+(640-draw.textlength(label,font=font))/2,408*row+374),label,font=font,fill='white')
 draw.text((6,408*row+362),f'{i/24:.3f}s',font=font,fill='#aaa')
fig=out/'six_times.png';canvas.save(fig)
p.save(out/'RECEIPT.json',{'schema':'r71-p0-only-preliminary-v1','files':details,'indices':indices,'crop_xywh':[16,8,1280,720],'figure':p.bound(fig),'P1_read':False,'selection':'same six preregistered uniform valid-prefix indices','scope':'actual P0 success; pair scientific equality still pending P1'})
print(fig)
