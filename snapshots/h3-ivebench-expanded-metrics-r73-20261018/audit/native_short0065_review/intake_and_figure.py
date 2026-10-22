"""Actual completed Native only; CPU source comparison, pair remains pending."""
from pathlib import Path
import subprocess,shlex,json,hashlib,tarfile,io,time
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
REMOTE='/data5/researcher/h3_runs/timing_ivebench_expanded_r73_20261018';RUN='r73_short_0065_seed2026101701_native'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
code='''
from pathlib import Path
import json,hashlib,tarfile,sys,io
r=Path(REMOTE);run=RUN
paths=[r/'logs'/(run+'_history.json'),r/'logs'/(run+'_job.json'),r/'configs/graphs'/(run+'.json')]
h,j,g=[json.loads(p.read_text()) for p in paths]
assert h['status']['completed'] and h['status']['status_str']=='success' and j['status']=='success'
assert h['prompt'][1]==j['prompt_id'] and h['prompt'][2]==g
im=h['outputs']['14']['images'];assert len(im)==1 and im[0]['type']=='output'
rel=Path(im[0].get('subfolder',''))/im[0]['filename'];assert not rel.is_absolute() and '..' not in rel.parts
paths.append(r/'output'/rel)
manifest=[]
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as t:
 for p in paths:
  data=p.read_bytes();manifest.append({'remote':str(p),'name':p.name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
  item=tarfile.TarInfo(p.name);item.size=len(data);t.addfile(item,io.BytesIO(data))
 data=json.dumps(manifest).encode();item=tarfile.TarInfo('manifest.json');item.size=len(data);t.addfile(item,io.BytesIO(data))
'''.replace('Path(REMOTE)','Path('+repr(REMOTE)+')').replace('run=RUN','run='+repr(RUN))
archive=OUT/'actual_native.tar'
if not archive.exists():
 with archive.open('xb') as f:subprocess.run(['ssh','-J','H3_SERVER_B','H3_SERVER_A','python3 -c '+shlex.quote(code)],stdout=f,check=True,timeout=120)
with tarfile.open(archive) as t:
 manifest=json.load(t.extractfile('manifest.json'))
 for item in manifest:
  data=t.extractfile(item['name']).read();assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'];p=OUT/item['name']
  if p.exists():assert p.read_bytes()==data
  else:p.write_bytes(data)
source=ROOT/'inputs/short_0065_video.mp4';native=OUT/(RUN+'_00001_.mp4');frames=[round(i*46/5) for i in range(6)]
font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',21);small=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',16)
canvas=Image.new('RGB',(1280,402*6),'black');d=ImageDraw.Draw(canvas)
for row,n in enumerate(frames):
 for col,p in enumerate((source,native)):
  data=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(p),'-vf',f'select=eq(n\\,{n}),crop=1280:720:16:8,scale=640:360:flags=lanczos','-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','-'],timeout=60)
  canvas.paste(Image.open(io.BytesIO(data)).convert('RGB'),(640*col,402*row));label=('参考视频','普通编辑')[col];d.text((640*col+(640-d.textlength(label,font=font))/2,402*row+371),label,font=font,fill='white')
 d.text((7,402*row+363),f'{n/24:.3f}s · frame {n}',font=small,fill='#bbb')
figure=OUT/'source_native_six_times.png';canvas.save(figure)
record={'source':'short_0065','status':'NATIVE_COMPLETE_ONLY','pair_gate':'PENDING_FORCED','valid_frames':47,'frame_indices':frames,'crop':[16,8,1280,720],'source_sha256':sha(source),'native_sha256':sha(native),'figure':str(figure),'figure_sha256':sha(figure),'downloaded':manifest,'scope':'six fixed source timestamps, no temporal alignment, Native-only task inspection','GPU_calls':0,'unix':time.time()}
(OUT/'INTAKE.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'figure':str(figure),'frames':frames},ensure_ascii=False))
