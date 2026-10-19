from pathlib import Path
import json,hashlib,subprocess,io
from PIL import Image,ImageDraw
B=Path('/Users/researcher/DevProjects'); A=Path(__file__).parent; I=B/'h3-benchmark-all-results-showcase-20261018/inventory/flexiact.json'; d=json.loads(I.read_text()); item=next(x for x in d['items'] if x['id']=='flex_r66_human2animal_1__game_man_4')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
(A/'inventory_before.json').write_bytes(I.read_bytes())
for n in ['build_inventory.py','PATH_AND_SHA_VALIDATION.json']:(A/(n+'.before')).write_bytes((A.parent/n).read_bytes())
frames={}; ledger={}
for col,k in enumerate(['reference_video_path','ordinary_video_path','guided_video_path']):
 p=Path(item[k]); assert sha(p)==item['media_sha256'][k]
 b=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(p),'-vf','scale=480:320','-frames:v','147','-f','rawvideo','-pix_fmt','rgb24','-'])
 assert len(b)==147*480*320*3
 frames[k]=[Image.frombytes('RGB',(480,320),b[n*480*320*3:(n+1)*480*320*3]) for n in range(147)]
 ledger[k]={'file':str(p),'sha256':sha(p),'decoded':147}
keys=list(range(0,147,3))
for page in range(7):
 im=Image.new('RGB',(1440,7*346),(0,0,0)); dr=ImageDraw.Draw(im)
 for r,n in enumerate(keys[page*7:(page+1)*7]):
  dr.text((4,r*346+4),f'frame {n} | t={n/24:.3f}s | source / Native / fixed',fill='white')
  for col,k in enumerate(frames):im.paste(frames[k][n],(col*480,r*346+26))
 im.save(A/f'all49_page_{page}.jpg',quality=93)
ledger['view_indices']=keys; ledger['note']='49 source timestamps at physical output frames 0,3,...144; no brightness change, same time, resize only'; ledger['target']={'file':item['reference_image_path'],'sha256':sha(item['reference_image_path'])}
(A/'FRAME_LEDGER.json').write_text(json.dumps(ledger,indent=2)+'\n')
print(A)
