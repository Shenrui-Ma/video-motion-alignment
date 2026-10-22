from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import subprocess,io,json
root=Path('/Users/researcher/DevProjects/h3-musk-bedside-pair-20261014')
out=Path('/Users/researcher/DevProjects/h3-four-pair-evidence-review-20261015/musk07')
paths=[root/'inputs/07_real_ary_v.mp4',root/'outputs/07_musk_s1_baseline_00001_.mp4',root/'outputs/07_musk_s1_weight3_00001_.mp4']
labels=['Source','Unweighted','Weight x3']
font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',20)
frames=[]
for p in paths:
 b=subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-f','rawvideo','-pix_fmt','rgb24','-'])
 n=1312*736*3
 frames.append([Image.frombytes('RGB',(1312,736),b[i:i+n]) for i in range(0,len(b),n)])
def make(seq,name,crop=None,w=520):
 h=round(w*(crop[3]-crop[1])/(crop[2]-crop[0])) if crop else round(w*736/1312)
 for page,start in enumerate(range(0,len(seq),4)):
  sub=seq[start:start+4]
  canvas=Image.new('RGB',(w*3,(h+30)*len(sub)),'black');d=ImageDraw.Draw(canvas)
  for row,n in enumerate(sub):
   for col in range(3):
    im=frames[col][n]
    if crop:im=im.crop(crop)
    im=im.resize((w,h))
    canvas.paste(im,(col*w,row*(h+30)+30))
    d.text((col*w+6,row*(h+30)+4),f'{labels[col]} | frame {n:03d}',font=font,fill='white')
  canvas.save(out/f'{name}_{sub[0]:03d}-{sub[-1]:03d}.jpg',quality=94)
make(list(range(0,141,12))+[140],'coarse')
make(list(range(45,91,3)),'target',crop=(460,0,1200,736),w=460)
make(list(range(56,71)),'fine',crop=(560,70,1070,530),w=420)
(out/'sheet_manifest.json').write_text(json.dumps({'source_paths':list(map(str,paths)),'coarse_frames':list(range(0,141,12))+[140],'target_frames':list(range(45,91,3)),'fine_frames':list(range(56,71)),'all_frames_decoded':list(map(len,frames))},indent=2))
print('made',len(list(out.glob('*.jpg'))),'sheets')
