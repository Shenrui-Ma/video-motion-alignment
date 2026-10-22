import fcntl,hashlib,json,subprocess,time
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
P=Path(__file__).parent;L=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock');lock=L.open('a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:print('BUSY');raise SystemExit(75)
t=time.time();pairs=json.loads((P/'PILOT_5_PAIR_BINDING.json').read_text())['pairs'];out=P/'source_review';out.mkdir(exist_ok=True);font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',17)
source=Image.new('RGB',(1200,5*188),'black');d=ImageDraw.Draw(source);target=Image.new('RGB',(1200,310),'black');dt=ImageDraw.Draw(target);indices=[0,12,24,36,48]
for y,row in enumerate(pairs):
 a=row['action'];v=row['source']['local_path']
 for x,n in enumerate(indices):
  dest=out/f'{a}_{n:03d}.png'
  subprocess.run(['ffmpeg','-v','error','-threads','1','-filter_threads','1','-i',v,'-vf',f'select=eq(n\\,{n})','-frames:v','1','-y',str(dest)],check=True,capture_output=True)
  im=Image.open(dest).convert('RGB');im.thumbnail((240,160));source.paste(im,(240*x,y*188));d.text((240*x+5,y*188+163),f'{a} | {n:02d} | {n/8:g}s',font=font,fill='white')
 im=Image.open(row['target']['local_path']).convert('RGB');im.thumbnail((236,270));target.paste(im,(240*y+(240-im.width)//2,(270-im.height)//2));dt.text((240*y+5,275),a,font=font,fill='white');dt.text((240*y+5,294),Path(row['target']['local_path']).name,font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',12),fill='white')
source.save(out/'five_sources_fixed_0_12_24_36_48.jpg',quality=94);target.save(out/'five_official_targets.jpg',quality=94)
(P/'SOURCE_GRID_RECEIPT.json').write_text(json.dumps({'source_only':True,'frames':indices,'no_pose_model':True,'source_sha256':[x['source']['official_lfs_sha256'] for x in pairs],'seconds':time.time()-t,'output_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.glob('*.jpg')}},indent=2)+'\n');print('grid complete')
