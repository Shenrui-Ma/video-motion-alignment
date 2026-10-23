from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
D=Path(__file__).resolve().parent
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',20)
def sheet(role,frames,name,crop,cols=5,width=340):
 ims=[]
 for n in frames:
  im=Image.open(D/role/f'{n:03d}.png').crop(crop);im=im.resize((width,round(im.height*width/im.width)));ims.append((n,im))
 h=ims[0][1].height+28;out=Image.new('RGB',(cols*width,((len(ims)+cols-1)//cols)*h),'#101010');dr=ImageDraw.Draw(out)
 for i,(n,im) in enumerate(ims):
  x=i%cols*width;y=i//cols*h;out.paste(im,(x,y+28));dr.text((x+6,y+3),f'{role}  frame {n}',font=font,fill='white')
 out.save(D/name)
sheet('partial_temporal_rope',range(54,74),'partial_hands_detail.jpg',(530,360,1130,720))
sheet('partial_temporal_rope',range(78,98),'partial_raise_detail.jpg',(530,70,1130,670))
for role,frames in [('source',list(range(40,53))+list(range(67,78))),('native',list(range(56,68))+list(range(82,94))),('global_weak',list(range(40,53))+list(range(67,78)))]:
 sheet(role,frames,role+'_events.jpg',(530,70,1130,720),cols=6,width=300)
