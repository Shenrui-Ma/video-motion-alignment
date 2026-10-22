exec(open('/Users/researcher/DevProjects/h3-four-pair-evidence-review-20261015/sam07/review.py').read().split('for name,p in files.items():')[0])
for start in (58,62,73,77):
 nums=range(start,start+4); width=400; crop=(335,80,960,736); h=round(width*(crop[3]-crop[1])/(crop[2]-crop[0])); im=Image.new('RGB',(width*3,(h+24)*4+30),'#111'); draw=ImageDraw.Draw(im)
 for j,l in enumerate(files):draw.text((j*width+5,8),l,fill='white')
 for i,n in enumerate(nums):
  for j,l in enumerate(files):
   fr=Image.open(out/'frames'/l/f'{n:03d}.png').crop(crop).resize((width,h))
   im.paste(fr,(j*width,i*(h+24)+54));draw.text((j*width+5,i*(h+24)+34),f'frame {n:03d}',fill='white')
 im.save(out/f'refine_{start}.jpg',quality=93)
