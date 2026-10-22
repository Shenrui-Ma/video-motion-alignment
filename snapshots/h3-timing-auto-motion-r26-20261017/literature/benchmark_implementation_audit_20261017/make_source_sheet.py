import pathlib,json,fcntl,subprocess,io,time
from PIL import Image,ImageDraw,ImageFont
b=pathlib.Path(__file__).resolve().parent;lock=open('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock','a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:print('BUSY');raise SystemExit(75)
ids=['bike-packing','breakdance','breakdance-flare','dance-jump','dance-twirl','hike','hockey','lady-running','lucia','parkour','shooting','tennis']
rows={r['id']:r for r in json.loads((b/'MTBENCH_SOURCE_INVENTORY.json').read_text())};out=b/'source_review';out.mkdir(exist_ok=True)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',18)
for k in range(2):
 canvas=Image.new('RGB',(960,6*244),'#111111');draw=ImageDraw.Draw(canvas)
 for n,id in enumerate(ids[k*6:(k+1)*6]):
  raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',rows[id]['path'],'-vf',"select='eq(n,0)+eq(n,24)+eq(n,48)',scale=320:214",'-fps_mode','vfr','-frames:v','3','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
  assert len(raw)==320*214*3*3
  for j,frame in enumerate([0,24,48]):
   im=Image.frombytes('RGB',(320,214),raw[j*320*214*3:(j+1)*320*214*3]);canvas.paste(im,(j*320,n*244+30));draw.text((j*320+5,n*244+5),f'{id} | f{frame} / {frame/8:.1f}s',font=font,fill='white')
 canvas.save(out/f'candidate_source_grid_{k+1}.jpg',quality=90)
print('two sheets complete')
