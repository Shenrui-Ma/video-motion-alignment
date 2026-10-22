from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import subprocess,json
out=Path('/Users/researcher/DevProjects/h3-four-pair-evidence-review-20261015/sam07')
base=Path('/Users/researcher/DevProjects/h3-sam-real-dance-batch-20261015')
files={'source':base/'inputs/07_real_ary_v.mp4','baseline':base/'outputs/07_sam_s1_baseline_00001_.mp4','weight3':base/'outputs/07_sam_s1_weight3_00001_.mp4'}
for name,p in files.items():
 d=out/'frames'/name;d.mkdir(parents=True,exist_ok=True)
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(p),'-fps_mode','passthrough','-start_number','0',str(d/'%03d.png')],check=True)

def sheet(nums,name,width=430,crop=None):
 h=round(width*736/1312) if not crop else round(width*(crop[3]-crop[1])/(crop[2]-crop[0]))
 im=Image.new('RGB',(width*3,(h+24)*len(nums)+30),'#111111');draw=ImageDraw.Draw(im)
 for j,label in enumerate(files):draw.text((j*width+5,8),label,fill='white')
 for i,num in enumerate(nums):
  for j,label in enumerate(files):
   fr=Image.open(out/'frames'/label/f'{num:03d}.png')
   if crop: fr=fr.crop(crop)
   im.paste(fr.resize((width,h)),(j*width,i*(h+24)+54))
   draw.text((j*width+5,i*(h+24)+34),f'frame {num:03d} ({num/24:.3f}s)',fill='white')
 im.save(out/f'{name}.jpg',quality=92)
for i in range(2):sheet(list(range(0,141,10))[i*8:(i+1)*8],f'coarse_{i+1}')
for i in range(2):sheet(list(range(45,91,3))[i*8:(i+1)*8],f'target_{i+1}')
