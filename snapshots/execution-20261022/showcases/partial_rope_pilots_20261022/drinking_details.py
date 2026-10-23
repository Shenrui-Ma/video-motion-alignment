from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
D=Path(__file__).resolve().parent/'visual/short_0358';font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',20)
def sheet(method,first,last,tag):
 frames=list(range(first,last+1));cols=6;rows=(len(frames)+cols-1)//cols
 out=Image.new('RGB',(cols*280,rows*230),'#151515');d=ImageDraw.Draw(out)
 for i,f in enumerate(frames):
  im=Image.open(D/method/f'{f:03d}.jpg').crop((0,65,430,380)).resize((280,205));x=i%cols*280;y=i//cols*230;out.paste(im,(x,y+25));d.text((x+8,y),f'{method} {f}',font=font,fill='white')
 p=D/f'{method}_{tag}_{first}-{last}.jpg';out.save(p);print(p)
if __name__=='__main__':
 import sys;sheet(sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),sys.argv[4])
