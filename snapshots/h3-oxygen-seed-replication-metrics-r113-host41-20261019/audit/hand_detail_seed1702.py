from pathlib import Path
import sys, subprocess
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import save,bound
from media import seed_paths
base=ROOT/'audit/actual_seed2026101702_preview';out=base/'hand_detail';out.mkdir(exist_ok=True)
paths=seed_paths(base,2026101702); frames=[44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,84,85,86,87,88,89,90,91,92,93,94,95,96,97]
w,h=650,400
raws=[subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',str(p),'-vf','crop=650:400:516:308','-frames:v','98','-pix_fmt','rgb24','-threads','1','-f','rawvideo','-']) for p in paths]
font=ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc',22);pages=[]
for k in range(0,len(frames),4):
 f=frames[k:k+4];im=Image.new('RGB',(3*w,(h+32)*len(f)),(0,0,0));d=ImageDraw.Draw(im)
 for j,idx in enumerate(f):
  y=j*(h+32)
  for col,role in enumerate(['Source','Native','Fixed']):
   d.text((col*w+10,y+2),f'{role} | frame {idx}',font=font,fill='white')
   raw=raws[col][idx*w*h*3:(idx+1)*w*h*3];im.paste(Image.frombytes('RGB',(w,h),raw),(col*w,y+32))
 name=out/f'hand_{f[0]:03d}-{f[-1]:03d}.jpg';im.save(name,quality=95);pages.append({'frames':f,**bound(name)})
save(out/'BINDING.json',{'seed':2026101702,'roles':['source','native','fixed'],'input_files':[bound(p) for p in paths],'native_canvas_crop_xywh':[516,308,650,400],'same_crop_all_columns':True,'pages':pages,'purpose':'Enlarged hand-contact and strap-event inspection; full-frame review retained'})
print(str(out))
