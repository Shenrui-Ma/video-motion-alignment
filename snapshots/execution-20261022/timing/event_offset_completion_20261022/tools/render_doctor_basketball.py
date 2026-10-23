import sys,json,os,hashlib
from PIL import Image,ImageDraw
root='/data/research-user/h3_metrics_20261022'
case,role,nums,out=sys.argv[1:]
ids=[int(x) for x in nums.split(',')]
p=root+'/frames/'+('source' if role=='source' else 'by_run/new_'+case+'_'+role)+'/'+case
w,h=320,180
im=Image.new('RGB',(w*5,(h+24)*((len(ids)+4)//5)),(15,15,15));d=ImageDraw.Draw(im)
for n,f in enumerate(ids):
 a=Image.open(p+f'/{f+1:06d}.png').convert('RGB');a.thumbnail((w,h));x=n%5*w;y=n//5*(h+24)
 im.paste(a,(x+(w-a.width)//2,y+24+(h-a.height)//2));d.text((x+5,y+5),f'{case} {role} frame {f}',fill='white')
os.makedirs(os.path.dirname(out),exist_ok=True);im.save(out,quality=88)
print(out)
