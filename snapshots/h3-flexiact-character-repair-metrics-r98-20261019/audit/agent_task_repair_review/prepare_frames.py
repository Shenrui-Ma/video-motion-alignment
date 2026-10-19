from pathlib import Path
import hashlib,json,subprocess,sys
from PIL import Image,ImageDraw,ImageFont
A=Path(__file__).resolve().parent; R=A.parents[1]; sys.path.insert(0,str(R/'scripts'))
from common import validate_static,verify_intake
from render import media_info,check_time
C=validate_static(); verify_intake(); P=R/'showcase/PRESENTATION.json'; M=json.loads(P.read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bound(p): return {'file':str(p),'sha256':sha(p)}
assert M['schema']=='r98-three-column-task-repair-v1' and M['columns']==C['columns']
assert M['valid_frames']==147 and M['guidance_routed_calls']==[0,0]
for k in ['gate','collection']:
 assert sha(M[k]['file'])==M[k]['sha256']
assert len(M['inputs'])==3
F='/opt/homebrew/bin/ffmpeg'; FP='/opt/homebrew/bin/ffprobe';w,h=480,320;n=147;raws=[];media=[]
for row in M['inputs']:
 path=Path(row['file']);assert sha(path)==row['sha256']
 info=media_info(path,FP);check_time(info,158,1152,768)
 raw=subprocess.check_output([F,'-v','error','-threads','1','-i',str(path),'-vf',f'scale={w}:{h}:flags=lanczos','-frames:v',str(n),'-f','rawvideo','-pix_fmt','rgb24','-threads','1','-'],timeout=120)
 assert len(raw)==n*w*h*3;raws.append(raw);media.append({'file':str(path),'sha256':sha(path),'properties':info})
font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',17);sheets=[]
for start in range(0,n,5):
 ids=list(range(start,min(start+5,n)));im=Image.new('RGB',(3*w,len(ids)*(h+32)),'black');draw=ImageDraw.Draw(im)
 for row,i in enumerate(ids):
  for col,raw in enumerate(raws):
   im.paste(Image.frombytes('RGB',(w,h),raw[i*w*h*3:(i+1)*w*h*3]),(col*w,row*(h+32)))
   draw.text((col*w+6,row*(h+32)+h+5),f"{C['columns'][col]} | f{i:03d} | {i/24:.3f}s",font=font,fill='white')
 p=A/f'all_frames_{start:03d}_{ids[-1]:03d}.jpg';im.save(p,quality=96);sheets.append({**bound(p),'physical_frame_indices':ids})
ledger={'schema':'r98-complete-frame-review-ledger-v1','presentation':bound(P),'review_plan':bound(A/'REVIEW_PLAN.json'),'all_physical_frame_indices':list(range(n)),'media':media,'sheets':sheets,'note':'Same physical indices; 147 valid frames, original source 8fps repeated three times. All entries are CPU analysis media, not new generated videos.'}
(A/'FRAME_LEDGER.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'pages':len(sheets),'ledger':str(A/'FRAME_LEDGER.json')},ensure_ascii=False))
